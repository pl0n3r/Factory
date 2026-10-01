"""Regresiones de la vista generada ESTADO.md."""
import copy
import json
import unittest
from pathlib import Path

from intelligence.derived_views import DerivedViewSpec
from intelligence.factory_status import (
    COMMITTED_TANDA2_EVIDENCE,
    derive_factory_status,
    render_committed_estado,
    render_estado,
)

ROOT = Path(__file__).resolve().parents[1]
ESTADO = ROOT / "ESTADO.md"
MANIFEST = ROOT / "config" / "derived_views.json"
PLAN = ROOT / "PLAN-AGENTES.md"
README = ROOT / "README.md"

DIRECTED_PROMPT = (
    "Trabajas en el repositorio pl0n3r/Condor. Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "para este repositorio."
)
DISPATCH_PROMPT = (
    "Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "en modo despachador."
)


class PlanEstadoTests(unittest.TestCase):
    def test_all_tanda2_epics_completed_activate_tanda3_deterministically(self):
        first = derive_factory_status(COMMITTED_TANDA2_EVIDENCE)
        second = derive_factory_status(reversed(COMMITTED_TANDA2_EVIDENCE))
        self.assertEqual(first, second)
        self.assertEqual(first["tanda1"], "COMPLETADA")
        self.assertEqual(first["tanda2"], "COMPLETADA")
        self.assertEqual(first["tanda3"], "ACTIVA")
        self.assertTrue(first["tanda3_active"])
        self.assertEqual(first["freshness"], "2026-09-30T17:03:36Z")

    def test_missing_open_or_inconsistent_epic_evidence_fails_closed(self):
        cases = []
        missing = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))[:-1]
        cases.append(missing)
        opened = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        opened[0]["state"] = "open"
        cases.append(opened)
        not_completed = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        not_completed[1]["state_reason"] = "not_planned"
        cases.append(not_completed)
        contradictory = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        contradictory[2]["labels"] = ()
        cases.append(contradictory)
        duplicate = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        conflict = copy.deepcopy(duplicate[0])
        conflict["state"] = "open"
        duplicate.append(conflict)
        cases.append(duplicate)
        bad_url = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        bad_url[0]["url"] = "https://github.com/pl0n3r/Condor/issues/999"
        cases.append(bad_url)
        bad_timestamp = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        bad_timestamp[0]["updated_at"] = "2026-09-26"
        cases.append(bad_timestamp)
        bad_issue = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        bad_issue[0]["issue_number"] = True
        cases.append(bad_issue)
        bad_labels = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        bad_labels[0]["labels"] = "estado: completado"
        cases.append(bad_labels)
        missing_field = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        del missing_field[0]["state_reason"]
        cases.append(missing_field)
        non_object = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        non_object[0] = "invalid"
        cases.append(non_object)
        unexpected = list(copy.deepcopy(COMMITTED_TANDA2_EVIDENCE))
        extra = copy.deepcopy(unexpected[0])
        extra["repository_ref"] = "pl0n3r/Factory"
        extra["issue_number"] = 718
        extra["url"] = "https://github.com/pl0n3r/Factory/issues/718"
        unexpected.append(extra)
        cases.append(unexpected)

        for evidence in cases:
            with self.subTest(evidence=evidence):
                status = derive_factory_status(evidence)
                self.assertEqual(status["tanda2"], "UNKNOWN")
                self.assertEqual(status["tanda3"], "BLOQUEADA")
                self.assertFalse(status["tanda3_active"])
                self.assertTrue(status["reasons"])
                rendered = render_estado(evidence)
                self.assertIn("TANDA 2:** UNKNOWN", rendered)
                self.assertIn("TANDA 3:** BLOQUEADA", rendered)

    def test_committed_estado_matches_canonical_render_and_sources(self):
        committed = ESTADO.read_text(encoding="utf-8")
        self.assertEqual(committed, render_committed_estado())
        for ref in ("Condor#192", "GrindFlow#129", "brvtal#630", "FactoryRunner#1"):
            self.assertIn(ref, committed)
        self.assertIn("Vista generada y no autoritativa", committed)
        self.assertIn("Snapshot SHA-256", committed)

    def test_generated_view_manifest_plan_pointer_and_readme_prompts_stay_consistent(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        specs = {row["view_id"]: DerivedViewSpec(**row) for row in payload["views"]}
        spec = specs["factory.estado.tandas"]
        spec.validate()
        self.assertEqual(spec.view, "ESTADO.md")
        self.assertEqual(spec.mode, "generated")
        self.assertEqual(spec.generator, "intelligence.factory_status:render_committed_estado")
        self.assertEqual(spec.drift_check, "tests/test_plan_estado.py")

        plan = PLAN.read_text(encoding="utf-8")
        self.assertIn("[ESTADO.md](ESTADO.md)", plan)
        self.assertIn("vista rápida derivada", plan)
        self.assertIn(
            "reglas 1–4 de la sección 0 → gate de tanda → reglas 5–7 → "
            "desempate de la regla 7",
            plan,
        )

        readme = README.read_text(encoding="utf-8")
        self.assertEqual(readme.count(DIRECTED_PROMPT), 1)
        self.assertEqual(readme.count(DISPATCH_PROMPT), 1)


if __name__ == "__main__":
    unittest.main()
