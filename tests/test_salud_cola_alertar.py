"""Aceptación #1539: aviso autorizado solo en Factory y evidencia completa."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import salud_cola_alertar as alert
from scripts.salud_cola import REPOSITORIES
from scripts.salud_cola_alertar import (
    ALERT_LABELS, ALERT_TITLE, AlertError, FACTORY, GitHubAPI, ejecutar, main,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeAPI:
    def __init__(self):
        self.repos = {
            "pl0n3r/" + name: [{"number": i + 1, "labels": [
                {"name": "estado: bloqueado"}], "body": "PII no publicable: test@example.com"}]
            for i, name in enumerate(REPOSITORIES)
        }
        self.history = []
        self.calls = []
        self.writes = []
        self.remaining = 4500
        self.missing = None
        self.stale = False
        self.inv_checks = 0
        self.limit = 5000
        self.kill_state = "RUNNING"

    def get(self, path):
        self.calls.append(("GET", path))
        if path == "/rate_limit":
            return {"resources": {"core": {
                "limit": self.limit, "remaining": self.remaining}}}
        if path == "/repos/pl0n3r/Factory/issues/767":
            return {"number": 767, "state": "closed", "user": {"login": "pl0n3r"},
                    "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
                    "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
                    "body": '<!-- factory-unattended-kill-switch '
                            + json.dumps({"version": 1, "state": self.kill_state,
                                          "owner": "pl0n3r"}) + ' -->'}
        for repo in self.repos:
            if path == "/repos/" + repo:
                name = self.missing if self.missing and repo.endswith(self.missing) else repo
                return {"full_name": None if self.missing and repo.endswith(self.missing)
                        else name, "private": False}
        if path.startswith("/repos/") and "/issues?" in path:
            repo, qs = path[len("/repos/"):].split("/issues?", 1)
            page = int(qs.rsplit("page=", 1)[-1])
            if "state=all" in qs:
                labels = set((ALERT_LABELS[0], ALERT_LABELS[-1]))
                matching = [row for row in self.history if labels.issubset({
                    item.get("name") for item in row.get("labels", [])
                    if type(item) is dict
                })]
                start = (page - 1) * alert.PAGE_SIZE
                return copy.deepcopy(matching[start:start + alert.PAGE_SIZE])
            if repo not in self.repos:
                raise AlertError("fake_missing_repo")
            if self.stale and repo == FACTORY:
                self.inv_checks += 1
                if self.inv_checks > 1:
                    return [{"number": 888, "labels": [{"name": "estado: disponible"}]}]
            return copy.deepcopy(self.repos[repo]) if page == 1 else []
        if path.startswith("/repos/pl0n3r/Factory/issues/"):
            number = int(path.rsplit("/", 1)[-1])
            found = [x for x in self.history if x["number"] == number]
            return copy.deepcopy(found[0]) if found else None
        raise AlertError("fake_forbidden")

    def write(self, method, path, payload):
        self.writes.append((method, path, copy.deepcopy(payload)))
        if method == "POST" and path == "/repos/pl0n3r/Factory/issues":
            number = 20000
            new = {"number": number, "state": "open", "body": payload["body"],
                   "user": {"login": "github-actions[bot]", "type": "Bot"},
                   "labels": [{"name": name} for name in payload["labels"]]}
            self.history.append(copy.deepcopy(new))
            self.repos[FACTORY].append(copy.deepcopy(new))
            return {"number": number}
        if method == "PATCH" and path == "/repos/pl0n3r/Factory/issues/20000":
            self.history[0]["body"] = payload["body"]
            self.repos[FACTORY][-1]["body"] = payload["body"]
            return {"number": 20000}
        raise AlertError("write_outside_factory")


class SaludColaAlertarTests(unittest.TestCase):
    def test_complete_seven_repository_evidence_required(self):
        api = FakeAPI()
        self.assertEqual(ejecutar(api, enabled=True)["status"], "CREATED")
        names = ["pl0n3r/" + n for n in REPOSITORIES]
        for repo in names:
            self.assertIn(("GET", "/repos/" + repo), api.calls)
            self.assertIn(("GET", "/repos/" + repo
                           + "/issues?state=open&per_page=100&page=1"), api.calls)
        self.assertEqual(len(api.writes), 1)
        for bad in ("brvtal", "FactoryRunner"):
            api = FakeAPI()
            api.missing = bad
            self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
            self.assertFalse(api.writes)
        api = FakeAPI()
        api.repos[FACTORY][0]["labels"] = []
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)
        api = FakeAPI()
        api.remaining = 900
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)
        api = FakeAPI()
        api.stale = True
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)

    def test_deduplicate_and_update_one_factory_issue_only(self):
        api = FakeAPI()
        first = ejecutar(api, enabled=True)
        self.assertEqual(first["status"], "CREATED")
        second = ejecutar(api, enabled=True)
        self.assertEqual(second["status"], "UPDATED")
        third = ejecutar(api, enabled=True)
        self.assertEqual(third["status"], "SKIPPED")
        self.assertEqual(third["reason"], "unchanged_alert")
        self.assertEqual([m for m, _, _ in api.writes], ["POST", "PATCH"])
        self.assertTrue(all(p.startswith("/repos/pl0n3r/Factory/issues")
                            for _, p, _ in api.writes))
        api.history[0]["state"] = "closed"
        api.repos[FACTORY] = [api.repos[FACTORY][0]]
        self.assertEqual(ejecutar(api, enabled=True)["reason"], "owner_closed_alert")
        self.assertEqual(len(api.writes), 2)
        api.history.append(copy.deepcopy(api.history[0]))
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertEqual(len(api.writes), 2)
        api.history = [api.history[0]]
        api.history[0]["user"] = {"login": "untrusted", "type": "User"}
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertEqual(len(api.writes), 2)

    def test_read_only_default_and_explicit_factory_write_authority(self):
        api = FakeAPI()
        self.assertEqual(ejecutar(api)["reason"], "disabled_by_default")
        self.assertFalse(api.calls or api.writes)
        api.kill_state = "PAUSED"
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)
        client = GitHubAPI("fake")
        for path in ("/repos/pl0n3r/Condor/issues",
                     "/repos/pl0n3r/ControlBot/issues/21"):
            with self.assertRaises(AlertError):
                client.request("POST", path, {"body": "x"})
        with patch("scripts.salud_cola_alertar.os.environ", {}), \
             patch("scripts.salud_cola_alertar.sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(main(), 0)
            self.assertEqual(json.loads(out.getvalue())["writes"], 0)

    def test_no_customer_data_spam_or_unauthorized_incident_label(self):
        api = FakeAPI()
        self.assertEqual(ejecutar(api, enabled=True)["status"], "CREATED")
        _, path, payload = api.writes[0]
        self.assertEqual(path, "/repos/pl0n3r/Factory/issues")
        self.assertEqual(payload["title"], ALERT_TITLE)
        self.assertEqual(payload["labels"], ALERT_LABELS)
        self.assertNotIn("tipo: incidente", payload["labels"])
        self.assertNotIn("test@example.com", json.dumps(payload))
        self.assertNotIn("github-actions", json.dumps(payload))
        self.assertIn("no es un incidente", payload["body"])
        self.assertTrue(payload["body"].startswith("<!-- factory-queue-alert "))

    def test_workflow_preserves_observer_and_scoped_publisher(self):
        content = (ROOT / ".github/workflows/salud-cola.yml").read_text()
        legacy = content.split("\n  publicar:\n", 1)[0]
        self.assertEqual(legacy.count("issues: read"), 2)
        self.assertEqual(legacy.count("contents: read"), 2)
        self.assertIn("salud_cola_observar.py | python3 -m scripts.salud_cola_publicar", legacy)
        self.assertIn("issues: write", content)
        self.assertNotIn("issues: write", legacy)
        self.assertIn("github.event_name == 'workflow_dispatch'", content)
        self.assertIn("inputs.publicar == true", content)
        self.assertIn("default: false", content)
        self.assertIn("FACTORY_QUEUE_ALERT_ENABLED: 'true'", content)
        self.assertEqual(content.count("cron:"), 1)
        self.assertNotIn("secrets.", content)



    def test_canonical_kill_switch_rejects_duplicate_keys_and_extra_starts(self):
        """Un check de strings no sustituye la autoridad canónica."""
        good = '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
        hostile = (
            '<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","state":"RUNNING","owner":"pl0n3r"} -->',
            good + '\n<!-- factory-unattended-kill-switch broken-json -->',
            '<!-- factory-unattended-kill-switch {"version":true,"state":"RUNNING","owner":"pl0n3r"} -->',
        )
        for body in hostile:
            with self.subTest(body=body):
                api = FakeAPI()
                original = api.get

                def changed(path):
                    item = original(path)
                    if path == "/repos/pl0n3r/Factory/issues/767":
                        return {**item, "body": body}
                    return item

                with patch.object(api, "get", side_effect=changed):
                    self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
                self.assertEqual(api.writes, [])

        api = FakeAPI()
        original = api.get

        def wrong_origin(path):
            item = original(path)
            if path == "/repos/pl0n3r/Factory/issues/767":
                return {**item, "url": "https://api.github.com/repos/pl0n3r/Factory/issues/1"}
            return item

        with patch.object(api, "get", side_effect=wrong_origin):
            self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertEqual(api.writes, [])

    def test_bounded_filtered_alert_history_survives_unrelated_factory_issues(self):
        """La deduplicación no debe recorrer todos los Issues históricos."""
        api = FakeAPI()
        api.history = [
            {"number": number, "state": "closed", "labels": [{"name": "tipo: error"}],
             "user": {"login": "pl0n3r", "type": "User"}, "body": "unrelated"}
            for number in range(1, 2601)
        ]
        self.assertEqual(ejecutar(api, enabled=True)["status"], "CREATED")
        expected = ("/repos/pl0n3r/Factory/issues?state=all&labels="
                    + alert.ALERT_LOOKUP_LABELS + "&per_page=100&page=1")
        self.assertIn(("GET", expected), api.calls)
        self.assertFalse(any("state=all&per_page=" in path for _, path in api.calls))
        self.assertEqual([method for method, _, _ in api.writes], ["POST"])

    def test_transport_allowlist_http_and_bounded_json(self):
        class Response:
            status = 200
            def __init__(self, raw, status=200):
                self.raw = raw
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, size):
                return self.raw[:size]

        with self.assertRaises(AlertError):
            GitHubAPI("")
        api = GitHubAPI("synthetic-token")
        quota = {"resources": {"core": {"limit": 5000, "remaining": 4500}}}
        with patch.object(alert, "urlopen", return_value=Response(json.dumps(quota).encode())) as send:
            self.assertEqual(api.get("/rate_limit"), quota)
            request = send.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertIn("/rate_limit", request.full_url)
        with patch.object(alert, "urlopen", return_value=Response(b'{"number":3}', 201)):
            result = api.write("POST", "/repos/pl0n3r/Factory/issues",
                               {"title": "synthetic", "body": "safe"})
            self.assertEqual(result["number"], 3)
        for status, raw in ((500, b'{}'), (200, b'x' * (alert.MAX_RESPONSE_BYTES + 1))):
            with self.subTest(http_status=status, bytes=len(raw)):
                with patch.object(alert, "urlopen", return_value=Response(raw, status)):
                    with self.assertRaises(AlertError):
                        api.get("/rate_limit")
        with patch.object(alert, "urlopen", return_value=Response(b'not-json')):
            with self.assertRaises(ValueError):
                api.get("/rate_limit")
        with patch.object(alert, "urlopen", side_effect=OSError("network synthetic")):
            with self.assertRaises(OSError):
                api.get("/rate_limit")
        for method, path, payload in (
            ("DELETE", "/repos/pl0n3r/Factory/issues/12", None),
            ("POST", "/repos/pl0n3r/Condor/issues", {"body": "x"}),
            ("PATCH", "/repos/pl0n3r/Factory/issues/0", {"body": "x"}),
            ("GET", "/repos/pl0n3r/Condor/issues?state=all&per_page=100&page=1", None),
            ("GET", "/repos/pl0n3r/Factory/issues?state=all&per_page=100&page=25", None),
            ("GET", "/repos/pl0n3r/Factory/issues/767", {"x": 1}),
            ("GET", "/repos/pl0n3r/Factory/issues?state=all&per_page=100&page=1", None),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(AlertError):
                    api.request(method, path, payload)

    def test_inventory_and_pagination_reject_malformed_sources(self):
        api = FakeAPI()
        self.assertEqual(alert._quota(api)["remaining"], 4500)
        for malformed in (None, [], {}, {"resources": None},
                          {"resources": {"core": None}},
                          {"resources": {"core": {"limit": True, "remaining": 1}}},
                          {"resources": {"core": {"limit": 0, "remaining": 0}}}):
            with patch.object(api, "get", return_value=malformed):
                with self.assertRaises(AlertError):
                    alert._quota(api)
        api.limit = 5000
        api.remaining = 1199
        with self.assertRaises(AlertError):
            alert._quota(api)
        api.remaining = 4500
        self.assertEqual(len(list(alert._pages(api, FACTORY))), 1)
        with self.assertRaises(AlertError):
            list(alert._pages(api, "pl0n3r/Condor", state="all"))
        for invalid in (None, {}, [None] * (alert.PAGE_SIZE + 1)):
            with patch.object(api, "get", return_value=invalid):
                with self.assertRaises(AlertError):
                    list(alert._pages(api, FACTORY))
        with patch.object(api, "get", return_value=[{}] * alert.PAGE_SIZE):
            with self.assertRaises(AlertError):
                list(alert._pages(api, FACTORY))
        for issues in (({"number": 2, "labels": [{"name": "estado: bloqueado"}]},) * 2,
                       ({"number": True, "labels": []},),
                       ({"number": 10, "labels": [{"name": "estado: sin-etiqueta"}]},),
                       ({"number": 10, "labels": [{"name": "estado: bloqueado"},
                                                  {"name": "estado: disponible"}]},)):
            api = FakeAPI()
            api.repos[FACTORY] = list(issues)
            self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
            self.assertFalse(api.writes)

    def test_switch_canonical_authority_rejects_duplicate_and_partial_markers(self):
        """El publicador falla cerrado ante markers ambiguos y origen falso."""
        valid = ('<!-- factory-unattended-kill-switch '
                 '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->')
        invalid_bodies = (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","state":"RUNNING","owner":"pl0n3r"} -->',
            valid + '\n<!-- factory-unattended-kill-switch broken-json -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":true,"state":"RUNNING","owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","owner":"pl0n3r"} -->',
        )
        for body in invalid_bodies:
            api = FakeAPI()
            original = api.get
            def forged(path):
                result = original(path)
                if path == "/repos/pl0n3r/Factory/issues/767":
                    return {**result, "body": body}
                return result
            with self.subTest(body=body[:90]), patch.object(api, "get", side_effect=forged):
                self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
            self.assertFalse(api.writes)
        for override in (
            {"url": "https://api.github.com/repos/pl0n3r/Factory/issues/768"},
            {"repository_url": "https://api.github.com/repos/pl0n3r/Condor"},
            {"user": {"login": "github-actions[bot]"}},
        ):
            api = FakeAPI()
            original = api.get
            def forged(path):
                result = original(path)
                if path == "/repos/pl0n3r/Factory/issues/767":
                    return {**result, **override}
                return result
            with self.subTest(override=override), patch.object(api, "get", side_effect=forged):
                self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
            self.assertFalse(api.writes)

    def test_switch_duplicate_alert_and_recheck_fail_closed(self):
        api = FakeAPI()
        original_get = api.get
        def fake_kill(path):
            if path == "/repos/pl0n3r/Factory/issues/767":
                return {"number": 767, "state": "closed", "user": {"login": "pl0n3r"},
                        "body": "<!-- factory-unattended-kill-switch broken-json -->"}
            return original_get(path)
        with patch.object(api, "get", side_effect=fake_kill):
            self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)
        api = FakeAPI()
        result = ejecutar(api, enabled=True)
        self.assertEqual(result["status"], "CREATED")
        api.history[0]["body"] = "<!-- factory-queue-alert \nnot-a-marker"
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        api = FakeAPI()
        self.assertEqual(ejecutar(api, enabled=True)["status"], "CREATED")
        original_get = api.get
        def stale_get(path):
            value = original_get(path)
            if path == "/repos/pl0n3r/Factory/issues/20000":
                return {**value, "body": "changed by owner"}
            return value
        with patch.object(api, "get", side_effect=stale_get):
            api.history[0]["body"] = "<!-- factory-queue-alert " + json.dumps(
                {"fingerprint": "0" * 64, "version": 1},
                sort_keys=True, separators=(",", ":")) + " -->\nchanged"
            self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertEqual(len(api.writes), 1)


if __name__ == "__main__":
    unittest.main()
