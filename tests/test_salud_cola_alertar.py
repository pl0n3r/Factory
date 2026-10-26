"""Aceptación #1539: aviso autorizado solo en Factory y evidencia completa."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

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
                return copy.deepcopy(self.history) if page == 1 else []
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
                   "labels": [{"name": "estado: bloqueado"}]}
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

    def test_read_only_default_and_explicit_factory_write_authority(self):
        api = FakeAPI()
        self.assertEqual(ejecutar(api)["reason"], "disabled_by_default")
        self.assertFalse(api.calls or api.writes)
        api.kill_state = "PAUSED"
        self.assertEqual(ejecutar(api, enabled=True)["status"], "SKIPPED")
        self.assertFalse(api.writes)
        for path in ("/repos/pl0n3r/Condor/issues",
                     "/repos/pl0n3r/ControlBot/issues/21"):
            with self.assertRaises(AlertError):
                GitHubAPI("fake").request("POST", path, {"body": "x"})
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


if __name__ == "__main__":
    unittest.main()
