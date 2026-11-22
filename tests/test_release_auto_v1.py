"""Regresiones sintéticas del contrato Factory@v1 (#2181).

La elegibilidad no es autoridad para mover refs/tags/v1. Hasta que el dueño
habilite la política de release automático, el flujo real sigue protegido.
Ninguna prueba hace llamadas a GitHub ni escribe tags o releases.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from scripts.release_auto_eligibility import (
    REQUIRED_CHECKS as ELIGIBILITY_CHECKS,
    evaluate as evaluate_eligibility,
)
from scripts.release_auto_policy import (
    REQUIRED_CHECKS as POLICY_CHECKS,
    evaluate as evaluate_policy,
)
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
PUBLISHED_SHA = "b" * 40


def eligibility_fixture() -> dict:
    """Escenario futuro coherente, sin evidencias reales ni autorización."""
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "release_machinery_changed": False,
        "v1_tag_protected": True,
        "evidence_authenticated": True,
        "main_sha": SHA,
        "observed_main_sha": SHA,
        "candidate_version": "1.0.59",
        "published_version": "1.0.58",
        "checks": [
            {"name": name, "head_sha": SHA, "status": "completed",
             "conclusion": "success", "authenticated": True}
            for name in sorted(ELIGIBILITY_CHECKS)
        ],
    }


def policy_fixture() -> dict:
    """Snapshot para la política histórica de promoción exact-SHA."""
    return {
        "candidate_sha": SHA,
        "observed_main_sha": SHA,
        "published_v1_sha": PUBLISHED_SHA,
        "v1_tag_protected": True,
        "evidence_authenticated": True,
        "kill_switch_state": "RUNNING",
        "freeze_active": False,
        "security_veto": False,
        "owner_decision": {
            "option": "A", "candidate_sha": SHA,
            "category": "factory-release", "journal_verified": True,
            "owner": "pl0n3r",
        },
        "checks": [
            {"name": name, "head_sha": SHA, "status": "completed",
             "conclusion": "success", "authenticated": True}
            for name in sorted(POLICY_CHECKS)
        ],
    }


def switch_fixture(state: str) -> dict:
    return {
        "number": 767,
        "url": "https://api.github.com/repos/pl0n3r/Factory/issues/767",
        "repository_url": "https://api.github.com/repos/pl0n3r/Factory",
        "state": "closed",
        "user": {"login": "pl0n3r"},
        "body": (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"' + state + '","owner":"pl0n3r"} -->'
        ),
    }


class ReleaseAutoV1Tests(unittest.TestCase):
    def assert_inert(self, decision: dict) -> None:
        self.assertIs(decision["authorizes_release"], False, decision)
        self.assertEqual(decision["mutations"], 0, decision)

    def test_construccion_version_nueva_y_gates_verdes_solo_habilita_preparacion(self) -> None:
        """AC-01: la candidatura es elegible; no simular publicación de v1."""
        sample = eligibility_fixture()
        original = deepcopy(sample)
        eligible = evaluate_eligibility(sample)
        self.assertEqual(eligible["decision"], "DRY_RUN_ELIGIBLE")
        self.assertEqual(eligible["reason"], "offline_snapshot_only")
        self.assert_inert(eligible)
        self.assertEqual(sample, original)
        self.assertEqual(eligible, evaluate_eligibility(sample))

        # El flujo heredado de publicación todavía exige el voto OWNER exact-SHA.
        policy = evaluate_policy(policy_fixture())
        self.assertEqual(policy["state"], "REVIEW_ONLY")
        self.assert_inert(policy)
        self.assertEqual(policy["release_tag_writes"], 0)

    def test_live_y_cambio_maquinaria_exigen_puerta_humana(self) -> None:
        """AC-01: incluso con todos los checks verdes, no autopublicar."""
        for changes in (
            {"phase": "live"},
            {"release_machinery_changed": True},
            {"phase": "live", "release_machinery_changed": True},
        ):
            with self.subTest(changes=changes):
                sample = eligibility_fixture()
                sample.update(changes)
                result = evaluate_eligibility(sample)
                self.assertEqual(result["decision"], "HUMAN_GATE_REQUIRED")
                self.assertEqual(result["reason"], "live_or_release_machinery")
                self.assert_inert(result)

    def test_kill_switch_cierra_ambas_politicas_antes_de_publicar(self) -> None:
        """AC-01: PAUSED, UNKNOWN y marker inválido nunca son ALLOW."""
        self.assertFalse(evaluate_unattended_kill_switch(
            switch_fixture("RUNNING")).global_pause)
        self.assertTrue(evaluate_unattended_kill_switch(
            switch_fixture("PAUSED")).global_pause)
        self.assertTrue(evaluate_unattended_kill_switch(
            switch_fixture("UNKNOWN")).global_pause)
        malformed = switch_fixture("RUNNING")
        malformed["body"] += malformed["body"]
        self.assertTrue(evaluate_unattended_kill_switch(malformed).global_pause)

        for state in ("PAUSED", "UNKNOWN", None):
            with self.subTest(state=state):
                candidate = eligibility_fixture()
                candidate["kill_switch_state"] = state
                result = evaluate_eligibility(candidate)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertEqual(result["reason"], "kill_switch_not_running")
                self.assert_inert(result)

                policy = policy_fixture()
                policy["kill_switch_state"] = state
                blocked = evaluate_policy(policy)
                self.assertEqual(blocked["state"], "BLOCKED")
                self.assert_inert(blocked)

    def test_sin_version_o_sha_exactos_no_hay_autorizacion(self) -> None:
        """Casos negativos: no convertir un snapshot incompleto en permiso."""
        for changes in (
            {"candidate_version": "1.0.58"},
            {"candidate_version": "2.0.0"},
            {"observed_main_sha": PUBLISHED_SHA},
            {"evidence_authenticated": False},
            {"v1_tag_protected": False},
            {"checks": []},
        ):
            with self.subTest(changes=changes):
                sample = eligibility_fixture()
                sample.update(changes)
                result = evaluate_eligibility(sample)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assert_inert(result)

    def test_sin_voto_owner_o_con_sha_equivocado_no_hay_release(self) -> None:
        """El criterio de construcción no elimina las puertas duras existentes."""
        for changes in (
            {"owner_decision": None},
            {"owner_decision": {**policy_fixture()["owner_decision"], "option": "B"}},
            {"owner_decision": {**policy_fixture()["owner_decision"],
                                "candidate_sha": PUBLISHED_SHA}},
            {"observed_main_sha": PUBLISHED_SHA},
        ):
            with self.subTest(changes=changes):
                sample = policy_fixture()
                sample.update(changes)
                result = evaluate_policy(sample)
                self.assertEqual(result["state"], "BLOCKED")
                self.assert_inert(result)

    def test_workflow_real_no_afirma_autopublicacion_habilitada(self) -> None:
        """La prueba es offline; la publicación real sigue siendo OWNER-dispatch."""
        workflow = (ROOT / ".github/workflows/release-bootstrap.yml").read_text(
            encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("GATE_ISSUE:", workflow)
        self.assertIn("Verificar SHA, Issues, puerta y v1", workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
