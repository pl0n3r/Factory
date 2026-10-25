"""Pruebas puras del artefacto Fase A: sin red, sin liberaciones."""
import io
import json
from pathlib import Path
import stat
import unittest
import zipfile

from scripts.lease_phase_a_artifact_qa import (
    inspect_artifact, ArtifactQAError, main,
)


SHA = "a" * 40
META = {"id": 415, "repository": "pl0n3r/Factory", "head_sha": SHA,
        "event": "schedule", "status": "completed", "conclusion": "success"}
ROW = {"issue": 111, "state": "read_only", "action": "wait", "reason": "activity_window",
       "activity_age_minutes": 8, "activity_source": "issue_comment", "release_authorized": False,
       "lock_verified": False, "cas_verified": False, "mutations": 0}
MANIFEST = {"schema_version": 1, "repository": META["repository"], "head_sha": SHA,
            "run_id": "415", "status": "candidate_terminal", "terminal_certified": False,
            "release_authorized": False, "mutations": 0, "valid_observations": 1,
            "unknown_observations": 0, "issues": [ROW]}


def archive(data: bytes, *, name: str = "lease-audit-evidence.json", twice=False,
            symlink=False, compression=zipfile.ZIP_DEFLATED) -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as out:
        member = zipfile.ZipInfo(name)
        member.compress_type = compression
        member.external_attr = ((stat.S_IFLNK if symlink else stat.S_IFREG) | 0o644) << 16
        out.writestr(member, data)
        if twice:
            out.writestr(member, data)
    return memory.getvalue()


def payload(value=None) -> bytes:
    return json.dumps(MANIFEST if value is None else value, separators=(",", ":")).encode()


class LeasePhaseAArtifactQATests(unittest.TestCase):
    def test_valid_zip_exact_identity_is_candidate_only(self):
        data = payload()
        result = inspect_artifact(archive(data), META)
        self.assertEqual(result["status"], "MATCHED_CANDIDATE")
        self.assertEqual(result["valid_observations"], 1)
        self.assertEqual(result["hypothetical_releases"], 0)
        self.assertEqual(len(result["sha256_json"]), 64)
        for key in ("artifact_attested", "terminal_certified", "release_authorized"):
            self.assertIs(result[key], False)
        self.assertNotIn("qa_approved", result)

    def test_unsafe_zip_and_duplicate_json_fail_closed(self):
        invalid = [b"", b"notzip", archive(payload(), name="../lease-audit-evidence.json"),
                   archive(payload(), twice=True), archive(payload(), symlink=True),
                   archive(b"x" * 32000),
                   archive(b'{"schema_version":1,"schema_version":1}')]
        for blob in invalid:
            with self.subTest(n=len(blob)), self.assertRaises(ArtifactQAError):
                inspect_artifact(blob, META)

    def test_unknown_mismatch_sensitive_and_schema_fail_closed(self):
        replacements = [({**META, "head_sha": "b" * 40}, MANIFEST),
                        ({**META, "event": "workflow_dispatch"}, MANIFEST),
                        (META, {**MANIFEST, "status": "UNKNOWN"}),
                        (META, {**MANIFEST, "release_authorized": True}),
                        (META, {**MANIFEST, "terminal_certified": True}),
                        (META, {**MANIFEST, "unknown_observations": 1}),
                        (META, {**MANIFEST, "valid_observations": 2}),
                        (META, {**MANIFEST, "token": "not-exported"}),
                        (META, {**MANIFEST, "issues": [{**ROW, "action": "release", "reason": "activity_window"}]}),
                        (META, {**MANIFEST, "issues": [{**ROW, "api_key": "not-exported"}]}),
                        (META, {**MANIFEST, "issues": [{**ROW, "mutations": True}]})]
        for metadata, manifest in replacements:
            with self.subTest(type=str(manifest)[:80]), self.assertRaises(ArtifactQAError):
                inspect_artifact(archive(payload(manifest)), metadata)

    def test_documented_manual_attestation_and_no_network_or_release(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/lease_phase_a_artifact_qa.py").read_text()
        docs = (Path(__file__).resolve().parents[1] / "docs/lease-phase-a-artifact-qa.md").read_text()
        for forbidden in ("urllib", "requests", "subprocess", "gh api", "create_issue(", "release_lease("):
            self.assertNotIn(forbidden, source)
        for required in ("100 ciclos", "24 horas", "GitHub autenticado", "QA individual",
                         "artifact_attested", "No autoriza Fase B"):
            self.assertIn(required, docs)
        self.assertEqual(main(["--artifact", "/does-not-exist", "--run-metadata", "/does-not-exist"]), 2)


if __name__ == "__main__":
    unittest.main()
