"""Factory #1620: 16 contratos de cobertura, sin fingir pruebas de producción.

Una aserción offline nunca acredita Fase B, before/after operativo ni backup.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest

from performance.contract import (
    PerformanceContractError, validate_performance_contract,
)
from performance.detector import detect_performance
from performance.remediation import evaluate_before_after, plan_remediation
from performance.status import derive_performance_status, readiness_projection
from performance.triage import triage_performance
from recovery.contract import (
    RecoveryContractError, canonical_recovery_manifest,
    validate_recovery_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
IDS = (
    "ISSUE-1382:AC-05", "ISSUE-1382:AC-06", "ISSUE-1382:AC-07",
) + tuple(f"ISSUE-304:AC-{i:02}" for i in range(1, 13)) + (
    "ISSUE-305:AC-01",
)
UNKNOWN = "UNKNOWN"
# No se certifican observaciones, permisos, releases o backups reales.
OPERATIONAL_GAPS = {
    "ISSUE-1382:AC-05": "24h_100_terminal_cycles_per_repository_not_observed",
    "ISSUE-1382:AC-06": "phase_b_authority_and_qa_not_observed",
    "ISSUE-304:AC-02": "authenticated_baseline_regression_not_demonstrated",
    "ISSUE-1382:AC-07": "consumer_runtime_and_flag_not_observed",
    "ISSUE-304:AC-11": "live_before_after_e2e_not_observed",
    "ISSUE-305:AC-01": "restore_rpo_rto_not_observed",
}
NOW = "2026-09-28T20:06:00Z"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def rows(raw):
    if not isinstance(raw, str):
        raise ValueError("Matriz ilegible")
    found = {}
    for line in raw.splitlines():
        line = line.lstrip()
        if not line.startswith("|"):
            continue
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in found or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("Fila incompleta o duplicada: " + key)
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError("Promoción sin evidencia: " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("Matriz incompleta: faltan IDs")
    return found


def assess(matrix, checks):
    try:
        rows(matrix)
    except ValueError:
        return {u: UNKNOWN for u in IDS}
    if type(checks) is not dict or set(checks) != set(IDS):
        return {u: UNKNOWN for u in IDS}
    if any(type(v) is not bool for v in checks.values()):
        return {u: UNKNOWN for u in IDS}
    return {
        u: ("OFFLINE_VERIFIED" if checks[u] and u not in OPERATIONAL_GAPS
            else UNKNOWN)
        for u in IDS
    }


def contract():
    metric = {
        "id": "latency_p95", "label": "Latency p95",
        "baseline": {"value": 180, "unit": "ms",
                     "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "run:1",
                     "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["create_work_item", "measure_before_after"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }
    return {"version": 1, "project": "condor",
            "surfaces": [{"id": "inventory", "label": "Inventory",
                          "metrics": [metric]}]}


def observation(value=300, **overrides):
    data = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "value": value, "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z",
        "window_seconds": 300, "sample_count": 30,
        "severity": "high", "operational_impact": False,
        "bottleneck": "database", "evidence_ref": "run:2",
        "sha": "a" * 40, "release": "v1.2.3",
    }
    data.update(overrides)
    return data


def detected(value=300, **updates):
    return detect_performance(contract(), observation(value, **updates),
                              evaluated_at=NOW)


def proposal(**updates):
    item = {
        "work_id": "perf-condor-inventory-1", "origin_mode": "automatic",
        "origin_system": "factory", "group_id": "pl0n3r-group",
        "project_id": "condor", "repository_ref": "pl0n3r/Condor",
        "work_type": "engineering", "requested_capabilities":
            ["coding", "database"],
        "required_roles": ["dba", "ingenieria-software", "qa"],
        "authority_level": "operational",
        "producer_ref": "factory:performance",
        "priority_class": "high", "severity": "high", "depends_on": [],
        "claims": ["performance:condor:inventory"],
        "policy_ref": "factory:constitution-v1",
        "evidence_refs": ["run:2"],
        "idempotency_key": "perf-condor-inventory-run2",
        "observed_at": "2026-09-28T20:05:00Z",
    }
    result = {
        "version": 1, "workflow_action": "create_work_item",
        "change_id": "inventory_index",
        "hypothesis_ref": "hypothesis:inventory-index",
        "reversible": True, "tests_covered": True, "within_authority": True,
        "changes_product_semantics": False, "triggered_conditions": [],
        "rollback_ref": "rollback:revert-index", "work_item": item,
    }
    result.update(updates)
    return result


def manifest():
    return {
        "version": 1, "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {
            "copies": 3, "media_types": 2, "offsite_copies": 1,
            "immutable_copies": 1, "undetected_restore_failures": 0,
        },
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "google_drive"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def evidence():
    workflow = read(".github/workflows/liberar-reservas.yml")
    docs = read("docs/liberacion-automatica-de-reservas.md")
    readme = read("README.md")
    before = detected()
    after = detected(220, evidence_ref="run:3",
                     observed_at="2026-09-28T20:05:30Z",
                     sha="b" * 40, release="v1.2.4")
    status = derive_performance_status(before)
    healthy = derive_performance_status(after)
    triage = triage_performance(before)
    plan = plan_remediation(before, triage, proposal())
    escalation = plan_remediation(
        before, triage, proposal(triggered_conditions=["cost_change"]))
    compare = evaluate_before_after(before, after)
    insufficient_compare = evaluate_before_after(
        before, detected(220, observed_at="2026-09-28T19:00:00Z"))
    stale = derive_performance_status(
        detected(220, observed_at="2026-09-28T19:00:00Z"))
    bad = copy.deepcopy(manifest())
    bad["protection"]["copies"] = 2
    schema = json.loads(read("recovery/contract.schema.json"))
    checks = {
        "ISSUE-1382:AC-05": (
            "deferred_low_quota" in workflow and "exit 0" in workflow
            and all(part in docs for part in (
                "24 horas", "100 ciclos", "terminales", "por repositorio",
                "cero falsos positivos", "QA individual"))),
        "ISSUE-1382:AC-06": (
            "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'" in workflow
            and "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'true'" not in workflow
            and "release_authorized" in workflow),
        "ISSUE-1382:AC-07": (
            "docs/liberacion-automatica-de-reservas.md" in readme
            and "Fase A" in docs and "Fase B" in docs),
        "ISSUE-304:AC-01": (
            validate_performance_contract(contract())["version"] == 1
            and len(contract()["surfaces"][0]["metrics"]) == 1),
        "ISSUE-304:AC-02": (
            before["classification"] in {"PERF_DEGRADATION", "PERF_INCIDENT"}
            and before["evidence_ref"] == "run:2"),
        "ISSUE-304:AC-03": (
            "dba" in triage["role_hints"] and "qa" in triage["role_hints"]),
        "ISSUE-304:AC-04": (
            compare["decision"] == "ADOPT"
            and after["evidence_ref"] != before["evidence_ref"]
            and insufficient_compare["decision"] == "REVERT_OR_REPLAN"
            and "evidence_not_current" in insufficient_compare["reasons"]),
        "ISSUE-304:AC-05": (
            plan["decision"] == "AUTO_REPAIR"
            and bool(proposal()["hypothesis_ref"])),
        "ISSUE-304:AC-06": (
            stale["status"] == UNKNOWN and status["status"] == "DEGRADED"),
        "ISSUE-304:AC-07": (
            plan["decision"] == "AUTO_REPAIR"
            and bool(proposal()["work_item"]["work_id"])),
        "ISSUE-304:AC-08": (
            plan["decision"] == "AUTO_REPAIR"
            and proposal()["reversible"] is True),
        "ISSUE-304:AC-09": (
            escalation["decision"] == "ESCALATE"
            and "cost_change" in proposal(
                triggered_conditions=["cost_change"])["triggered_conditions"]),
        "ISSUE-304:AC-10": (
            readiness_projection(status)["status"] == status["status"]
            and readiness_projection(status)["evidence_refs"] ==
                status["evidence_refs"]),
        "ISSUE-304:AC-11": (
            compare["decision"] == "ADOPT"
            and derive_performance_status(
                after, remediation=plan, comparison=compare)["status"]
                == "HEALTHY"),
        "ISSUE-304:AC-12": (
            "no crea scheduler ni backlog paralelo"
            in read("docs/performance-engineering.md")
            and status["parallel_queue"] is False),
        "ISSUE-305:AC-01": (
            validate_recovery_manifest(manifest())["version"] == 1
            and schema["additionalProperties"] is False
            and json.loads(canonical_recovery_manifest(manifest())) ==
                manifest()),
    }
    return checks


class BrechasFactory02Tests(unittest.TestCase):
    def test_contrato_principal(self):
        extracted = rows(read("docs/matriz-cobertura.md"))
        checks = evidence()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(IDS), set(extracted))
        self.assertEqual(set(checks), set(IDS))
        for key in IDS:
            with self.subTest(key=key):
                self.assertEqual(extracted[key][2], "NO_VERIFICABLE")
                self.assertTrue(checks[key], f"{key}: regresión offline")
        self.assertEqual(
            {key for key, result in assess(read("docs/matriz-cobertura.md"),
                                            checks).items()
             if result == UNKNOWN},
            set(OPERATIONAL_GAPS),
        )

    def test_falla_cerrado(self):
        original = read("docs/matriz-cobertura.md")
        line = next(line for line in original.splitlines()
                    if chr(96) + IDS[0] + chr(96) in line)
        for invalid in (
            None, "", original.replace(line, "", 1),
            original + "\n" + line,
            original + "\n    " + line,
            original.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO")),
        ):
            with self.subTest(invalid=str(invalid)[:25]):
                with self.assertRaises(ValueError):
                    rows(invalid)
                self.assertEqual(set(assess(invalid, dict.fromkeys(IDS, True))
                                     .values()), {UNKNOWN})
        for invalid in (
            None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
            dict.fromkeys(IDS, "success"),
            {**dict.fromkeys(IDS, True), "other": True},
        ):
            self.assertEqual(set(assess(original, invalid).values()), {UNKNOWN})
        for invalid in (2, None, True, "1"):
            bad = manifest()
            bad["version"] = invalid
            with self.assertRaises(RecoveryContractError):
                validate_recovery_manifest(bad)
        invalid_contract = contract()
        invalid_contract["version"] = 2
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(invalid_contract)
        self.assertEqual(
            derive_performance_status(detected(220, sample_count=2))["status"],
            UNKNOWN)

    def test_sin_datos_reales(self):
        fixtures = json.dumps([contract(), observation(), proposal(), manifest()],
                              sort_keys=True).lower()
        for forbidden in (
            "authorization", "password", "access_token",
            "https://", "http://", "@" + "gmail",
        ):
            self.assertNotIn(forbidden, fixtures)
        tree = ast.parse(read("tests/test_brechas_factory_02.py"))
        imports = {
            alias.name.split(".")[0] for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        self.assertFalse(imports & {"requests", "socket", "urllib",
                                    "subprocess"})
        self.assertTrue(all(i.startswith("ISSUE-") for i in IDS))

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        checks = evidence()
        verdicts = assess(matrix, checks)
        self.assertEqual(set(OPERATIONAL_GAPS) & set(IDS), set(OPERATIONAL_GAPS))
        for key in IDS:
            with self.subTest(key=key):
                self.assertNotIn(verdicts[key], {"PRODUCTION_GREEN", "LIVE"})
                self.assertEqual(assess(matrix, {**checks, key: False})[key],
                                 UNKNOWN)
        for key, why in OPERATIONAL_GAPS.items():
            self.assertEqual(verdicts[key], UNKNOWN, why)
            self.assertTrue(why and "_" in why)
        self.assertEqual(
            derive_performance_status(
                detected(220, observed_at="2026-09-28T19:00:00Z")
            )["status"], UNKNOWN)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'",
                      read(".github/workflows/liberar-reservas.yml"))
        missing = manifest()
        missing["protection"]["copies"] = 2
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(missing)


if __name__ == "__main__":
    unittest.main()
