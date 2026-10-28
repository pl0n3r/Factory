"""Factory #1308 / F1C: una sola baja y pruebas de Sonar offline conservadas."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_scheduled_entrypoints import EXPECTED, SAFE_ARGS, ScheduledEntrypointTests

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
REMOVED = "sonar-watch.yml"
BASE_SHA = "d9d9681720b258ad871c14260a254d389fbb96d2"
BLOB_SHA = "8dd0f9cfed97be7a804c8248a89b17b817639a7a"
EXPECTED_ACTIVE = frozenset([
    "aceptacion.yml",
    "auditoria-privacidad.yml",
    "automerge-construccion.yml",
    "automerge.yml",
    "bootstrap-coordination.yml",
    "ci.yml",
    "codeql-evidence.yml",
    "coordinacion-trabajo.yml",
    "coordinacion.yml",
    "costos.yml",
    "deploy.yml",
    "etiquetas-pr.yml",
    "etiquetas.yml",
    "factory-ci.yml",
    "liberar-reservas.yml",
    "observar.yml",
    "orquestador.yml",
    "politica-comentario.yml",
    "politica.yml",
    "preview.yml",
    "privacidad.yml",
    "provision-project.yml",
    "readme.yml",
    "release-bootstrap.yml",
    "release-window.yml",
    "release.yml",
    "reusable-release-watchdog.yml",
    "reusable-selftest.yml",
    "roles.yml",
    "seguridad.yml",
    "sonar.yml",
    "unattended-watchdog.yml"
])
# Mantener los 32 nombres históricos exactos; sumar las adiciones posteriores validadas.
LEGAL_SYNC = WF / "revision-juridica-sync.yml"
if LEGAL_SYNC.is_file() and not LEGAL_SYNC.is_symlink():
    EXPECTED_ACTIVE = EXPECTED_ACTIVE | frozenset({"revision-juridica-sync.yml"})
# Factory#1425: observador GET-only posterior al ledger F1C, sin bajas.
QUEUE_OBSERVER = WF / "salud-cola.yml"
if QUEUE_OBSERVER.is_file() and not QUEUE_OBSERVER.is_symlink():
    EXPECTED_ACTIVE = EXPECTED_ACTIVE | frozenset({"salud-cola.yml"})
# Factory#1442: adición del reusable consumidor, sin tocar baseline F1C.
CONSUMER_OBSERVER = WF / "observador-reservas-consumidor.yml"
if CONSUMER_OBSERVER.is_file() and not CONSUMER_OBSERVER.is_symlink():
    EXPECTED_ACTIVE = EXPECTED_ACTIVE | frozenset({"observador-reservas-consumidor.yml"})
# Factory #1616: observador manual GET-only, añadido tras el ledger F1C.
RELEASE_OBSERVER = WF / "release-auto-observador.yml"
if RELEASE_OBSERVER.is_file() and not RELEASE_OBSERVER.is_symlink():
    EXPECTED_ACTIVE = EXPECTED_ACTIVE | frozenset({"release-auto-observador.yml"})
HARD_GATES = (
    "factory-ci.yml", "sonar.yml", "codeql-evidence.yml",
    "seguridad.yml", "costos.yml", "unattended-watchdog.yml",
    "coordinacion-trabajo.yml", "release.yml", "release-window.yml",
    "deploy.yml", "privacidad.yml",
)


class DietaFase1CTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = (ROOT / "docs" / "dieta-factory.md").read_text(encoding="utf-8")

    @staticmethod
    def actual() -> set[str]:
        return {p.name for ext in ("*.yml", "*.yaml") for p in WF.glob(ext) if p.is_file()}

    def test_sonar_watch_optional_workflow_removed_after_consumer_preflight(self):
        active = self.actual()
        self.assertEqual(active, EXPECTED_ACTIVE)
        self.assertEqual(len(active), len(EXPECTED_ACTIVE))
        self.assertNotIn(REMOVED, active)
        self.assertIn("122 YAML", self.document)
        self.assertIn("check requerido `Validar`", self.document)
        for name in sorted(active):
            content = (WF / name).read_text(encoding="utf-8")
            self.assertNotIn("sonar-watch.yml", content)
            self.assertNotIn("Sonar Watch", content)
            self.assertNotIn("sonar-watch.py", content)

    def test_sonar_gate_and_offline_engine_regressions_survive(self):
        for name in HARD_GATES:
            with self.subTest(name=name):
                self.assertIn(name, self.actual())
        for file in (
            ROOT / "scripts" / "sonar-watch.py",
            ROOT / "quality" / "sonar-watch-config.json",
            ROOT / "tests" / "test_sonar_watch.py",
        ):
            self.assertTrue(file.is_file(), file)
        source = (ROOT / "scripts" / "sonar-watch.py").read_text(encoding="utf-8")
        compile(source, "scripts/sonar-watch.py", "exec")
        ci = (WF / "factory-ci.yml").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests", ci)
        sonar_tests = (ROOT / "tests" / "test_sonar_watch.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"(?m)^    def test_", sonar_tests)), 30)
        self.assertIn("test_retired_workflow_and_offline_engine_are_preserved", sonar_tests)

    def test_scheduled_entrypoints_and_historical_diets_remain_consistent(self):
        self.assertNotIn("scripts/sonar-watch.py", EXPECTED)
        self.assertIn("scripts/sonar-watch.py", SAFE_ARGS)
        self.assertTrue((ROOT / "scripts" / "sonar-watch.py").is_file())
        case = ScheduledEntrypointTests("test_all_scheduled_python_path_entrypoints_are_import_safe")
        self.assertEqual(case._scheduled_paths(), EXPECTED)
        self.assertNotIn("scripts/sonar-watch.py", case._scheduled_paths())
        for token in ("38 workflows", "36 workflows", "35 workflows", "34 workflows"):
            self.assertIn(token, self.document)
        for ledger in ("## Ledger F1A", "## Ledger F1B", "## Ledger F1C"):
            self.assertIn(ledger, self.document)

    def test_sonar_watch_runbook_marks_scheduler_disabled_and_preserves_offline_qa(self):
        runbook = (ROOT / "docs" / "quality-sonar-watch.md").read_text(encoding="utf-8")
        self.assertNotIn(REMOVED, self.actual())
        for phrase in ("no se ejecuta automáticamente", "cron cada seis horas",
                       "workflow_dispatch", "desactivados",
                       "no se refrescan automáticamente", "#1052/#1053",
                       "Sonar CI-based", "CodeQL", "no sustituyen"):
            self.assertIn(phrase, runbook)
        for path in ("scripts/sonar-watch.py", "quality/sonar-watch-config.json",
                     "tests/test_sonar_watch.py"):
            self.assertIn(path, runbook)
            self.assertTrue((ROOT / path).is_file())
        self.assertNotIn("conserva `schedule` y `workflow_dispatch`", runbook)
        self.assertNotIn("Factory ejecuta vigilancia Sonar centralizada", runbook)

    def test_f1c_ledger_exact_only_one_deletion_and_reversible(self):
        section = self.document.split("## Ledger F1C de baja de Sonar Watch\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("main@" + BASE_SHA, section)
        expected_row = (
            "| F1C | `.github/workflows/" + REMOVED + "` | `" + BLOB_SHA
            + "` | 35 → 34 | squash-revert PR F1C |"
        )
        def verify_single_baja(document):
            # Cualquier segunda fila de datos (incluido id diferente) es inválida.
            rows = [
                line for line in document.splitlines()
                if line.startswith("| ") and not line.startswith("| Baja |")
                and not line.startswith("| ---")
            ]
            if rows != [expected_row]:
                raise AssertionError("Ledger F1C debe contener exactamente una baja autorizada")
        verify_single_baja(section)
        with self.assertRaises(AssertionError):
            verify_single_baja(section + "\n" + expected_row)
        with self.assertRaises(AssertionError):
            verify_single_baja(
                section + "\n| F1C | `.github/workflows/extra.yml` | `"
                + "0" * 40 + "` | 35 → 33 | squash-revert PR F1C |"
            )
        self.assertIn("cada seis horas", section)
        self.assertIn("Sonar CI-based", section)
        self.assertIn("squash-revert solo del PR F1C", section)
        self.assertIn("#1052/#1053", section)
        active = self.actual()
        self.assertEqual(active, EXPECTED_ACTIVE)
        victim = next(iter(sorted(active)))
        swapped = (active - {victim}) | {"workflow-no-autorizado.yml"}
        self.assertEqual(len(swapped), len(EXPECTED_ACTIVE))
        self.assertNotEqual(swapped, EXPECTED_ACTIVE)


if __name__ == "__main__":
    unittest.main()
