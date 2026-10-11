#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.29 (#1172).

No publica tags, no consulta GitHub ni infiere el gate humano. La selección
de evidencia de CI/main, startup watcher, freeze y v1 es externa y exact-SHA.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


class ReleaseCandidate1029Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_29(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = payload["version"]
        self.assertIsInstance(version, str)
        self.assertRegex(version, r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
        self.assertGreaterEqual(tuple(map(int, version.split("."))), (1, 0, 29))

    @staticmethod
    def _acceptance_tools():
        try:
            from scripts.aceptacion_kit import Criterion, run_named_test
        except ModuleNotFoundError as exc:
            if exc.name != "scripts":
                raise
            from aceptacion_kit import Criterion, run_named_test
        return Criterion, run_named_test

    def test_required_repairs_previous_contracts_and_release_drift(self) -> None:
        Criterion, run_named_test = self._acceptance_tools()
        # Contratos que materializan las garantías históricas de 1.0.27.
        previous = (
            "test_candidate_version_is_1_0_27",
            "test_candidate_keeps_1_0_26_guarantees_as_historical_compatibility",
            "test_candidate_keeps_authenticated_policy_transport_contract",
            "test_candidate_keeps_release_gate_and_window_separation",
        )
        targets = [
            "tests/test_release_candidate_1_0_27.py::ReleaseCandidate1027Tests::"
            + method for method in previous
        ]
        # Representantes ejecutables de los repairs fusionados en main. Se
        # ejecutan los módulos reales, no inspecciones superficiales de nombres.
        targets.extend((
            "tests/test_bootstrap_coordination.py::BootstrapCoordinationTests::"
            "test_bootstrap_is_idempotent_and_rejects_conflicting_intent",
            "tests/test_release_comment_pages.py::ReleaseCommentPagesTests::"
            "test_malformed_or_incomplete_comment_pages_fail_closed",
            "tests/test_release_api_budget.py::ReleaseApiBudgetTests::"
            "test_rate_limit_retries_bounded_and_always_fail_closed",
            "tests/test_lease_authority_snapshot.py::LeaseAuthoritySnapshotTests::"
            "test_blocked_issue_with_active_v3_remains_exclusive",
            "tests/test_automerge_construccion.py::AutoMergeConstruccionTests::"
            "test_valid_construction_candidate_is_diagnostic_only",
            "tests/test_automerge_construccion.py::AutoMergeConstruccionTests::"
            "test_live_sensitive_paths_and_freeze_require_human_gate",
            "tests/test_captura_leccion_workflow.py::CaptureLessonWorkflowTests::"
            "test_event_gate_executed_against_fixtures",
            "tests/test_recovery_manifests.py::RecoveryManifestsTests::"
            "test_five_manifests_validate_against_closed_schema",
            "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
            "test_latest_rejects_distinct_shas_in_gate_body",
            "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
            "test_preflight_revalidates_v1_ruleset_read_only",
            "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
            "test_authenticated_check_transport_cannot_regress_to_anonymous_curl",
        ))
        for target in targets:
            with self.subTest(target=target):
                run_named_test(Criterion("AC-02", "test", target), self.root)


        # Snapshot informativo de la comparacion REST v1...main ya observada
        # fuera del test. Es una prueba OFFLINE del inventario, no una llamada
        # autenticada; el gate externo debe volver a comparar HEAD + tag.
        observed = {
            "tag_sha": "7be20fda7a60fd1371af3aa03f3f2ac6d03ec281",
            "main_sha": "79140a8ebbea1fe026c1ec500c8330062c1e78f5",
            "ahead_by": 24,
            "status": "ahead",
            "files": list(self._known_compare_paths())
        }
        self.assertEqual(self._validate_release_drift_fixture(observed),
                         set(self._declared_control_changes()))
        # La lista de diff histórico por sí sola también incluiría archivos
        # ELIMINADOS. Exigir que todo control declarado siga siendo un archivo
        # legible/no vacío en el árbol candidato, sin tratar esto como prueba
        # de contenido, firma, frescura o ausencia de deriva externa.
        for name in self._declared_control_changes():
            with self.subTest(required_control=name):
                path = self.root / name
                self.assertTrue(path.is_file(), "required_control_missing")
                self.assertGreater(path.stat().st_size, 0)

        # Negativos: paths nuevos de control, paginas incompletas, identidad
        # falsa o mismo SHA no pasan como evidencia de ausencia de deriva.
        for variant in (
            {**observed, "files": observed["files"] +
             [".github/workflows/unexpected-release.yml"]},
            {**observed, "files": observed["files"][:-1]},
            {**observed, "files": observed["files"] +
             [observed["files"][0]]},
            {**observed, "main_sha": observed["tag_sha"]},
            {**observed, "status": "identical"},
            {**observed, "ahead_by": True},
            {**observed, "tag_sha": "unknown"},
        ):
            with self.subTest(invalid=variant):
                with self.assertRaises(ValueError):
                    self._validate_release_drift_fixture(variant)

        # Misma cardinalidad y mismo par exact-SHA; el rechazo debe nacer de
        # un cambio de control NO declarado, no del chequeo len(files) != 53.
        unclassified = list(observed["files"])
        unclassified[-1] = ".github/workflows/unexpected-release.yml"
        with self.assertRaisesRegex(
            ValueError, "undeclared_release_or_security_drift"
        ):
            self._validate_release_drift_fixture(
                {**observed, "files": unclassified}
            )
        # Mismo numero de entradas y los mismos cambios sensibles: una ruta
        # no sensible inventada tambien debe quedar rechazada.
        altered_nonsensitive = list(observed["files"])
        altered_nonsensitive[-1] = "docs/unobserved-note.md"
        with self.assertRaisesRegex(
            ValueError, "unverified_compare_inventory"
        ):
            self._validate_release_drift_fixture(
                {**observed, "files": altered_nonsensitive}
            )
        omitted_control = list(observed["files"])
        omitted_control[0] = "docs/another-readme.md"
        with self.assertRaisesRegex(
            ValueError, "undeclared_release_or_security_drift"
        ):
            self._validate_release_drift_fixture(
                {**observed, "files": omitted_control}
            )

    @staticmethod
    def _known_compare_paths() -> tuple[str, ...]:
        """Inventario completo del compare observado v1...main; NO actualiza GitHub."""
        return (
            ".github/workflows/captura-leccion.yml",
            ".github/workflows/factory-ci.yml",
            ".github/workflows/release-bootstrap.yml",
            ".github/workflows/seguridad.yml",
            "docs/principios-construccion.md",
            "docs/release-bootstrap.md",
            "lecciones/registros/2026-10-construccion.jsonl",
            "lecciones/registros/principios-construccion.jsonl",
            "lecciones/test_memoria.py",
            "performance/contracts/autofactory.json",
            "performance/contracts/condor.json",
            "performance/contracts/controlbot.json",
            "performance/contracts/factoryrunner.json",
            "recovery/contract.py",
            "recovery/gdrive_adapter.py",
            "recovery/manifests/autofactory.yml",
            "recovery/manifests/brvtal.yml",
            "recovery/manifests/condor.yml",
            "recovery/manifests/controlbot.yml",
            "recovery/manifests/grindflow.yml",
            "scripts/automerge_construccion.py",
            "scripts/captura_leccion.py",
            "scripts/lease_authority_snapshot.py",
            "scripts/orquestar_fabrica.py",
            "scripts/release_api_budget.py",
            "scripts/salud_cola.py",
            "scripts/salud_cola_snapshot.py",
            "scripts/validar_claims_issue.py",
            "template/AGENTES.md",
            "tests/test_automerge_construccion.py",
            "tests/test_bootstrap_coordination.py",
            "tests/test_captura_leccion.py",
            "tests/test_captura_leccion_workflow.py",
            "tests/test_coordinacion_reusable_contract.py",
            "tests/test_lease_authority_snapshot.py",
            "tests/test_orquestar_fabrica.py",
            "tests/test_performance_autofactory_contract.py",
            "tests/test_performance_condor_contract.py",
            "tests/test_performance_controlbot_contract.py",
            "tests/test_performance_factoryrunner_contract.py",
            "tests/test_principios_construccion.py",
            "tests/test_recovery_contract.py",
            "tests/test_recovery_gdrive_adapter.py",
            "tests/test_recovery_manifests.py",
            "tests/test_release_api_budget.py",
            "tests/test_release_bootstrap_workflow.py",
            "tests/test_release_comment_pages.py",
            "tests/test_release_window_snapshot_complete.py",
            "tests/test_salud_cola.py",
            "tests/test_salud_cola_snapshot.py",
            "tests/test_security_comment_routing.py",
            "tests/test_template_principios_construccion.py",
            "tests/test_validar_claims_issue.py",
        )

    @staticmethod
    def _declared_control_changes() -> tuple[str, ...]:
        # Incluye seguridad.yml y captura-leccion.yml, omitidos inicialmente.
        return tuple([
            ".github/workflows/captura-leccion.yml",
            ".github/workflows/factory-ci.yml",
            ".github/workflows/release-bootstrap.yml",
            ".github/workflows/seguridad.yml",
            "scripts/automerge_construccion.py",
            "scripts/lease_authority_snapshot.py",
            "scripts/release_api_budget.py",
            "scripts/validar_claims_issue.py"
    ])

    @classmethod
    def _validate_release_drift_fixture(cls, observation: dict) -> set[str]:
        if type(observation) is not dict or set(observation) != {
            "tag_sha", "main_sha", "ahead_by", "status", "files"
        }:
            raise ValueError("invalid_compare_envelope")
        if (observation["tag_sha"] != "7be20fda7a60fd1371af3aa03f3f2ac6d03ec281"
                or observation["main_sha"] != "79140a8ebbea1fe026c1ec500c8330062c1e78f5"
                or observation["tag_sha"] == observation["main_sha"]
                or type(observation["ahead_by"]) is not int
                or observation["ahead_by"] != 24
                or observation["status"] != "ahead"):
            raise ValueError("unverified_compare_identity")
        files = observation["files"]
        if (type(files) is not list or len(files) != 53
                or any(type(path) is not str
                       or not re.fullmatch(r"[A-Za-z0-9._/-]+", path)
                       or path.startswith("/")
                       or "/../" in path or path.startswith("../")
                       for path in files)
                or len(set(files)) != len(files)):
            raise ValueError("invalid_compare_inventory")
        relevant = {
            path for path in files
            if path.startswith(".github/workflows/")
            or path.startswith("scripts/release_")
            or path in cls._declared_control_changes()
        }
        if relevant != set(cls._declared_control_changes()):
            raise ValueError("undeclared_release_or_security_drift")
        if tuple(sorted(files)) != cls._known_compare_paths():
            raise ValueError("unverified_compare_inventory")
        # Un fixture no sustituye la comparacion autenticada exact-SHA;
        # ningun estado READY, gate A, publication_allowed ni v1 se deriva.
        return relevant


if __name__ == "__main__":
    unittest.main()
