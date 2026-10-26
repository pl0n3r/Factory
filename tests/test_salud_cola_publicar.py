"""Regresiones de la puerta Factory #1523/A: propuesta de cola sin publicación."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from scripts.salud_cola import REPOSITORIES
from scripts.salud_cola_publicar import _read_local_observation, preparar_publicacion

ROOT = Path(__file__).resolve().parents[1]


def complete_snapshot():
    rows = []
    for name in REPOSITORIES:
        rows.append({
            "name": name, "complete": True, "open_issues": 1,
            "counts": {"available": 0, "reserved": 0, "blocked": 1,
                       "planned": 0, "in_review": 0, "recovery_required": 0},
            "blockers": [{"number": 17, "cause": "dependency", "roadmap": True}],
        })
    return {"version": 1, "repositories": rows, "agent_capacity": 4,
            "rate_limit": {"limit": 5000, "remaining": 4000}}


def canonical_source():
    return {"authenticated": True, "repository_scope": list(REPOSITORIES),
            "identities_verified": True, "pagination_complete": True,
            "checks_complete": True}


class SaludColaPublicarTests(unittest.TestCase):
    def test_complete_canonical_inventory_generates_only_dry_run(self):
        result = preparar_publicacion(complete_snapshot(), canonical_source())
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(result["action"], "create_candidate")
        self.assertEqual(result["proposal"]["open_total"], 7)
        self.assertEqual(result["proposal"]["candidate_count"], 7)
        self.assertEqual(result["proposal"]["state"], "queue_empty")
        self.assertRegex(result["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertFalse(result["publish_allowed"])
        self.assertEqual(result["writes"], 0)
        self.assertNotIn("token", json.dumps(result))

    def test_unknown_low_quota_and_partial_inventory_fail_closed(self):
        raw = complete_snapshot()
        invalid = copy.deepcopy(raw)
        invalid["repositories"].pop()
        other = copy.deepcopy(raw)
        other["rate_limit"]["remaining"] = 999
        unknown = copy.deepcopy(raw)
        unknown["repositories"][0]["complete"] = False
        bad_source = canonical_source()
        bad_source.pop("checks_complete")
        not_paged = canonical_source()
        not_paged["pagination_complete"] = False
        cases = ((invalid, canonical_source(), "invalid_or_incomplete_inventory"),
                 (unknown, canonical_source(), "invalid_or_incomplete_inventory"),
                 (other, canonical_source(), "low_quota"),
                 (raw, bad_source, "unverified_provenance"),
                 (raw, not_paged, "unverified_provenance"),
                 (raw, {}, "unverified_provenance"))
        for sample, provenance, reason in cases:
            with self.subTest(reason=reason):
                out = preparar_publicacion(sample, provenance)
                self.assertEqual(out["status"], "SKIPPED")
                self.assertEqual(out["reason"], reason)
                self.assertFalse(out["publish_allowed"])
                self.assertEqual(out["writes"], 0)
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "local.json"
            p.write_text(json.dumps({"status": "OBSERVED_LOCAL_ONLY",
                                     "scope": "pl0n3r/Factory", "writes": 0}))
            self.assertEqual(_read_local_observation(str(p))["reason"],
                             "local_observation_not_global_proof")
            p.write_text(json.dumps({"status": "DEFERRED_LOW_QUOTA",
                                     "scope": "pl0n3r/Factory", "writes": 0}))
            self.assertEqual(_read_local_observation(str(p))["reason"], "low_quota")

    def test_repeated_fingerprint_is_idempotent_without_duplicate_issues(self):
        first = preparar_publicacion(complete_snapshot(), canonical_source())
        second = preparar_publicacion(complete_snapshot(), canonical_source(),
                                     first["fingerprint"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(second["action"], "noop")
        self.assertEqual(second["writes"], 0)
        self.assertFalse(second["publish_allowed"])
        self.assertEqual(preparar_publicacion(complete_snapshot(), canonical_source(),
                           "unexpected")["status"], "SKIPPED")
        report = str(first) + str(second)
        self.assertNotIn("POST", report)
        self.assertNotIn("PATCH", report)

    def test_workflow_preserves_read_only_permissions_and_zero_mutations(self):
        workflow = (ROOT / ".github/workflows/salud-cola.yml").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts/salud_cola_publicar.py").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("issues: read"), 2)
        self.assertEqual(workflow.count("contents: read"), 2)
        for forbidden in ("issues: write", "pull-requests: write", "secrets.",
                          'method="POST"', 'method="PATCH"'):
            self.assertNotIn(forbidden, workflow + publisher)
        self.assertEqual(workflow.count("cron:"), 1)
        self.assertIn("salud_cola_observar.py", workflow)
        self.assertIn("python3 -m scripts.salud_cola_publicar --observacion", workflow)
        self.assertNotIn("from urllib", publisher)
        self.assertNotIn("import requests", publisher)
        # La invocación -m conserva una prueba real de import-safe bajo cron;
        # no modifica la allowlist de entrypoints directos históricos.
        with tempfile.TemporaryDirectory() as dirname:
            observation = Path(dirname) / "report.json"
            observation.write_text(
                json.dumps({"status": "OBSERVED_LOCAL_ONLY",
                            "scope": "pl0n3r/Factory", "writes": 0}),
                encoding="utf-8",
            )
            environment = os.environ.copy()
            for key in ("PYTHONPATH", "GH_TOKEN", "GITHUB_TOKEN",
                        "SONAR_TOKEN", "GITHUB_STEP_SUMMARY"):
                environment.pop(key, None)
            result = subprocess.run(
                [sys.executable, "-m", "scripts.salud_cola_publicar",
                 "--observacion", str(observation)],
                cwd=ROOT, env=environment, text=True,
                capture_output=True, timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
