"""Fail-closed tests for the read-only post #2075 policy candidate preflight."""
from __future__ import annotations

import base64
import copy
import json
import unittest
from unittest.mock import patch

from scripts.release_auto_candidate_preflight import (
    TRUSTED_APPS, _get, collect_inventory, evaluate_inventory,
)

SHA = "a" * 40
V1 = "b" * 40


def example():
    checks = {name: {"authenticated": True, "head_sha": SHA, "status": "completed",
                     "conclusion": "success", "app": {"slug": app[0], "id": app[1]}}
              for name, app in TRUSTED_APPS.items()}
    return {
        "checkout_sha": SHA, "phase": "construccion",
        "main": {"name": "main", "protected": True, "commit": {"sha": SHA}},
        "tag": {"ref": "refs/tags/v1", "object": {"type": "commit", "sha": V1}},
        "switch": {"number": 767, "state": "closed", "user": {"login": "pl0n3r"},
                   "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'},
        "freeze": {"number": 921, "state": "closed"},
        "release_gates": [], "rate": {"resources": {"core": {"limit": 5000, "remaining": 2100}}},
        "candidate_version": "1.0.51", "published_version": "1.0.50",
        "compare": {"status": "ahead", "ahead_by": 1, "behind_by": 0,
                    "files": [{"filename": "docs/candidate-note.md"}]},
        "ruleset": {"id": 23958613, "target": "tag", "enforcement": "active"},
        "checks": checks,
        "consumer_compatibility": {"authenticated": True, "head_sha": SHA,
                                   "status": "completed", "conclusion": "success"},
        "watchdog": {"authenticated": True, "head_sha": SHA,
                     "status": "completed", "conclusion": "success"},
    }


class ReleaseAutoCandidatePreflightTests(unittest.TestCase):
    def assertBlocked(self, case, reason=None):
        result = evaluate_inventory(case)
        self.assertEqual("BLOCKED", result["state"], result)
        if reason is not None:
            self.assertEqual(reason, result["reason"])
        self.assertFalse(result["authorizes_release"])
        self.assertEqual(0, result["mutations"])
        self.assertEqual(0, result["tag_writes"])

    def test_rechaza_evidencia_incompleta_y_sha_invalido(self):
        for value in (None, [], {}, {**example(), "unknown": 42},
                      {**example(), "checkout_sha": "wrong"},
                      {**example(), "main": {"name": "main", "protected": False, "commit": {"sha": SHA}}},
                      {**example(), "main": {"name": "main", "protected": True, "commit": {"sha": V1}}},
                      {**example(), "tag": {"ref": "refs/tags/v1", "object": {"type": "tag", "sha": V1}}},
                      {**example(), "ruleset": {"id": 23958613, "target": "tag", "enforcement": "disabled"}}):
            with self.subTest(value=str(value)[:40]):
                self.assertBlocked(value)
        self.assertEqual("REVIEW_ONLY", evaluate_inventory(example())["state"])

    def test_bloquea_fase_live_y_maquinaria_release(self):
        for key, value in (
            ("phase", "live"), ("phase", None),
            ("compare", {**example()["compare"], "files": [{"filename": "seguridad/puertas_humanas.py"}]}),
            ("compare", {**example()["compare"], "files": [{"filename": ".github/workflows/release-auto.yml"}]}),
            ("compare", {**example()["compare"], "status": "diverged", "behind_by": 1}),
            ("candidate_version", "1.0.50"), ("candidate_version", "2.0.0"),
            ("freeze", {"number": 921, "state": "open"}),
            ("release_gates", [{"number": 999}]),
            ("switch", {**example()["switch"], "body": ''}),
            ("switch", {**example()["switch"], "body": example()["switch"]["body"] * 2}),
        ):
            with self.subTest(key=key):
                case = example()
                case[key] = value
                self.assertBlocked(case)

    def test_cuota_gates_y_consultas_autenticadas(self):
        for key, value in (
            ("rate", {"resources": {"core": {"remaining": 999, "limit": 5000}}}),
            ("checks", {**example()["checks"], "CodeQL": {**example()["checks"]["CodeQL"], "conclusion": "failure"}}),
            ("checks", {**example()["checks"], "Validar": {**example()["checks"]["Validar"], "head_sha": V1}}),
            ("checks", {**example()["checks"], "SonarCloud Code Analysis": {**example()["checks"]["SonarCloud Code Analysis"], "app": {"slug": "unknown", "id": 3}}}),
            ("consumer_compatibility", None), ("watchdog", None),
        ):
            with self.subTest(key=key):
                case = example()
                case[key] = value
                self.assertBlocked(case)

        root = "/repos/pl0n3r/Factory"
        fixture = example()
        def b64(v):
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(json.dumps({"version": v}).encode()).decode() + "\n"}
        def get(path):
            # Every requested path is caller-constructed, deterministic and GET-only.
            visited.append(path)
            if path == "/rate_limit": return fixture["rate"]
            if path.endswith("/branches/main"): return fixture["main"]
            if path.endswith("/git/ref/tags/v1"): return fixture["tag"]
            if path.endswith("/issues/767"): return fixture["switch"]
            if path.endswith("/issues/921"): return fixture["freeze"]
            if "issues?state=open" in path: return fixture["release_gates"]
            if path.endswith("/rulesets/23958613"): return fixture["ruleset"]
            if path.endswith("/contents/config/version.json?ref=" + SHA): return b64("1.0.51")
            if path.endswith("/contents/config/version.json?ref=v1"): return b64("1.0.50")
            if path.endswith("/compare/v1..." + SHA): return fixture["compare"]
            if "check_name=" in path:
                from urllib.parse import unquote
                name = unquote(path.split("check_name=")[1])
                row = fixture["checks"][name]
                return {"total_count": 1, "check_runs": [{"name": name, "id": 5,
                        "head_sha": row["head_sha"], "status": row["status"],
                        "conclusion": row["conclusion"], "app": row["app"]}]}
            raise AssertionError(path)
        visited = []
        result = collect_inventory(SHA, "construccion", get=get)
        self.assertEqual("BLOCKED", result["state"])
        self.assertEqual("consumer_compatibility_not_independently_attested", result["reason"])
        self.assertEqual(13, len(visited))
        self.assertEqual(len(visited), len(set(visited)))
        self.assertTrue(all(p == "/rate_limit" or p.startswith(root + "/") for p in visited))

    def test_solo_get_sin_autoridad_de_publicacion(self):
        case = example()
        before = copy.deepcopy(case)
        expected = evaluate_inventory(case)
        self.assertEqual("REVIEW_ONLY", expected["state"])
        self.assertEqual(case, before)
        for _ in range(7): self.assertEqual(expected, evaluate_inventory(case))
        for value in (case, {}, None):
            row = evaluate_inventory(value)
            self.assertFalse(row["authorizes_release"])
            self.assertEqual(0, row["mutations"])
            self.assertEqual(0, row["tag_writes"])
            self.assertEqual(0, row["release_writes"])
        with patch("scripts.release_auto_candidate_preflight.subprocess.run") as run:
            run.return_value.stdout = '{}'
            self.assertEqual({}, _get("/repos/pl0n3r/Factory/issues/767"))
            args = run.call_args.args[0]
            self.assertEqual(["gh", "api", "-X", "GET"], args[:4])
            self.assertEqual("/repos/pl0n3r/Factory/issues/767", args[4])
            self.assertFalse(any(s in args for s in ("POST", "PATCH", "DELETE", "PUT")))
        result = collect_inventory("bad", "construccion", get=lambda _: self.fail("should not fetch"))
        self.assertEqual("sha_invalid", result["reason"])


if __name__ == "__main__":
    unittest.main()
