"""Regresiones reales del contrato Sonar y portada README, Factory #1837.

Sin red ni datos reales. La fuente pública de /health requiere prueba de entorno
separada (B03): validar URLs en un README no demuestra que el servicio existe.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

from quality.sonar import (
    FACTORY_PROJECTS,
    SonarEvidenceError,
    normalize_sonar_snapshot,
)
from readme.validate_readme import validate_readme


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_factory46_sonar_fixtures", ROOT / "tests" / "test_quality_sonar.py"
)
assert SPEC is not None and SPEC.loader is not None
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)
NOW = fixtures.NOW
SONAR = "docs/quality-sonar.md:"
OFFLINE = frozenset(SONAR + key for key in (
    "L11-U1", "L12-U1", "L13-U1", "L15-U1", "L21-U1",
    "L22-U1", "L24-U1", "L25-U1", "L26-U1", "L28-U1",
    "L32-U1", "L32-U2", "L32-U3", "L34-U1", "L34-U2",
    "L5-U1", "L7-U1", "L8-U1", "L9-U1",
))


def signal(output, name):
    return next(item for item in output["signals"] if item["signal"] == name)


def normalize(raw=None, contract=None):
    return normalize_sonar_snapshot(
        fixtures.contract() if contract is None else contract,
        fixtures.snapshot() if raw is None else raw,
        observed_at=NOW,
    )


def applicability(*, method="ci", visibility="public"):
    contract = fixtures.contract()
    contract["sonar"].update({
        "analysis_method": method,
        "expected_visibility": visibility,
        "applicability": {
            "coverage": {
                "state": "not_applicable" if method == "automatic" else "required",
                "reason": (
                    "coverage_not_applicable_automatic_analysis"
                    if method == "automatic" else "coverage_required_ci_analysis"
                ),
                "source_ref": "pl0n3r/Factory#516",
            },
            "organization_line_usage": {
                "state": "not_applicable" if visibility == "public" else "required",
                "reason": (
                    "organization_line_usage_not_applicable_public"
                    if visibility == "public" else "organization_line_usage_required_private"
                ),
                "source_ref": "pl0n3r/Factory#516",
            },
        },
    })
    return contract


class CoberturaFactory46Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada fila Sonar offline invoca el normalizador real."""
        done = set()
        self.assertEqual(len(OFFLINE), 19)
        base = normalize()
        self.assertEqual(base["project"], "factory")
        self.assertEqual(base["authority"], "read_only")
        self.assertFalse(base["execute_actions"])
        self.assertEqual(base["observed_at"], NOW)
        self.assertEqual(len(base["signals"]), 8)
        done.add(SONAR + "L5-U1")

        self.assertEqual(tuple(sorted(FACTORY_PROJECTS)), FACTORY_PROJECTS)
        for project in FACTORY_PROJECTS:
            with self.subTest(project=project):
                result = normalize_sonar_snapshot(
                    fixtures.contract(project), fixtures.snapshot(project),
                    observed_at=NOW,
                )
                self.assertEqual(result["project"], project)
        done.add(SONAR + "L7-U1")

        self.assertEqual(base["snapshot_freshness"]["state"], "CURRENT")
        self.assertEqual(
            signal(base, "quality_gate")["evidence_refs"],
            ["sonar:factory:snapshot:001"],
        )
        done.add(SONAR + "L8-U1")
        self.assertEqual(signal(base, "quality_gate")["status"], "PASS")
        failed_gate = fixtures.snapshot()
        failed_gate["quality_gate"] = {
            "status": "ERROR",
            "conditions": [{
                "metric": "new_reliability_rating", "status": "ERROR",
                "actual": "3", "threshold": "1",
            }],
        }
        failure = signal(normalize(failed_gate), "quality_gate")
        self.assertEqual(failure["status"], "FAIL")
        self.assertEqual(failure["reason"], "quality_gate_failed")
        self.assertEqual(
            failure["details"]["failed_conditions"][0]["metric"],
            "new_reliability_rating",
        )
        done.add(SONAR + "L9-U1")
        done.add(SONAR + "L21-U1")

        failed_ce = fixtures.snapshot()
        failed_ce["ce_task"] = {
            "status": "FAILED",
            "error_message": (
                "Analysis failed; see https://example.invalid/report "
                "token=synthetic-secret-placeholder"
            ),
        }
        ce = signal(normalize(failed_ce), "ce_task")
        self.assertEqual((ce["status"], ce["reason"]), ("FAIL", "ce_task_failed"))
        self.assertIn("[url removed]", ce["details"]["error_message"])
        self.assertIn("[sensitive removed]", ce["details"]["error_message"])
        self.assertNotIn("synthetic-secret-placeholder", ce["details"]["error_message"])
        done.add(SONAR + "L11-U1")

        missing = fixtures.snapshot()
        for key in ("quality_gate", "analysis", "ce_task", "organization", "visibility"):
            missing[key] = None
        signals = normalize(missing)
        for name in (
            "quality_gate", "analysis_freshness", "ce_task", "organization_line_usage",
            "visibility", "analysis_method", "coverage",
        ):
            self.assertEqual(signal(signals, name)["status"], "UNKNOWN")
        self.assertEqual(signal(signals, "quality_gate")["reason"], "quality_gate_missing")
        done.add(SONAR + "L13-U1")
        done.add(SONAR + "L15-U1")

        aged = fixtures.snapshot()
        aged["analysis"]["analyzed_at"] = "2026-09-27T11:50:00Z"
        fresh = signal(normalize(aged), "analysis_freshness")
        self.assertEqual(fresh["status"], "STALE")
        self.assertEqual(fresh["freshness"]["state"], "STALE")
        done.add(SONAR + "L22-U1")

        exceeding = fixtures.snapshot()
        exceeding["organization"] = {"line_usage_percent": 81}
        exceeding["visibility"] = "private"
        exceeding["analysis"]["method"] = "automatic"
        classified = normalize(exceeding)
        self.assertEqual(signal(classified, "organization_line_usage")["status"], "FAIL")
        self.assertEqual(
            signal(classified, "organization_line_usage")["details"]["max_percent"], 80
        )
        done.add(SONAR + "L12-U1")
        done.add(SONAR + "L24-U1")
        self.assertEqual(signal(classified, "visibility")["status"], "FAIL")
        self.assertEqual(signal(classified, "visibility")["details"]["expected"], "public")
        done.add(SONAR + "L25-U1")
        self.assertEqual(signal(classified, "analysis_method")["status"], "FAIL")
        self.assertEqual(signal(classified, "analysis_method")["details"]["actual"], "automatic")
        done.add(SONAR + "L26-U1")

        no_coverage = fixtures.snapshot()
        no_coverage["analysis"]["coverage_available"] = False
        coverage = signal(normalize(no_coverage), "coverage")
        self.assertEqual((coverage["status"], coverage["reason"]), (
            "FAIL", "coverage_missing_for_ci"
        ))
        done.add(SONAR + "L32-U1")

        automatic = fixtures.snapshot()
        automatic["analysis"].update({"method": "automatic", "coverage_available": False})
        automatic["organization"] = None
        output = normalize(automatic, applicability(method="automatic"))
        self.assertEqual(signal(output, "coverage")["status"], "NOT_APPLICABLE")
        self.assertNotEqual(signal(output, "coverage")["status"], "PASS")
        self.assertEqual(
            signal(output, "coverage")["details"]["source_ref"],
            "pl0n3r/Factory#516",
        )
        done.add(SONAR + "L32-U2")
        self.assertEqual(signal(output, "organization_line_usage")["status"], "NOT_APPLICABLE")
        private = fixtures.snapshot()
        private["visibility"] = "private"
        private["organization"] = None
        private_output = normalize(private, applicability(visibility="private"))
        self.assertEqual(
            signal(private_output, "organization_line_usage")["status"], "UNKNOWN"
        )
        done.add(SONAR + "L32-U3")

        debt = fixtures.snapshot()
        debt["debt"] = [{
            "type": "vulnerability", "severity": "CRITICAL",
            "opened_at": "2026-08-30T12:00:00Z",
            "evidence_ref": "sonar:factory:vulnerability:example",
        }]
        debt_signal = signal(normalize(debt), "historical_debt")
        self.assertEqual(debt_signal["status"], "FAIL")
        self.assertEqual(debt_signal["details"]["counts"][0]["count"], 1)
        self.assertIn("vulnerability:1>0", debt_signal["details"]["exceeded"])
        done.add(SONAR + "L28-U1")

        many = fixtures.snapshot()
        many["debt"] = [{
            "type": "bug", "severity": "MAJOR",
            "opened_at": "2026-09-29T12:00:00Z",
            "evidence_ref": f"sonar:factory:bug:{i}",
        } for i in range(34)]
        grouped = signal(normalize(many), "historical_debt")
        self.assertEqual(grouped["details"]["counts"][0]["count"], 34)
        self.assertEqual(grouped["status"], "FAIL")
        self.assertNotIn("sonar:factory:bug:0", grouped["evidence_refs"])
        done.add(SONAR + "L34-U1")
        self.assertEqual(grouped["evidence_refs"], ["sonar:factory:snapshot:001"])
        done.add(SONAR + "L34-U2")
        self.assertEqual(done, OFFLINE)

    def test_falla_cerrado(self):
        """AC-02: no admitir campos ausentes, referencias sensibles o ambigüedad."""
        cases = []
        for field in (
            "project", "snapshot_at", "quality_gate", "analysis", "ce_task",
            "organization", "visibility", "debt", "evidence_refs",
        ):
            raw = fixtures.snapshot()
            del raw[field]
            cases.append((f"missing_{field}", raw, fixtures.contract()))

        missing_zone = fixtures.snapshot()
        missing_zone["snapshot_at"] = "2026-09-30T11:55:00"
        cases.append(("missing_timezone", missing_zone, fixtures.contract()))
        future = fixtures.snapshot()
        future["snapshot_at"] = "2999-01-01T00:00:00Z"
        cases.append(("future_snapshot", future, fixtures.contract()))
        url_ref = fixtures.snapshot()
        url_ref["evidence_refs"] = ["https://example.invalid/synthetic"]
        cases.append(("url_ref", url_ref, fixtures.contract()))
        duplicate_refs = fixtures.snapshot()
        duplicate_refs["evidence_refs"] *= 2
        cases.append(("duplicate_refs", duplicate_refs, fixtures.contract()))
        bad_project = fixtures.snapshot()
        bad_project["project"] = "not-a-factory-project"
        cases.append(("unknown_project", bad_project, fixtures.contract()))
        bad_ce = fixtures.snapshot()
        bad_ce["ce_task"] = {"status": "FAILED", "error_message": None}
        cases.append(("failed_ce_without_error", bad_ce, fixtures.contract()))
        bad_gate = fixtures.snapshot()
        bad_gate["quality_gate"] = {"status": "ERROR", "conditions": []}
        cases.append(("gate_without_condition", bad_gate, fixtures.contract()))
        bad_org = fixtures.snapshot()
        bad_org["organization"] = {"line_usage_percent": 101}
        cases.append(("organization_over_100", bad_org, fixtures.contract()))
        unknown_method = fixtures.snapshot()
        unknown_method["analysis"]["method"] = "guess"
        cases.append(("unknown_analysis_method", unknown_method, fixtures.contract()))
        bad_debt = fixtures.snapshot()
        bad_debt["debt"] = [{
            "type": "bug", "severity": "MAJOR", "opened_at": "2026-09-29T12:00:00Z",
            "evidence_ref": "https://example.invalid/issue",
        }]
        cases.append(("debt_item_url", bad_debt, fixtures.contract()))
        wrong_visibility = fixtures.snapshot()
        wrong_visibility["visibility"] = "internal"
        cases.append(("wrong_visibility", wrong_visibility, fixtures.contract()))
        extra = fixtures.snapshot()
        extra["unstated"] = "synthetic"
        cases.append(("extra_key", extra, fixtures.contract()))
        for name, raw, contract in cases:
            with self.subTest(name=name), self.assertRaises(SonarEvidenceError):
                normalize(raw, contract)

        # README contract v2 omits optional health when no authentic public source exists.
        readme_contract = __import__("json").loads(
            (ROOT / "readme" / "contract.json").read_text(encoding="utf-8")
        )
        readme = (
            "# Demo\n\n## Operational Cockpit\n"
            "[CI](https://github.com/pl0n3r/Factory/actions)\n"
            "[Release](https://github.com/pl0n3r/Factory/releases/latest)\n"
            "[Orquestador](https://control.condorapp.com.co/)\n"
        )
        metadata = {"name": "Factory", "phase": "construction"}
        validate_readme(readme, readme_contract, metadata, {}, None)
        forged = readme + "[Health](https://untrusted.example.invalid/health)\n"
        with self.assertRaises(ValueError):
            validate_readme(forged, readme_contract, metadata, {}, None)
        unsafe = copy.deepcopy(readme_contract)
        unsafe["live_status"]["allowed_hosts"] = []
        with self.assertRaises(ValueError):
            validate_readme(readme, unsafe, metadata, {}, None)

    def test_sin_datos_reales(self):
        """AC-03: pruebas deterministas y sin clientes, red ni secretos."""
        self.assertEqual(len(OFFLINE), 19)
        self.assertEqual(len(FACTORY_PROJECTS), 6)
        self.assertTrue((ROOT / "quality" / "sonar.py").is_file())
        self.assertTrue((ROOT / "readme" / "validate_readme.py").is_file())
        self.assertTrue((ROOT / "tests" / "test_quality_sonar.py").is_file())
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^\s*(?:from|import)\s+(?:requests|httpx|socket|subprocess)\b")
        self.assertNotIn("PRIVATE" + " KEY-----", own)
        self.assertNotIn("os." + "environ", own)
        self.assertNotIn("url" + "open(", own)
        # B03 is a real-world public endpoint proof, outside a no-network test.


if __name__ == "__main__":
    unittest.main()
