"""AC ejecutables de Factory#1297: inventario y poda reversible sin cambiar CI.

Este módulo solo lee el árbol del checkout, sin red ni credenciales.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "dieta-factory.md"
WORKFLOWS = ROOT / ".github" / "workflows"

PATH_REF = re.compile(r"(?:scripts|tests|metricas|producto)/[A-Za-z0-9_./-]+\.py")
WORKFLOW_ROW = re.compile(r"^\| `(\.github/workflows/[^\`]+\.ya?ml)` \|", re.MULTILINE)
REQUIRED_KEEP = {
    "ci.yml",
    "factory-ci.yml",
    "codeql-evidence.yml",
    "seguridad.yml",
    "sonar.yml",
    "auditoria-privacidad.yml",
    "privacidad.yml",
    "release.yml",
    "deploy.yml",
    "observar.yml",
    "liberar-reservas.yml",
    "coordinacion.yml",
    "costos.yml",
    "unattended-watchdog.yml",
}
REQUIRED_SIMPLIFY = {
    "politica.yml",
    "politica-comentario.yml",
    "release-bootstrap.yml",
    "release-window.yml",
    "coordinacion-trabajo.yml",
    "automerge-construccion.yml",
    "aceptacion.yml",
}


def inventory_rows(text: str) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for line in text.splitlines():
        if not line.startswith("| `.github/workflows/"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            raise AssertionError(f"Fila con columnas inesperadas: {line}")
        path = cells[0].strip("`")
        if path in result:
            raise AssertionError(f"Workflow duplicado: {path}")
        decision = cells[5].strip("*")
        result[path] = {
            "events": {event.strip() for event in cells[1].split(",")},
            "lines": int(cells[2]),
            "scripts": cells[3],
            "tests": cells[4],
            "decision": decision,
            "phase": int(cells[6]),
        }
    return result


def workflow_events(workflow: Path) -> set[str]:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.fullmatch(r"on:\s*", line))
    except StopIteration as exc:
        raise AssertionError(f"Sin bloque 'on': {workflow}") from exc
    found: set[str] = set()
    for line in lines[start + 1:]:
        if line and not line[0].isspace():
            break
        match = re.match(r"^  ([\w-]+):", line)
        if match:
            found.add(match.group(1))
    return found


class FactoryDietInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = DOC.read_text(encoding="utf-8")
        cls.rows = inventory_rows(cls.content)

    def test_inventory_lists_every_workflow_with_trigger_and_decision(self) -> None:
        actual = {
            path.relative_to(ROOT).as_posix()
            for extension in ("*.yml", "*.yaml")
            for path in WORKFLOWS.glob(extension)
            if path.is_file()
        }
        self.assertEqual(set(self.rows), actual, "Inventario obsoleto o incompleto")
        self.assertTrue(actual)
        for rel_path, row in self.rows.items():
            with self.subTest(workflow=rel_path):
                self.assertIn(row["decision"], {"quedarse", "simplificar", "eliminar"})
                self.assertEqual(row["events"], workflow_events(ROOT / rel_path))
                self.assertGreater(row["lines"], 0)
                # El recuento procede de un snapshot histórico, no del HEAD vivo.
                self.assertIn(row["phase"], {0, 1, 2, 3, 4})

    def test_historical_line_counts_are_provenance_not_immutable_runtime(self) -> None:
        """Un workflow puede crecer después del snapshot sin invalidar la tabla."""
        self.assertIn("main@b0713650194e9a0c464d625bc6136eecad776377", self.content)
        target = WORKFLOWS / "politica-comentario.yml"
        recorded = int(self.rows[target.relative_to(ROOT).as_posix()]["lines"])
        original_read_text = Path.read_text
        current = original_read_text(target, encoding="utf-8")
        # Diferencia deliberada aunque el workflow cambie en otros PRs futuros.
        future = current + "\n# Cambio futuro permitido" * (
            abs(recorded - len(current.split("\n"))) + 2
        )
        self.assertNotEqual(recorded, len(future.split("\n")))

        def read_with_future_edit(path: Path, *args: object, **kwargs: object) -> str:
            if path == target:
                return future
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", read_with_future_edit):
            self.test_inventory_lists_every_workflow_with_trigger_and_decision()

    def test_f1a_ledger_matches_exact_two_deletions(self) -> None:
        """F1A conserva la baseline y no encubre workflows desaparecidos."""
        baseline = "main@173519bde16498a796afd6a5af96b517d7e3a091"
        self.assertIn(baseline, self.content)
        self.assertIn("38 workflows", self.content)
        self.assertIn("36 workflows", self.content)
        self.assertIn("35 workflows", self.content)
        ledger = self.content.split("## Ledger F1A de bajas autorizadas\n", 1)[1].split(
            "\n## ", 1
        )[0]
        match = re.findall(
            r"^\| ([12]) \| \x60(\.github/workflows/[^\x60]+\.yml)\x60 \| "
            r"\x60([0-9a-f]{40})\x60 \| F1A / fase 1 \| "
            r"squash-revert PR F1A \| \x60([^\x60]+)\x60 \|$",
            ledger,
            flags=re.MULTILINE,
        )
        self.assertEqual(
            {path: (sha, suite) for _, path, sha, suite in match},
            {
                ".github/workflows/evolution-lab.yml": (
                    "645cd08c9d9f79e23e945f798d14b225eaf0e95d",
                    "tests/test_factory_lab_contract.py",
                ),
                ".github/workflows/feedback-producto.yml": (
                    "fe107d7f3a39a30d4fecefd0ca1c9ece68f5e490",
                    "tests/test_feedback_contract.py",
                ),
            },
        )
        self.assertEqual({number for number, *_ in match}, {"1", "2"})
        actual = {
            path.relative_to(ROOT).as_posix()
            for ext in ("*.yml", "*.yaml")
            for path in WORKFLOWS.glob(ext)
            if path.is_file()
        }
        baseline_paths = {
            ".github/workflows/aceptacion.yml",
            ".github/workflows/auditoria-privacidad.yml",
            ".github/workflows/automerge-construccion.yml",
            ".github/workflows/bootstrap-coordination.yml",
            ".github/workflows/cabina.yml",
            ".github/workflows/captura-leccion.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/codeql-evidence.yml",
            ".github/workflows/coordinacion-trabajo.yml",
            ".github/workflows/coordinacion.yml",
            ".github/workflows/costos.yml",
            ".github/workflows/deploy.yml",
            ".github/workflows/etiquetas-pr.yml",
            ".github/workflows/etiquetas.yml",
            ".github/workflows/evolution-lab.yml",
            ".github/workflows/factory-ci.yml",
            ".github/workflows/feedback-producto.yml",
            ".github/workflows/liberar-reservas.yml",
            ".github/workflows/metricas.yml",
            ".github/workflows/observar.yml",
            ".github/workflows/orquestador.yml",
            ".github/workflows/politica-comentario.yml",
            ".github/workflows/politica.yml",
            ".github/workflows/preview.yml",
            ".github/workflows/privacidad.yml",
            ".github/workflows/provision-project.yml",
            ".github/workflows/readme.yml",
            ".github/workflows/release-bootstrap.yml",
            ".github/workflows/release-window.yml",
            ".github/workflows/release.yml",
            ".github/workflows/reusable-release-watchdog.yml",
            ".github/workflows/reusable-selftest.yml",
            ".github/workflows/roles.yml",
            ".github/workflows/seguridad.yml",
            ".github/workflows/sonar-watch.yml",
            ".github/workflows/sonar.yml",
            ".github/workflows/sync-label-colors.yml",
            ".github/workflows/unattended-watchdog.yml",
        }
        removed = {path for _, path, _, _ in match}
        # Prueba el conjunto, no solo el cardinal y la tabla mutable.
        self.assertEqual(baseline_paths - removed - {".github/workflows/metricas.yml"}, actual)
        victim = next(path for path in sorted(actual) if path not in removed)
        unauthorized_swap = (actual - {victim}) | {
            ".github/workflows/trigger-no-autorizado.yml"
        }
        self.assertEqual(len(unauthorized_swap), len(actual))
        with self.assertRaises(AssertionError):
            self.assertEqual(baseline_paths - removed - {".github/workflows/metricas.yml"}, unauthorized_swap)
        self.assertEqual(len(actual), 35)
        self.assertEqual(set(self.rows), actual)
        self.assertEqual(len(actual) + len(match) + 1, 38)
        for _, path, _, suite in match:
            self.assertNotIn(path, actual)
            self.assertTrue((ROOT / suite).is_file())

    def test_every_removal_names_its_script_and_test_references(self) -> None:
        removals = {path: row for path, row in self.rows.items() if row["decision"] == "eliminar"}
        self.assertGreater(len(removals), 0)
        for path, row in removals.items():
            with self.subTest(workflow=path):
                self.assertIn(row["phase"], {1, 2}, "No borrar validadores de release/CI")
                self.assertTrue(row["scripts"])
                self.assertTrue(row["tests"])
                self.assertNotEqual(row["tests"], "ninguno")
                references = PATH_REF.findall(str(row["scripts"]) + " " + str(row["tests"]))
                self.assertTrue(references, "Debe listar pruebas/scripts exactos a revisar")
                for ref in references:
                    self.assertTrue((ROOT / ref).is_file(), f"Referencia ausente en {path}: {ref}")
                workflow_text = (ROOT / path).read_text(encoding="utf-8")
                direct_scripts = {
                    ref for ref in PATH_REF.findall(workflow_text)
                    if not ref.startswith("tests/")
                }
                documented_scripts = set(PATH_REF.findall(str(row["scripts"])))
                self.assertTrue(
                    direct_scripts.issubset(documented_scripts),
                    f"Dependencias directas sin inventariar en {path}: {direct_scripts - documented_scripts}",
                )
                phase_text = self._phase_text(int(row["phase"]))
                self.assertIn(f"`{path}`", phase_text)

    def test_hard_gates_and_quality_scanners_are_never_removed(self) -> None:
        for basename in REQUIRED_KEEP:
            with self.subTest(workflow=basename):
                self.assertEqual(
                    self.rows[f".github/workflows/{basename}"]["decision"], "quedarse"
                )
        for basename in REQUIRED_SIMPLIFY:
            with self.subTest(workflow=basename):
                self.assertEqual(
                    self.rows[f".github/workflows/{basename}"]["decision"], "simplificar"
                )
        for critical in (
            "CodeQL", "Sonar", "CodeRabbit", "gasto", "datos reales",
            "borrado", "deploy", "go-live", "#767",
        ):
            self.assertIn(critical, self.content)
        self.assertIn("No borrar", self.content)
        guarded_jobs = {
            "costos.yml": ("presupuesto-pr:", "metricas/costos.py pr", "ref: ${{ github.event.pull_request.base.sha }}"),
            "unattended-watchdog.yml": ("watchdog:", "daily-summary:", "scripts.unattended_watchdog_runtime", "scripts.unattended_daily_summary"),
        }
        for filename, tokens in guarded_jobs.items():
            with self.subTest(guard=filename):
                body = (WORKFLOWS / filename).read_text(encoding="utf-8")
                for token in tokens:
                    self.assertIn(token, body, f"{filename}: control perdido: {token}")
                self.assertEqual(
                    self.rows[f".github/workflows/{filename}"]["phase"], 0,
                    f"{filename}: no debe asignarse a una fase de borrado",
                )

    def test_phases_are_ordered_and_reversible(self) -> None:
        positions = [
            self.content.index(f"### Fase {n}:")
            for n in range(1, 5)
        ]
        self.assertEqual(positions, sorted(positions))
        seen: set[str] = set()
        for phase in range(1, 5):
            with self.subTest(phase=phase):
                section = self._phase_text(phase)
                self.assertIn("Rutas exactas:", section)
                self.assertIn("Reversión:", section)
                paths = set(re.findall(
                    r"`((?:\.github/workflows|scripts|tests|metricas|producto)/[^\`]+|PLAN-AGENTES\.md|agentes/NUCLEO\.md)`",
                    section,
                ))
                self.assertTrue(paths)
                for path in paths:
                    if not path.endswith(".py") and not path.endswith(".yml") and not path.endswith(".md"):
                        continue
                    self.assertTrue((ROOT / path).exists(), f"Ruta de fase {phase} ausente: {path}")
                # Se permiten menciones informativas como «no borrar» en otra fase;
                # la colisión prohibida es la doble asignación de workflows a eliminar/simplificar.
                edits = {path for path, row in self.rows.items() if row["phase"] == phase}
                self.assertFalse(seen & edits, "Workflow asignado a dos fases")
                seen.update(edits)
        self.assertIn("coordinación", self._phase_text(4).lower())
        self.assertEqual(
            seen,
            {path for path, row in self.rows.items() if row["phase"] in {1, 2, 3, 4}},
        )

    @classmethod
    def _phase_text(cls, phase: int) -> str:
        start = cls.content.index(f"### Fase {phase}:")
        end = cls.content.find("\n### Fase ", start + 1)
        if end < 0:
            end = cls.content.find("\n## ", start + 1)
        return cls.content[start:end if end >= 0 else None]


if __name__ == "__main__":
    unittest.main()
