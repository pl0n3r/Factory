"""Regresiones Factory #1523/A: simulación de aviso sin publicación."""
from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.salud_cola import REPOSITORIES
from scripts.salud_cola_publicar import (
    MAX_OBSERVATION_BYTES, _read_local_observation, main, preparar_publicacion,
)

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
        partial = copy.deepcopy(raw)
        partial["repositories"].pop()
        unknown = copy.deepcopy(raw)
        unknown["repositories"][0]["complete"] = False
        quota = copy.deepcopy(raw)
        quota["rate_limit"]["remaining"] = 999
        active = copy.deepcopy(raw)
        active["repositories"][0]["counts"].update(available=1, blocked=0)
        active["repositories"][0]["blockers"] = []
        bad_source = canonical_source()
        bad_source.pop("checks_complete")
        not_paged = canonical_source()
        not_paged["pagination_complete"] = False
        forged_source = canonical_source()
        forged_source["authenticated"] = 1
        malformed_scope = canonical_source()
        malformed_scope["repository_scope"] = list(reversed(REPOSITORIES))
        cases = (
            (partial, canonical_source(), "invalid_or_incomplete_inventory"),
            (unknown, canonical_source(), "invalid_or_incomplete_inventory"),
            (quota, canonical_source(), "low_quota"),
            (active, canonical_source(), "no_queue_empty_trigger"),
            (raw, bad_source, "unverified_provenance"),
            (raw, not_paged, "unverified_provenance"),
            (raw, forged_source, "unverified_provenance"),
            (raw, malformed_scope, "unverified_provenance"),
            (raw, {}, "unverified_provenance"),
        )
        for sample, provenance, reason in cases:
            with self.subTest(reason=reason):
                out = preparar_publicacion(sample, provenance)
                self.assertEqual(out["status"], "SKIPPED")
                self.assertEqual(out["reason"], reason)
                self.assertFalse(out["publish_allowed"])
                self.assertEqual(out["writes"], 0)
        with patch("scripts.salud_cola_publicar.diagnose_queue",
                   side_effect=TypeError("untrusted")):
            self.assertEqual(preparar_publicacion(raw, canonical_source())["reason"],
                             "invalid_or_incomplete_inventory")
        with patch("scripts.salud_cola_publicar.diagnose_queue",
                   return_value={"state": "queue_empty", "publication_allowed": True}):
            self.assertEqual(preparar_publicacion(raw, canonical_source())["reason"],
                             "unexpected_publish_authority")

        local = {"status": "OBSERVED_LOCAL_ONLY",
                 "scope": "pl0n3r/Factory", "writes": 0}
        self.assertEqual(_read_local_observation(json.dumps(local).encode())["reason"],
                         "local_observation_not_global_proof")
        local["status"] = "UNKNOWN"
        self.assertEqual(_read_local_observation(json.dumps(local).encode())["reason"],
                         "local_observation_not_global_proof")
        local["status"] = "DEFERRED_LOW_QUOTA"
        self.assertEqual(_read_local_observation(json.dumps(local).encode())["reason"],
                         "low_quota")
        local["status"] = "OBSERVED_LOCAL_ONLY"
        for input_data in (None, "", b"", b"\xff", b"invalid", b"[]",
                           b"x" * (MAX_OBSERVATION_BYTES + 1),
                           json.dumps({"status": "OBSERVED_LOCAL_ONLY",
                                       "scope": "different", "writes": 0}).encode(),
                           json.dumps({**local, "writes": True}).encode(),
                           json.dumps({**local, "writes": 1}).encode(),
                           json.dumps({**local, "status": "GREEN"}).encode()):
            with self.subTest(value=repr(input_data)[:60]):
                result = _read_local_observation(input_data)
                self.assertEqual(result["status"], "SKIPPED")
                self.assertFalse(result["publish_allowed"])
                self.assertEqual(result["writes"], 0)

    def test_repeated_fingerprint_is_idempotent_without_duplicate_issues(self):
        first = preparar_publicacion(complete_snapshot(), canonical_source())
        second = preparar_publicacion(complete_snapshot(), canonical_source(),
                                     first["fingerprint"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(second["action"], "noop")
        self.assertEqual(second["writes"], 0)
        self.assertFalse(second["publish_allowed"])
        modified = complete_snapshot()
        modified["repositories"][0]["blockers"][0]["cause"] = "claims"
        changed = preparar_publicacion(modified, canonical_source(),
                                       first["fingerprint"])
        self.assertEqual(changed["action"], "create_candidate")
        self.assertNotEqual(changed["fingerprint"], first["fingerprint"])
        for invalid in ("unexpected", "A" * 64, 4, False, [], {}):
            self.assertEqual(preparar_publicacion(
                complete_snapshot(), canonical_source(), invalid,
            )["reason"], "invalid_previous_fingerprint")
        self.assertNotIn("POST", str(first) + str(second))
        self.assertNotIn("PATCH", str(first) + str(second))

    def test_workflow_preserves_read_only_permissions_and_zero_mutations(self):
        workflow = (ROOT / ".github/workflows/salud-cola.yml").read_text(encoding="utf-8")
        publisher = (ROOT / "scripts/salud_cola_publicar.py").read_text(encoding="utf-8")
        # La aprobación #1532/A autoriza un job separado; el observador antiguo
        # y su simulador conservan exactamente los permisos GET-only originales.
        observer = workflow.split("\n  publicar:\n", 1)[0]
        self.assertEqual(observer.count("issues: read"), 2)
        self.assertEqual(observer.count("contents: read"), 2)
        for forbidden in ("issues: write", "pull-requests: write", "secrets.",
                          'method="POST"', 'method="PATCH"'):
            self.assertNotIn(forbidden, observer + publisher)
        self.assertEqual(workflow.count("cron:"), 1)
        self.assertIn(
            "python3 scripts/salud_cola_observar.py | python3 -m scripts.salud_cola_publicar",
            workflow,
        )
        self.assertNotIn("from pathlib import Path", publisher)
        self.assertNotIn("from urllib", publisher)
        self.assertNotIn("import requests", publisher)
        local = json.dumps({"status": "OBSERVED_LOCAL_ONLY",
                            "scope": "pl0n3r/Factory", "writes": 0})
        environment = os.environ.copy()
        for key in ("PYTHONPATH", "GH_TOKEN", "GITHUB_TOKEN",
                    "SONAR_TOKEN", "GITHUB_STEP_SUMMARY"):
            environment.pop(key, None)
        child = subprocess.run(
            [sys.executable, "-m", "scripts.salud_cola_publicar"],
            input=local, cwd=ROOT, env=environment, text=True,
            capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertNotIn("ModuleNotFoundError", child.stderr)
        self.assertEqual(json.loads(child.stdout)["reason"],
                         "local_observation_not_global_proof")

        output = io.StringIO()
        self.assertEqual(main([], stream=io.BytesIO(local.encode()), output=output), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "SKIPPED")
        for raw in (b"", b"invalid", b"\xff", b"[]" ,
                    b"x" * (MAX_OBSERVATION_BYTES + 1)):
            output = io.StringIO()
            self.assertEqual(main([], stream=io.BytesIO(raw), output=output), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "SKIPPED")

        class BrokenStream:
            def read(self, limit):
                raise OSError("unavailable")

        output = io.StringIO()
        self.assertEqual(main([], stream=BrokenStream(), output=output), 0)
        self.assertEqual(json.loads(output.getvalue())["reason"],
                         "observation_unreadable")
        help_out = io.StringIO()
        self.assertEqual(main(["--help"], output=help_out), 0)
        self.assertIn("stdin", publisher)
        self.assertIn("Uso:", help_out.getvalue())
        with patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(main(["--observacion", "/private"]), 2)


if __name__ == "__main__":
    unittest.main()
