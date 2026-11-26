"""Fixtures REST sintéticos: ningún acceso a GitHub ni publicación."""
import io
import json
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from scripts.salud_cola_global_observar import (
    GitHubReader, NoRedirect, ObservationError, REPOSITORIES, ROOT, observe,
)

SHA = "a" * 40


class Response(io.BytesIO):
    def __init__(self, url, data, link=None, remaining=4000):
        super().__init__(json.dumps(data).encode())
        self.url, self.status = url, 200
        self.headers = Message()
        for key, value in (("Limit", "5000"), ("Remaining", str(remaining)), ("Resource", "core")):
            self.headers["X-RateLimit-" + key] = value
        if link is not None:
            self.headers["Link"] = link

    def geturl(self):
        return self.url


class Fixture:
    def __init__(self, variant=None):
        self.variant, self.calls, self.sweep = variant, [], 0

    def open(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        assert request.get_method() == "GET" and request.full_url.startswith(ROOT + "/")
        assert 0 < timeout <= 10
        url = request.full_url
        parts = urlsplit(url)
        if parts.path == "/rate_limit":
            self.sweep += 1
            return Response(url, {"resources": {"core": {"limit": 5000,
                "remaining": 100 if self.variant == "low" else 4000}}})
        repo = parts.path.split("/")[3]
        endpoint = f"{ROOT}/repos/pl0n3r/{repo}"
        if not parts.query:
            identity = REPOSITORIES.index(repo) + 1
            if repo == "Factory" and self.sweep == 2 and self.variant == "identity_drift":
                identity += 50
            return Response(url, {"full_name": "wrong" if self.variant == "identity"
                                  else f"pl0n3r/{repo}", "id": identity, "archived": False})
        page = int(parse_qs(parts.query)["page"][0])
        if self.variant in ("forbidden", "rate_limited", "omitted") and (
                self.variant != "omitted" or page == 2):
            code = {"forbidden": 403, "rate_limited": 429, "omitted": 404}[self.variant]
            raise HTTPError(url, code, "PRIVATE-FIXTURE", Message(), None)
        if self.variant == "timeout":
            raise TimeoutError("PRIVATE-FIXTURE")
        size = 100 if repo == "Factory" and page == 1 else 1
        label = "estado: disponible" if repo in ("Factory", "Condor") else "status: blocked"
        if self.variant == "drift" and self.sweep == 2 and repo == "Factory":
            label = "estado: reservado"
        rows = [{"number": (page - 1) * 100 + n, "state": "open",
                 "repository_url": endpoint, "url": f"{endpoint}/issues/{(page-1)*100+n}",
                 "labels": [{"name": label}], "body": "PRIVATE-FIXTURE",
                 "user": {"login": "private-fixture"}} for n in range(1, size + 1)]
        if self.variant == "row_identity":
            rows[0]["repository_url"] = ROOT + "/repos/other/repo"
        if repo == "Factory":
            link = (f'<{endpoint}/issues?state=open&per_page=100&page=2>; rel="next", '
                    f'<{endpoint}/issues?state=open&per_page=100&page=2>; rel="last"'
                    if page == 1 else f'<{endpoint}/issues?state=open&per_page=100&page=1>; rel="prev"')
            if self.variant == "absent_link":
                link = None
            elif self.variant == "invalid_link":
                link = '<https://example.test/PRIVATE-FIXTURE>; rel="next"'
        else:
            link = None
        return Response(url + ("&unexpected=1" if self.variant == "redirect" else ""), rows,
                        link, remaining=100 if self.variant == "mid_quota" else 4000)


class GlobalQueueObserverTests(unittest.TestCase):
    def test_stable_seven_repo_sweeps_and_fail_closed(self):
        fixture = Fixture()
        result = observe(GitHubReader("fixture-token", opener=fixture), SHA)
        self.assertEqual(result["status"], "OBSERVED_GLOBAL_ONLY")
        self.assertEqual(result["open_total"], 107)
        self.assertEqual(result["available_total"], 102)
        self.assertEqual(set(result["fingerprints"]), set(REPOSITORIES))
        self.assertEqual(len(fixture.calls), 33)  # 3 quota + 2*(7 identity + 8 page)
        self.assertIsNone(result["capacity"])
        self.assertEqual(result["authority"], "unchanged")
        self.assertEqual(result["writes"], 0)
        self.assertNotIn("PRIVATE-FIXTURE", json.dumps(result))
        self.assertNotIn("private-fixture", json.dumps(result))
        for variant in ("absent_link", "invalid_link", "omitted", "drift", "identity",
                        "identity_drift", "row_identity", "redirect", "low", "mid_quota",
                        "forbidden", "rate_limited", "timeout"):
            with self.subTest(variant=variant):
                fixture = Fixture(variant)
                result = observe(GitHubReader("fixture-token", opener=fixture), SHA)
                self.assertIn(result["status"], ("UNKNOWN", "DEFERRED"))
                self.assertIsNone(result["counts"])
                self.assertIsNone(result["fingerprints"])
                self.assertEqual(result["writes"], 0)
                self.assertNotIn("PRIVATE-FIXTURE", json.dumps(result))
                self.assertNotIn("available_total", result)

    def test_scheduled_global_observer_is_get_only(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/salud-cola.yml").read_text()
        observer = workflow.split("\n  publicar:\n", 1)[0]
        self.assertEqual(workflow.count("cron:"), 1)
        self.assertIn("python3 -m scripts.salud_cola_global_observar", observer)
        self.assertIn("salud_cola_observar.py | python3 -m scripts.salud_cola_publicar", observer)
        self.assertNotIn("issues: write", observer)
        self.assertNotIn("salud_cola_alertar", observer)
        self.assertNotIn("secrets.", workflow)
        fixture = Fixture()
        reader = GitHubReader("fixture-token", opener=fixture)
        self.assertEqual(observe(reader, SHA)["status"], "OBSERVED_GLOBAL_ONLY")
        self.assertTrue(all(method == "GET" for method, _ in fixture.calls))
        with self.assertRaisesRegex(ObservationError, "endpoint_forbidden"):
            reader.get("https://example.test", 1)
        with self.assertRaisesRegex(ObservationError, "redirect_rejected"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test")
        ticks = iter((0, 121))
        result = observe(GitHubReader("fixture-token", opener=Fixture(),
                                      clock=lambda: next(ticks)), SHA)
        self.assertEqual(result["reason"], "window_expired")


if __name__ == "__main__":
    unittest.main()
