#!/usr/bin/env python3
"""Factory #1845: rollback de Factory@v1, pruebas puras de evidencia y autoridad.

No simula que un tag se movió, que un workflow de consumidor corrió, ni
que un OWNER concedió permiso. Nunca lee docs/matriz-cobertura*.md.
"""
from __future__ import annotations

from copy import deepcopy
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request

from scripts.release_auto_rollback_plan import plan_rollback


BAD = "a" * 40
GOOD = "b" * 40
CONSUMERS = (
    ("fixture/consumer-a", "Build", 400, 100),
    ("fixture/consumer-b", "Validate", 600, 200),
)
AFTER = [
    "new_consumer_run_materializes_jobs",
    "new_consumer_run_is_not_startup_failure",
    "published_v1_ref_matches_stable_sha",
]


def consumer(repo, workflow, number, sha, *, failed):
    return {
        "repository": repo,
        "workflow": workflow,
        "run_id": number,
        "factory_sha": sha,
        "conclusion": "startup_failure" if failed else "success",
        "authenticated": True,
        "materialized_jobs": not failed,
    }


def incident():
    """Evidencia sintética con dos consumidores y runs previos correlacionados."""
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "tag_protected": True,
        "evidence_authenticated": True,
        "incident_type": "startup_failure",
        "affected_factory_sha": BAD,
        "current_v1_sha": BAD,
        "stable_factory_sha": GOOD,
        "affected_consumer_runs": [
            consumer(repo, workflow, failed_run, BAD, failed=True)
            for repo, workflow, failed_run, stable_run in CONSUMERS
        ],
        "stable_consumer_runs": [
            consumer(repo, workflow, stable_run, GOOD, failed=False)
            for repo, workflow, failed_run, stable_run in CONSUMERS
        ],
    }


class CoberturaFactory54Tests(unittest.TestCase):
    """AC-01..04: tests de lógica real, nunca observación remota ficticia."""

    def assert_no_authority(self, result):
        self.assertIs(result["authorizes_tag_move"], False)
        self.assertEqual(result["mutations"], 0)
        self.assertEqual(result["postrollback_verification_required"], AFTER)

    def assert_blocked(self, evidence):
        result = plan_rollback(evidence)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIsNone(result["proposed_stable_sha"])
        self.assert_no_authority(result)
        return result

    def test_contrato_principal(self):
        # L25-U1/L26-U1: las identidades concretas de DOS consumidores y
        # los runs estables previos habilitan SOLO un plan, nunca el rollback.
        evidence = incident()
        original = deepcopy(evidence)
        result = plan_rollback(evidence)
        self.assertEqual(result["decision"], "HUMAN_GATE_REQUIRED")
        self.assertEqual(result["reason"], "owner_must_authorize_v1_rollback")
        self.assertEqual(result["proposed_stable_sha"], GOOD)
        self.assertEqual(evidence, original)
        self.assert_no_authority(result)

        # L30-U1/L32-U1/L34-U1/L38-U1: no se devuelven operaciones,
        # comandos Git, refs/tags/v1 ni una autorización de OWNER.
        self.assertEqual(set(result), {
            "decision", "reason", "proposed_stable_sha",
            "authorizes_tag_move", "mutations",
            "postrollback_verification_required",
        })
        self.assertNotIn("refs/tags/v1", str(result))
        self.assertNotIn("force", result)

        # L42-U1/L44-U1/L45-U1/L46-U1: el resultado REAL del plan
        # exige las TRES comprobaciones posteriores de consumidor/sha.
        self.assertEqual(result["postrollback_verification_required"], AFTER)

        # L48-U1/L50-U1/L63-U2: "plan listo" no significa consumidor
        # restaurado, incidente cerrado ni contrato caller compatible.
        self.assertNotEqual(result["decision"], "RECOVERED")
        self.assertNotEqual(result["decision"], "AUTHORIZED")
        self.assertEqual(result["mutations"], 0)

        # Orden de consumidores no altera la elección del SHA.
        reorder = incident()
        reorder["affected_consumer_runs"].reverse()
        reorder["stable_consumer_runs"].reverse()
        self.assertEqual(plan_rollback(reorder), result)

        # Un único consumidor afectado sigue siendo evidencia válida si
        # conserva historia correlacionada; NO autoriza mover la etiqueta.
        subset = incident()
        subset["affected_consumer_runs"].pop()
        self.assertEqual(plan_rollback(subset)["decision"], "HUMAN_GATE_REQUIRED")
        self.assert_no_authority(plan_rollback(subset))

    def test_falla_cerrado(self):
        # L25-U1/L26-U1: falla si falta cualquier run, no coincide repo,
        # workflow, SHA, evidencia de jobs o la historia no es previa.
        variations = [
            ("sin_consumidores", lambda s: s["affected_consumer_runs"].clear()),
            ("sin_historia", lambda s: s["stable_consumer_runs"].pop()),
            ("repo_distinto", lambda s: s["stable_consumer_runs"][1].update(
                repository="fixture/unknown")),
            ("workflow_distinto", lambda s: s["stable_consumer_runs"][0].update(
                workflow="Unknown")),
            ("run_tardio", lambda s: s["stable_consumer_runs"][1].update(
                run_id=601)),
            ("stable_sin_jobs", lambda s: s["stable_consumer_runs"][0].update(
                materialized_jobs=False)),
            ("affected_con_jobs", lambda s: s["affected_consumer_runs"][0].update(
                materialized_jobs=True)),
            ("stable_startup_failure", lambda s: s["stable_consumer_runs"][0].update(
                conclusion="startup_failure")),
            ("affected_success", lambda s: s["affected_consumer_runs"][0].update(
                conclusion="success")),
            ("stable_sha_incorrecto", lambda s: s["stable_consumer_runs"][0].update(
                factory_sha=BAD)),
            ("run_duplicado", lambda s: s["affected_consumer_runs"][1].update(
                run_id=400)),
            ("run_booleano", lambda s: s["affected_consumer_runs"][0].update(
                run_id=True)),
            ("run_no_autenticado", lambda s: s["stable_consumer_runs"][1].update(
                authenticated=False)),
            ("snapshot_no_autenticado", lambda s: s.update(
                evidence_authenticated=False)),
            ("tag_no_protegido", lambda s: s.update(tag_protected=False)),
            ("switch_pausado", lambda s: s.update(kill_switch_state="PAUSED")),
            ("sha_objetivo_igual", lambda s: s.update(stable_factory_sha=BAD)),
            ("v1_ya_cambiado", lambda s: s.update(current_v1_sha=GOOD)),
            ("sha_malformado", lambda s: s.update(stable_factory_sha="last-green")),
            ("incidente_distinto", lambda s: s.update(incident_type="failure")),
            ("datos_extra", lambda s: s.update(owner_approved=True)),
        ]
        for name, mutate in variations:
            with self.subTest(name=name):
                evidence = incident()
                mutate(evidence)
                self.assert_blocked(evidence)

        # L26-U1: el run estable anterior nunca puede inferirse de
        # que otro proyecto o workflow tuvo un run verde.
        no_evidence = incident()
        no_evidence["stable_consumer_runs"] = [
            consumer("fixture/unrelated", "Other", 1, GOOD, failed=False)
        ]
        self.assertEqual(
            self.assert_blocked(no_evidence)["reason"],
            "consumer_stable_history_missing",
        )

    def test_sin_datos_reales(self):
        # L30-U1/L38-U1: impedir ejecución de red, git, subprocess o
        # sistema durante el plan. Los valores son SHA/runs ficticios.
        def forbid(*_args, **_kwargs):
            raise AssertionError("I/O prohibido por el contrato offline")

        evidence = incident()
        with patch.object(socket, "create_connection", forbid), \
             patch.object(request, "urlopen", forbid), \
             patch.object(subprocess, "run", forbid):
            planned = plan_rollback(evidence)
            self.assertEqual(planned["decision"], "HUMAN_GATE_REQUIRED")
            self.assert_no_authority(planned)
            evidence["tag_protected"] = None
            self.assert_blocked(evidence)

    def test_gate_validar_presente(self):
        # AC-04: el check GitHub Validar sobre el HEAD exacto sigue
        # siendo imprescindible; este test no le atribuye "success".
        # El código prueba que sin prueba completa del consumidor
        # el rollback nunca obtiene autorización implícita.
        evidence = incident()
        evidence["evidence_authenticated"] = None
        self.assertEqual(
            self.assert_blocked(evidence)["reason"],
            "evidence_not_authenticated",
        )
        for value in (None, [], {}, "result: success"):
            with self.subTest(value=value):
                self.assert_blocked(value)


if __name__ == "__main__":
    unittest.main()
