"""Factory #1844: regresiones de feedback, permisos y rollback.

Ejercita código real con entradas sintéticas, sin red, secretos, datos
personales ni lectura de docs/matriz-cobertura*.md.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib import request

from producto.feedback import (
    FeedbackValidationError, aggregate, load_epic_markers, parse_epic_marker,
    validate_record,
)
from scripts.reusable_permission_compat import compare_callers, compare_permissions
from scripts.release_auto_rollback_plan import plan_rollback


CATALOG = {
    "error_rate": {"family": "error", "unit": "ratio", "direction": "decrease"},
    "conversion_rate": {
        "family": "conversion", "unit": "ratio", "direction": "increase",
    },
}
EPIC = "example/sandbox#7"
AFFECTED = "a" * 40
STABLE = "b" * 40


def record(phase="baseline", **overrides):
    row = {
        "project": "example/sandbox",
        "epic": EPIC,
        "metric": "error_rate",
        "surface": "checkout",
        "phase": phase,
        "period_start": (
            "2026-01-01T00:00:00Z" if phase == "baseline"
            else "2026-01-10T00:00:00Z"
        ),
        "period_end": (
            "2026-01-08T00:00:00Z" if phase == "baseline"
            else "2026-01-17T00:00:00Z"
        ),
        "value": 0.02 if phase == "baseline" else 0.04,
        "sample_size": 200,
    }
    row.update(overrides)
    return row


def epic_body(metric="error_rate", surface="checkout"):
    value = {"metric": metric, "surface": surface, "target_improvement_pct": 10}
    return "objetivo\n<!-- factory-product-metric " + json.dumps(value) + " -->"


def consumer_run(sha, conclusion, jobs, run_id, repo="example/consumer",
                 workflow="CI"):
    return {
        "repository": repo, "workflow": workflow, "run_id": run_id,
        "factory_sha": sha, "conclusion": conclusion,
        "authenticated": True, "materialized_jobs": jobs,
    }


def snapshot():
    return {
        "phase": "construccion", "kill_switch_state": "RUNNING",
        "tag_protected": True, "evidence_authenticated": True,
        "incident_type": "startup_failure",
        "affected_factory_sha": AFFECTED, "current_v1_sha": AFFECTED,
        "stable_factory_sha": STABLE,
        "affected_consumer_runs": [
            consumer_run(AFFECTED, "startup_failure", False, 200),
        ],
        "stable_consumer_runs": [consumer_run(STABLE, "success", True, 100)],
    }


class CoberturaFactory53Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # retroalimentacion-producto L9 y L49: identidad del proyecto,
        # marcador real del épico y vínculo metric/surface con el resultado.
        before = validate_record(record(), CATALOG, "baseline")
        after = validate_record(record("post-deploy"), CATALOG, "post")
        self.assertEqual(before["project"], "example/sandbox")
        self.assertEqual(after["epic"], EPIC)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "epic-markers.json"
            path.write_text(json.dumps({EPIC: epic_body()}), encoding="utf-8")
            markers = load_epic_markers(path, CATALOG, [EPIC])
            result = aggregate([before, after], CATALOG, epic_markers=markers)
        self.assertEqual(markers[EPIC]["metric"], "error_rate")
        self.assertEqual(markers[EPIC]["surface"], "checkout")
        self.assertEqual(result["results"][0]["status"], "regressed")
        self.assertEqual(result["proposals"][0]["target_improvement_pct"], 10.0)

        # reusable-permission-compat L3,L7,L8,L10: lattice none<read<write,
        # un scope ausente vale none; un grant debe dominar cada requisito.
        self.assertTrue(compare_permissions(
            {"contents": "read", "checks": "none"},
            {"contents": "write"},
        )["compatible"])
        for level in ("none", "read", "write"):
            self.assertTrue(compare_permissions(
                {"actions": level}, {"actions": "write"},
            )["compatible"])
        self.assertEqual(compare_permissions(
            {"checks": "read"}, {},
        )["missing"], [
            {"scope": "checks", "required": "read", "granted": "none"},
        ])
        self.assertEqual(compare_permissions(
            {"contents": "write"}, {"contents": "read"},
        )["reason"], "insufficient_permissions")

        # reusable-permission-compat L11-U1/U2: unanimidad de consumidores;
        # L17-U1: el módulo valida mapas, sin interpretar YAML ni llamar API.
        callers = {
            "one": {"contents": "read"}, "two": {"contents": "write"},
            "three": {"contents": "read"},
        }
        self.assertTrue(compare_callers({"contents": "read"}, callers)["compatible"])
        callers["three"] = {"contents": "none"}
        collective = compare_callers({"contents": "read"}, callers)
        self.assertEqual(collective["reason"], "caller_incompatible")
        self.assertEqual(
            [c["caller"] for c in collective["callers"] if not c["compatible"]],
            ["three"],
        )
        self.assertEqual(compare_permissions(
            {"issues": "write"}, {"issues": "write"},
        )["reason"], "compatible")

        # reusable-release-rollback L11,L12,L13,L19,L23,L24: runs concretos
        # y SHA estable con historial; nunca concede autoridad de mover tags.
        evidence = snapshot()
        original = deepcopy(evidence)
        planned = plan_rollback(evidence)
        self.assertEqual(planned["decision"], "HUMAN_GATE_REQUIRED")
        self.assertEqual(planned["reason"], "owner_must_authorize_v1_rollback")
        self.assertEqual(planned["proposed_stable_sha"], STABLE)
        self.assertEqual(evidence["affected_factory_sha"], AFFECTED)
        self.assertEqual(evidence["stable_factory_sha"], STABLE)
        self.assertEqual(evidence, original)
        self.assertIs(planned["authorizes_tag_move"], False)
        self.assertEqual(planned["mutations"], 0)
        self.assertEqual(len(planned["postrollback_verification_required"]), 3)

    def test_falla_cerrado(self):
        # Feedback L9/L49: proyecto/epic inválido, Issue ausente, sin marker,
        # discrepancias de metric/surface y marker malformado.
        for row in (
            record(project="solo"), record(project="example//sandbox"),
            record(project="example/other"), record(epic="example/other#7"),
        ):
            with self.subTest(project=row["project"], epic=row["epic"]):
                with self.assertRaises(FeedbackValidationError):
                    validate_record(row, CATALOG, "invalid")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "epic-markers.json"
            for value in (
                {}, {EPIC: "sin marker"},
                {EPIC: epic_body(metric="conversion_rate")},
                {EPIC: epic_body(surface="other")},
            ):
                path.write_text(json.dumps(value), encoding="utf-8")
                if not value or value[EPIC] == "sin marker":
                    with self.assertRaises(FeedbackValidationError):
                        load_epic_markers(path, CATALOG, [EPIC])
                else:
                    markers = load_epic_markers(path, CATALOG, [EPIC])
                    rows = [validate_record(record(), CATALOG, "synthetic")]
                    with self.assertRaises(FeedbackValidationError):
                        aggregate(rows, CATALOG, epic_markers=markers)
            with self.assertRaises(FeedbackValidationError):
                parse_epic_marker("<!-- factory-product-metric ??? -->", CATALOG)

        # Reusable L9/L19-U2: mapas, scopes, levels, evidencia inválidos.
        for required, granted in (
            ({"mystery": "read"}, {"contents": "write"}),
            ({"contents": "admin"}, {"contents": "write"}),
            ({"contents": "read"}, {"contents": "owner"}),
            ({"contents": "read"}, None),
            (None, {"contents": "write"}),
        ):
            with self.subTest(required=required, granted=granted):
                decision = compare_permissions(required, granted)
                self.assertFalse(decision["compatible"])
                self.assertEqual(decision["reason"], "invalid_contract")
        for consumers in ({}, None, {"": {"contents": "write"}}):
            self.assertFalse(compare_callers(
                {"contents": "read"}, consumers,
            )["compatible"])

        # Rollback L11/L12/L13/L19/L23/L24: nunca inferir estabilidad del
        # último verde, de un run no autenticado o de SHA no correlacionado.
        for patch_fields in (
            {"stable_consumer_runs": []},
            {"affected_consumer_runs": []},
            {"stable_factory_sha": AFFECTED},
            {"stable_factory_sha": "last-green"},
            {"affected_factory_sha": "not-sha"},
            {"current_v1_sha": STABLE},
            {"incident_type": "success"},
            {"evidence_authenticated": False},
        ):
            case = snapshot()
            case.update(patch_fields)
            with self.subTest(changed=patch_fields):
                result = plan_rollback(case)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertIsNone(result["proposed_stable_sha"])
                self.assertIs(result["authorizes_tag_move"], False)
        for key, value in (
            ("repository", "example/another"),
            ("workflow", "Different"), ("run_id", 250),
            ("authenticated", False), ("materialized_jobs", False),
        ):
            case = snapshot()
            case["stable_consumer_runs"][0][key] = value
            with self.subTest(field=key):
                self.assertEqual(plan_rollback(case)["decision"], "BLOCKED")

    def test_sin_datos_reales(self):
        # Guards explícitos: ningún flujo ejecuta red, comandos, deploy o
        # publicación. Solo contratos puros y fixtures ficticios.
        def forbidden(*_args, **_kwargs):
            raise AssertionError("I/O externo prohibido en fixture")

        with patch.object(socket, "create_connection", forbidden), \
             patch.object(request, "urlopen", forbidden), \
             patch.object(subprocess, "run", forbidden):
            self.assertTrue(compare_permissions(
                {"contents": "read"}, {"contents": "write"},
            )["compatible"])
            self.assertEqual(parse_epic_marker(
                epic_body(), CATALOG,
            )["surface"], "checkout")
            result = plan_rollback(snapshot())
            self.assertEqual(result["decision"], "HUMAN_GATE_REQUIRED")
            self.assertFalse(result["authorizes_tag_move"])
            self.assertEqual(result["mutations"], 0)


if __name__ == "__main__":
    unittest.main()
