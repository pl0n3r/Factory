#!/usr/bin/env python3
"""Factory#1848: functional evidence for Sonar CE and unattended handoff.

The executable A subset calls production modules with synthetic input. The
remaining B/C/D requirements are individually classified without equating
historical claims, a rendered UI or a missing scheduler with local coverage.
The coverage matrix is deliberately never read by this test.
"""
from __future__ import annotations

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
import urllib.request

from quality.sonar import normalize_sonar_snapshot
from scripts.unattended_cycle_handoff import project_unattended_cycle_handoff
from scripts import unattended_handoff_conformance_cli as conformance


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "unattended_handoff_v1"

A = frozenset({
    "docs/sonar-superseded-ce.md:L9-U1",
    "docs/unattended-handoff-consumer-pack.md:L10-U1",
    "docs/unattended-handoff-consumer-pack.md:L11-U1",
    "docs/unattended-handoff-consumer-pack.md:L12-U1",
    "docs/unattended-handoff-consumer-pack.md:L13-U1",
    "docs/unattended-handoff-consumer-pack.md:L19-U1",
    "docs/unattended-handoff-consumer-pack.md:L29-U1",
    "docs/unattended-handoff-consumer-pack.md:L30-U1",
})
B = {
    "docs/tanda1-handoff.md:L13-U1": "GitHub App cross-repo: requires live installation/permissions evidence",
    "docs/tanda1-handoff.md:L25-U1": "historical Issues 1-14: requires authenticated closed-state and timeline receipts",
    "docs/tanda1-handoff.md:L26-U1": "privacy #54: requires three-product and auditor receipts",
    "docs/tanda1-handoff.md:L27-U1": "v1 trust root #83: requires release-channel provenance",
    "docs/tanda1-handoff.md:L28-U1": "v1.0.0: requires release and consumer self-test evidence",
    "docs/tanda1-handoff.md:L29-U1": "global TANDA 1 completed: requires historical cross-repo receipts",
    "docs/tanda1-handoff.md:L35-U1": "published @v1 identity: requires live tag and release-gate verification",
    "docs/tanda1-handoff.md:L9-U1": "human gate and mobile receipt: requires real owner/consumer evidence",
}
C = {
    "docs/tanda1-handoff.md:L9-U2": "human decisions cannot be inferred from CI; governance policy",
    "docs/tanda1-handoff.md:L33-U1": "preserve historical closing text; editorial policy",
    "docs/unattended-handoff-consumer-pack.md:L33-U1": "consumer must not recalculate priority from display fields; external consumer policy",
}
D = {
    "docs/unattended-daily-summary.md:B04": "08:00 Bogota delivery job/cron retired; offline renderer cannot deliver it",
}
IDS = A | frozenset(B) | frozenset(C) | frozenset(D)

EXPECTED_PERMISSIONS = {
    "reserve": False,
    "merge": False,
    "deploy": False,
    "spend": False,
    "live": False,
}


def _fixture(name: str) -> dict[str, object]:
    with (FIXTURES / (name + ".json")).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError("canonical fixture must be an object")
    return value


def _cycle(action: str, *, freshness: str = "fresh") -> dict[str, object]:
    selected = "Factory#synthetic" if action == "ALLOW" else None
    provenance = {
        "head_sha": "a" * 40,
        "dispatch_ref": "test:synthetic",
        "guard_ref": "b" * 64,
        "watchdog_ref": "c" * 64,
        "freshness": freshness,
    }
    return {
        "version": 1,
        "action": action,
        "authority": "unchanged",
        "selected": selected,
        "selected_class": "medium" if selected else None,
        "freshness": freshness,
        "reasons": () if action == "ALLOW" else ("synthetic_guard",),
        "provenance": None if freshness == "unknown" else provenance,
        "components": {},
    }


NOW = "2026-10-06T00:10:00Z"
OLD_SHA = "f582680fd50436405329fc8cfd697167004fac32"
NEW_SHA = "c5e09d6f4e9982fd9b6d52d7043fd6c226453401"
SUPERSEDED = (
    f"Report for commit '{OLD_SHA}' can’t be processed: "
    "a newer report has already been processed, and processing older reports is not supported. "
    f"The last processed report was for commit '{NEW_SHA}'."
)


def contract(project="condor"):
    return {
        "version": 1,
        "project": project,
        "surfaces": [
            {
                "id": "admin",
                "criticality": "critical",
                "required_gates": ["unit"],
            }
        ],
        "invariants": ["authorization"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": [],
            "devices": [],
        },
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": False, "source_ref": None},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {"required": False, "source_ref": None},
            "recovery": {"required": False, "source_ref": None},
        },
        "sonar": {
            "expected_visibility": "public",
            "analysis_method": "ci",
            "max_analysis_age_seconds": 86400,
            "max_organization_line_usage_percent": 80,
            "max_open_vulnerabilities": 0,
            "max_open_bugs": 0,
            "max_open_hotspots": 0,
            "max_debt_age_days": 30,
        },
    }


def snapshot(project="condor"):
    return {
        "project": project,
        "snapshot_at": "2026-10-06T00:06:12Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {
            "analyzed_at": "2026-10-06T00:05:00Z",
            "method": "ci",
            "coverage_available": True,
        },
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50},
        "visibility": "public",
        "debt": [],
        "evidence_refs": ["sonar:condor:snapshot:20261006T000612Z"],
    }


def ce_signal(raw):
    normalized = normalize_sonar_snapshot(contract(raw["project"]), raw, observed_at=NOW)
    return next(item for item in normalized["signals"] if item["signal"] == "ce_task")


class CoberturaFactory57Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        self.assertEqual(len(IDS), 20)
        self.assertEqual((len(A), len(B), len(C), len(D)), (8, 8, 3, 1))

                raw = snapshot()
        raw["ce_task"] = {"status": "FAILED", "error_message": SUPERSEDED}
        signal = ce_signal(raw)  # quality.sonar real
        self.assertEqual(signal["status"], "PASS")
        self.assertEqual(signal["reason"], "ce_task_superseded_by_newer_report")
        self.assertEqual(signal["freshness"]["state"], "CURRENT")
        for sha in (OLD_SHA, NEW_SHA):
            self.assertEqual(len(sha), 40)
            self.assertIn(sha, signal["details"]["error_message"])

        expected = {
            "allow": ("ALLOW", "fresh"),
            "pause": ("PAUSE", "fresh"),
            "blocked": ("BLOCKED", "fresh"),
            "unknown": ("BLOCKED", "unknown"),
        }
        for name, (action, freshness) in expected.items():
            with self.subTest(fixture=name):
                document = _fixture(name)
                self.assertEqual(
                    conformance.evaluate_document(document),
                    {"version": 1, "conformant": True, "code": "conformant"},
                )
                self.assertEqual(document["action"], action)
                self.assertEqual(document["next_transition"], action)
                self.assertEqual(document["freshness"], freshness)
                self.assertEqual(document["authority"], "unchanged")
                self.assertEqual(document["permissions"], EXPECTED_PERMISSIONS)

        # Execute the actual cycle handoff projector, not a test-only
        # "consumer" reimplementation or text search against documentation.
        for action, freshness in (
            ("ALLOW", "fresh"),
            ("PAUSE", "fresh"),
            ("BLOCKED", "unknown"),
        ):
            with self.subTest(projection=action):
                cycle = _cycle(action, freshness=freshness)
                projected = project_unattended_cycle_handoff(cycle)
                self.assertEqual(projected["action"], action)
                self.assertEqual(projected["next_transition"], action)
                self.assertEqual(projected["freshness"], freshness)
                self.assertEqual(projected["authority"], "unchanged")
                self.assertEqual(projected["permissions"], EXPECTED_PERMISSIONS)
                self.assertEqual(projected["reasons"], cycle["reasons"])
                self.assertEqual(projected["provenance"], cycle["provenance"])
                verdict = conformance.evaluate_document(json.loads(json.dumps(projected)))
                self.assertTrue(verdict["conformant"])
                if freshness == "unknown":
                    self.assertEqual(projected["action"], "BLOCKED")
                    self.assertNotEqual(projected["action"], "ALLOW")

    def test_falla_cerrado(self) -> None:
                raw = snapshot()
        raw["ce_task"] = {
            "status": "FAILED",
            "error_message": SUPERSEDED.replace(
                OLD_SHA, OLD_SHA[:-1]
            ),
        }
        signal = ce_signal(raw)
        self.assertEqual((signal["status"], signal["reason"]),
                         ("FAIL", "ce_task_failed"))

        for key, replacement in (
            ("version", 2),
            ("action", "UNKNOWN"),
            ("freshness", "unknown"),
            ("permissions", {**EXPECTED_PERMISSIONS, "merge": True}),
            ("unexpected", "no authority"),
        ):
            with self.subTest(invalid=key):
                bad = deepcopy(_fixture("allow"))
                bad[key] = replacement
                self.assertFalse(conformance.evaluate_document(bad)["conformant"])

        for mutation in (
            {"action": "UNKNOWN"},
            {"authority": "elevated"},
            {"surprise": True},
            {"selected": 42},
        ):
            with self.subTest(projector=mutation):
                bad = _cycle("ALLOW")
                bad.update(mutation)
                result = project_unattended_cycle_handoff(bad)
                self.assertEqual(result["action"], "BLOCKED")
                self.assertEqual(result["permissions"], EXPECTED_PERMISSIONS)

        stdout = StringIO()
        code = conformance.main(
            ['{"version":1,"version":1}'], stdin=StringIO(""), stdout=stdout
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["code"], "duplicate_json_key")

    def test_sin_datos_reales(self) -> None:
        fake_secret = "synthetic-private-value-never-log"
        bad = _fixture("allow")
        bad["token"] = fake_secret
        with (
            patch.object(socket, "create_connection",
                         side_effect=AssertionError("network forbidden")),
            patch.object(urllib.request, "urlopen",
                         side_effect=AssertionError("network forbidden")),
            patch.object(subprocess, "run",
                         side_effect=AssertionError("subprocess forbidden")),
        ):
            self.assertEqual(
                project_unattended_cycle_handoff(_cycle("BLOCKED", freshness="unknown"))["action"],
                "BLOCKED",
            )
            self.assertTrue(conformance.evaluate_document(_fixture("allow"))["conformant"])
            output = StringIO()
            exit_code = conformance.main(
                [json.dumps(bad)], stdin=StringIO(""), stdout=output
            )
            self.assertEqual(exit_code, 2)
            self.assertFalse(json.loads(output.getvalue())["conformant"])
            self.assertNotIn(fake_secret, output.getvalue())
            self.assertNotIn("token", output.getvalue())

        # The fixture and source paths are local test artifacts; no live,
        # credentials, customer data, or server sessions are consulted.
        self.assertTrue(all(path.startswith("docs/") for path in IDS))
        self.assertEqual(len(IDS), 20)


if __name__ == "__main__":
    unittest.main()
