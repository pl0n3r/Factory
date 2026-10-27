#!/usr/bin/env python3
"""Aceptación ejecutable del censo de requisitos Factory #1550."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
BASE_SHA = "8088e66c2366f2483d5229fc6fda8718f1ab46a0"
STATES = {"CUBIERTO", "EN_CURSO", "SIN_COBERTURA", "DESCARTADO", "NO_VERIFICABLE", "NO_APLICA"}
EPIC_AC = {304: 12, 305: 12, 1080: 4, 1082: 4, 1296: 0, 1382: 7}
ISSUE = re.compile(r"https://github\.com/pl0n3r/Factory/issues/(\d+)")
MODAL = re.compile(
    r"(debe|deben|deberá|requier|exig|obligat|prohib|nunca|solo|únicamente|"
    r"siempre|must|shall|fail.closed|falla cerr|no se|no puede|no acepta|"
    r"se rechaza|no autoriza|permite|valida|verifica|cierra|bloque|garantiza|"
    r"ningún|ninguna|al menos)", re.IGNORECASE
)
# Autenticación de estos PR MERGED y paths comprobada en GitHub al crear el corte.
VERIFIED = {
    "docs/factory-living-software.md:B01": (199, "445f41ca3858ba1726d6013d996763a68f5c05a4", "evolution/constitution.py", "tests/test_living_constitution.py"),
    "docs/factory-living-software.md:B02": (199, "445f41ca3858ba1726d6013d996763a68f5c05a4", "evolution/constitution.py", "tests/test_living_constitution.py"),
    "docs/factory-living-software.md:B03": (199, "445f41ca3858ba1726d6013d996763a68f5c05a4", "evolution/constitution.py", "tests/test_living_constitution.py"),
    "docs/factory-living-software.md:B04": (199, "445f41ca3858ba1726d6013d996763a68f5c05a4", "evolution/constitution.py", "tests/test_living_constitution.py"),
    "docs/dieta-factory.md:B02": (1304, "2e20aef7fd8b019c677acec37e18d711341662cc", ".github/workflows/factory-ci.yml", "tests/test_dieta_fase1a.py"),
    "docs/dieta-factory.md:B03": (1304, "2e20aef7fd8b019c677acec37e18d711341662cc", ".github/workflows/factory-ci.yml", "tests/test_factory_lab_contract.py"),
    "docs/factory-lab.md:B01": (210, "be8c5776e716d5115f2e9040e73ab1ecfd464851", "lab/factory_lab.py", "tests/test_factory_lab_contract.py"),
    "docs/factory-lab.md:B02": (210, "be8c5776e716d5115f2e9040e73ab1ecfd464851", "lab/factory_lab.py", "tests/test_factory_lab_contract.py"),
    "docs/factory-lab.md:B03": (291, "3e6b1640a780b94fd21ab99d4f17be18f3ca1d44", "lab/experiment_evidence.py", "tests/test_experiment_evidence.py"),
    "docs/factory-lab.md:B04": (219, "5f22c659288bd2013213a234f61eae285d7f8ed3", "lab/factory_lab.py", "tests/test_factory_lab_contract.py"),
    "docs/orquestador.md:L121-U1":
        (1414, "67994aafbb5d", "scripts/coordinar_trabajo.py",
         "tests/test_coordinar_trabajo.py"),
    "docs/performance-remediation.md:L25-U3":
        (1548, "9c12107bd64e", "performance/remediation.py",
         "tests/test_performance_remediation.py"),
    "docs/liberacion-automatica-de-reservas.md:L181-U1":
        (1515, "1072b8b26582", "scripts/lease_auto_release_integration.py",
         "tests/test_lease_hypothetical_action_preview.py"),
    "docs/recovery-status.md:L13-U1":
        (1528, "465bc1e711ea", "recovery/status.py",
         "tests/test_recovery_status.py"),
    "docs/arquitectura-tecnica.md:B01":
        (1414, "67994aafbb5d", "scripts/coordinar_trabajo.py",
         "tests/test_coordinar_trabajo.py"),
    "docs/admin-staff-api.md:B01":
        (186, "64f1901e456a", "template/ops/admin-staff-api.json",
         "tests/test_admin_staff_contract.py"),
    "docs/admin-staff-api.md:B02":
        (186, "64f1901e456a", "template/ops/admin-staff-api.json",
         "tests/test_admin_staff_contract.py"),
    "docs/admin-staff-api.md:B03":
        (186, "64f1901e456a", "template/ops/admin-staff-api.json",
         "tests/test_admin_staff_contract.py"),
    "docs/readme-progress-readiness.md:B01":
        (298, "73e63d68af7c", "readme/progress_readiness.py",
         "tests/test_readme_progress.py"),
    "docs/readme-progress-readiness.md:B02":
        (298, "73e63d68af7c", "readme/progress_readiness.py",
         "tests/test_readme_progress.py"),
    "docs/readme-progress-readiness.md:B03":
        (301, "3e47a229c2a1", "readme/progress_readiness.py",
         "tests/test_readme_progress_e2e.py"),
    "docs/readme-contract.md:B01":
        (1025, "2dc5a8d0b2a6", "readme/validate_readme.py",
         "tests/test_readme_contract_v2.py"),
    "docs/readme-contract.md:B02":
        (1025, "2dc5a8d0b2a6", "readme/validate_readme.py",
         "tests/test_readme_contract_v2.py"),
    "docs/unattended-safe-mode.md:B01": (747, "073b46e8e0a0bd81b081f0b6a678e2681a088d68", "scripts/unattended_guards.py", "tests/test_unattended_guards.py"),
    "docs/unattended-safe-mode.md:B02": (754, "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e", "scripts/unattended_watchdog.py", "tests/test_unattended_watchdog.py"),
    "docs/unattended-runtime-guards.md:B01": (747, "073b46e8e0a0bd81b081f0b6a678e2681a088d68", "scripts/unattended_guards.py", "tests/test_unattended_guards.py"),
    "docs/unattended-runtime-guards.md:B02": (750, "a06303d528c9c2065b9f14829c6a7489a6c96529", "scripts/unattended_guards.py", "tests/test_unattended_guards.py"),
    "docs/unattended-runtime-guards.md:B03": (747, "073b46e8e0a0bd81b081f0b6a678e2681a088d68", "scripts/unattended_guards.py", "tests/test_unattended_guards.py"),
    "docs/unattended-runtime-guards.md:B04": (747, "073b46e8e0a0bd81b081f0b6a678e2681a088d68", "scripts/unattended_guards.py", "tests/test_unattended_guards.py"),
    "docs/unattended-daily-summary.md:B01": (789, "6c69a6cfd594ce5ba7617e2b0c22257045b2e477", "scripts/unattended_daily_summary.py", "tests/test_unattended_daily_summary.py"),
    "docs/unattended-daily-summary.md:B02": (789, "6c69a6cfd594ce5ba7617e2b0c22257045b2e477", "scripts/unattended_daily_summary.py", "tests/test_unattended_daily_summary.py"),
    "docs/unattended-daily-summary.md:B03": (911, "b233504ec6c03449a37677353bac59a24e88efac", "scripts/unattended_daily_summary.py", "tests/test_unattended_daily_summary.py"),
    "docs/unattended-watchdog.md:B01": (754, "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e", "scripts/unattended_watchdog.py", "tests/test_unattended_watchdog.py"),
    "docs/unattended-watchdog.md:B02": (754, "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e", "scripts/unattended_watchdog.py", "tests/test_unattended_watchdog.py"),
    "docs/unattended-watchdog.md:B03": (754, "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e", "scripts/unattended_watchdog.py", "tests/test_unattended_watchdog.py"),
    "docs/unattended-watchdog.md:B04": (754, "e1509bfe9d133d0dda58ecb3f898201d5ccdc53e", "scripts/unattended_watchdog.py", "tests/test_unattended_watchdog.py"),
    "docs/unattended-watchdog-runtime.md:B01": (786, "2964992a8833e10627e353132c24358ecce99de9", "scripts/unattended_watchdog_runtime.py", "tests/test_unattended_watchdog_runtime.py"),
    "docs/unattended-watchdog-runtime.md:B02": (786, "2964992a8833e10627e353132c24358ecce99de9", "scripts/unattended_watchdog_runtime.py", "tests/test_unattended_watchdog_runtime.py"),
    "docs/aceptacion-ejecutable.md:L49-U1": (926, "2644eb1be4e8d9106fe00e026a5b7c17eb94079a", "scripts/aceptacion_kit.py", "tests/test_aceptacion_kit.py"),
    "docs/adaptive-orchestration.md:L15-U1": (287, "49703d7138e6da759f911a625239c270164b777d", "scripts/presence_contract.py", "tests/test_presence_contract.py"),
    "docs/ai-gateway.md:L3-U1": (288, "e58a6c68bf8e2490db31b1495a80e3cf7d702d71", "intelligence/ai_gateway.py", "tests/test_ai_gateway.py"),
    "docs/ai-gateway.md:L9-U1": (288, "e58a6c68bf8e2490db31b1495a80e3cf7d702d71", "intelligence/ai_gateway.py", "tests/test_ai_gateway.py"),
    "docs/ai-gateway.md:L11-U1": (288, "e58a6c68bf8e2490db31b1495a80e3cf7d702d71", "intelligence/ai_gateway.py", "tests/test_ai_gateway.py"),
    "docs/ai-gateway.md:L11-U2": (288, "e58a6c68bf8e2490db31b1495a80e3cf7d702d71", "intelligence/ai_gateway.py", "tests/test_ai_gateway.py"),
    "docs/ai-gateway.md:L15-U1": (288, "e58a6c68bf8e2490db31b1495a80e3cf7d702d71", "intelligence/ai_gateway.py", "tests/test_ai_gateway.py"),
    "docs/autonomy-engine.md:L8-U1": (207, "729f4de7a7fc68fa679c4ef7b59728a65243974b", "evolution/autonomy.py", "tests/test_autonomy_engine.py"),
    "docs/autonomy-engine.md:L30-U1": (207, "729f4de7a7fc68fa679c4ef7b59728a65243974b", "evolution/autonomy.py", "tests/test_autonomy_engine.py"),
    "docs/capability-authority.md:L5-U1": (289, "f0f16e1d8e3e8d943da0998468551379df70cd9f", "evolution/capability_authority.py", "tests/test_capability_authority.py"),
    "docs/capability-authority.md:L19-U1": (289, "f0f16e1d8e3e8d943da0998468551379df70cd9f", "evolution/capability_authority.py", "tests/test_capability_authority.py"),
    "docs/context-compiler.md:L17-U1": (203, "e6949df35b7f13dda5fdf2b34a427a8d6f352936", "intelligence/context_compiler.py", "tests/test_context_compiler.py"),
    "docs/context-compiler.md:L23-U1": (203, "e6949df35b7f13dda5fdf2b34a427a8d6f352936", "intelligence/context_compiler.py", "tests/test_context_compiler.py"),
    "docs/conversacion-agentes.md:L7-U1": (303, "4952bac3b22cb17934c507663cf0b8e7c4d8963e", "agentes/NUCLEO.md", "tests/test_conversacion_agentes.py"),
    "docs/coordinacion-pr-validation.md:L14-U1": (788, "a1726510557dd398ec2b15dff5739439e67e606e", ".github/workflows/coordinacion-trabajo.yml", "tests/test_coordinacion_reusable_contract.py"),
    "docs/organizational-complexity.md:L44-U1": (338, "7b129a43915959ab206afa089eb5f380383e0c3a", "metricas/organizational_complexity.py", "tests/test_organizational_complexity.py"),
    "docs/organizational-complexity.md:L55-U1": (338, "7b129a43915959ab206afa089eb5f380383e0c3a", "metricas/organizational_complexity.py", "tests/test_organizational_complexity.py"),
    "docs/performance-ci-suite-benchmark.md:L7-U3": (1502, "5d89679ff6498fd5f61867ef7c71891e7a26e262", "performance/ci_suite_benchmark.py", "tests/test_performance_ci_suite_benchmark.py"),
    "docs/performance-ci-suite-benchmark.md:L16-U1": (1502, "5d89679ff6498fd5f61867ef7c71891e7a26e262", "performance/ci_suite_benchmark.py", "tests/test_performance_ci_suite_benchmark.py"),
    "docs/performance-classification.md:L9-U1": (650, "32be91dc654ff2318c0b342168e7e50b9a298258", "performance/classifier.py", "tests/test_performance_classifier.py"),
    "docs/performance-contract.md:L17-U1": (314, "756c7a613681b9c91417981e397ec46e56ae414d", "performance/contract.py", "tests/test_performance_contract.py"),
    "docs/performance-contract.md:L14-U1": (314, "756c7a613681b9c91417981e397ec46e56ae414d", "performance/contract.py", "tests/test_performance_contract.py"),
    "docs/performance-detection.md:L10-U1": (316, "ebfb56d7164eb337e7519c2209785572ddd2dffb", "performance/detector.py", "tests/test_performance_detector.py"),
    "docs/performance-detection.md:L14-U1": (316, "ebfb56d7164eb337e7519c2209785572ddd2dffb", "performance/detector.py", "tests/test_performance_detector.py"),
    "docs/performance-github-actions-ci.md:L9-U2": (1498, "0b910998cba15c6e93a2b636c9ad59ccc6d4017d", "performance/github_actions_ci.py", "tests/test_performance_github_actions_ci.py"),
    "docs/performance-remediation.md:L15-U1": (1531, "669b1ef512ba5f080831bf01d703d01fb2bd34e6", "performance/remediation.py", "tests/test_performance_remediation.py"),
    "docs/performance-remediation.md:L23-U1": (1531, "669b1ef512ba5f080831bf01d703d01fb2bd34e6", "performance/remediation.py", "tests/test_performance_remediation.py"),
    "docs/portfolio-signals.md:L40-U1": (339, "7e9062203f3faae85a6dfc6fc9cb446d4faaf71e", "portfolio/signals.py", "tests/test_portfolio_signals.py"),
    "docs/portfolio-signals.md:L33-U1": (339, "7e9062203f3faae85a6dfc6fc9cb446d4faaf71e", "portfolio/signals.py", "tests/test_portfolio_signals.py"),
}


def normative_units(path: Path) -> dict[str, str]:
    """Una unidad identificable por cláusula, no por título o README."""
    name = path.relative_to(ROOT).as_posix()
    output = {}
    fence = False
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^\s*(\x60{3}|~{3})", line):
            fence = not fence
            continue
        if fence or re.match(r"^\s*(#|\||<!--|</|<details|<summary)", line):
            continue
        value = re.sub(r"^>\s*", "", line.strip())
        bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.*)$", value)
        if bullet:
            value = bullet.group(1)
        if not value or re.match(r"^\[[^\]]+\]\(#[^)]+\)", value):
            continue
        unit = 0
        for piece in re.split(r";\s+|(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ])", value):
            piece = piece.strip()
            if len(piece) < 12 or (not bullet and not MODAL.search(piece)):
                continue
            unit += 1
            output[f"{name}:L{line_no}-U{unit}"] = piece
    return output


def parse_rows(doc: str) -> list[dict[str, str]]:
    if doc.count("## Filas de cobertura") != 1:
        raise ValueError("Sección de requisitos ausente o duplicada")
    part = doc.split("## Filas de cobertura", 1)[1]
    if "## Producción y mejoras pendientes" not in part:
        raise ValueError("La tabla no está delimitada")
    part = part.split("## Producción y mejoras pendientes", 1)[0]
    found, used = [], set()
    for line in part.splitlines():
        if not line.startswith("| ") or line.startswith(("| ID de requisito", "| ---")):
            continue
        values = [v.strip() for v in re.split(r"(?<!\\)\|", line)]
        if len(values) != 7 or values[0] or values[-1]:
            raise ValueError("Fila sin cinco columnas")
        key, desc, state, evidence, issue = values[1:-1]
        if not all((key, desc, state, evidence, issue)):
            raise ValueError("Celda vacía")
        if not (key.startswith(chr(96)) and key.endswith(chr(96))):
            raise ValueError("ID sin formato literal")
        key = key[1:-1]
        if key in used:
            raise ValueError("Requisito duplicado: " + key)
        used.add(key)
        if state not in STATES:
            raise ValueError("Estado inválido: " + state)
        found.append(dict(id=key, state=state, desc=desc,
                          evidence=evidence, issue=issue))
    if not found:
        raise ValueError("No hay requisitos")
    return found


def new_leaf_registry(doc: str) -> set[int]:
    part = doc.split("## Registro de hojas SIN_COBERTURA", 1)[1]
    part = part.split("## Resumen verificable", 1)[0]
    result = set()
    for line in part.splitlines():
        if line.startswith("| [#"):
            matches = ISSUE.findall(line)
            if len(matches) != 1:
                raise ValueError("Hoja no canónica")
            result.add(int(matches[0]))
    return result


def check_statuses(rows: list[dict[str, str]], registry: set[int]) -> None:
    for item in rows:
        state, issue, evidence, key = (
            item["state"], item["issue"], item["evidence"], item["id"]
        )
        if state == "SIN_COBERTURA":
            linked = [int(x) for x in ISSUE.findall(issue)]
            if len(linked) != 1 or linked[0] not in registry or linked[0] == 1550:
                raise ValueError("SIN_COBERTURA sin hoja real registrada")
        elif state == "EN_CURSO":
            if ("Épico" in issue or "EPIC" in issue or
                    not ISSUE.search(issue)):
                raise ValueError("Un épico no prueba que el trabajo sea ejecutable")
        elif state == "CUBIERTO":
            info = VERIFIED.get(key)
            if info is None:
                raise ValueError("Cobertura sin verificación externa")
            pr, merge_sha, code, test = info
            if (f"/pull/{pr}" not in evidence or merge_sha not in evidence or
                    code not in evidence or test not in evidence or
                    not (ROOT / code).is_file() or not (ROOT / test).is_file()):
                raise ValueError("CUBIERTO sin código, test o PR fusionado pertinente")


def inventory(doc: str) -> dict[str, int]:
    section = doc.split("## Inventario de fuentes", 1)[1]
    section = section.split("## Filas de cobertura", 1)[0]
    pattern = re.compile(
        r"^\| " + chr(96) + r"([^" + chr(96) + r"]+)" +
        chr(96) + r" \| (\d+) \|$"
    )
    result = {}
    for line in section.splitlines():
        match = pattern.fullmatch(line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def pinned_sources(doc: str, available: set[str] | None = None) -> list[str]:
    """Auditar solo las fuentes del corte declarado; cambios nuevos no reescriben historia."""
    names = set(inventory(doc))
    if available is None:
        available = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "docs").glob("*.md")
        } | {"AGENTES.md"}
    missing = names - set(available)
    if missing:
        raise ValueError("Falta fuente auditada en snapshot: " + sorted(missing)[0])
    return sorted(names)


class MatrizCoberturaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = MATRIX.read_text(encoding="utf-8")
        cls.rows = parse_rows(cls.doc)

    def test_cubre_todas_las_fuentes(self) -> None:
        expected, census = {}, {}
        # El censo de #1550 es un snapshot del SHA BASE_SHA, no una regla
        # para prohibir nuevas hojas documentales añadidas en otro PR.
        docs = [ROOT / name for name in pinned_sources(self.doc)
                if name.startswith("docs/")]
        self.assertEqual(len(docs), 103)
        for path in [*docs, ROOT / "AGENTES.md"]:
            items = normative_units(path)
            census[path.relative_to(ROOT).as_posix()] = len(items)
            expected.update(items)
        self.assertEqual(census, inventory(self.doc))
        for epic, count in EPIC_AC.items():
            for n in range(1, count + 1):
                expected[f"ISSUE-{epic}:AC-{n:02d}"] = "Epic AC"
        # #1561 y #1562 migran solo siete fuentes del censo antiguo a comportamientos;
        # el inventario anclado a #1550 y las 97 fuentes restantes no se alteran.
        migrated = (
            "docs/inventario-tecnico-datos-productos.md",
            "docs/arquitectura-tecnica.md",
            "docs/admin-staff-api.md",
            "docs/auditoria-pre-v1.md",
            "docs/release-bootstrap.md",
            "docs/readme-progress-readiness.md",
            "docs/readme-contract.md",
            "docs/unattended-safe-mode.md",
            "docs/unattended-runtime-guards.md",
            "docs/unattended-daily-summary.md",
            "docs/unattended-watchdog.md",
            "docs/unattended-watchdog-runtime.md",
            "docs/factory-living-software.md",
            "docs/factoryrunner-execution-plane.md",
            "docs/dieta-factory.md",
            "docs/factory-lab.md",
        )
        expected = {key: value for key, value in expected.items()
                    if not any(key.startswith(source + ":L") for source in migrated)}
        contract = (ROOT / "docs/contraste-matriz-datos_arq.md").read_text(encoding="utf-8")
        behaviors = [line.split("`", 2)[1] for line in contract.splitlines()
                     if line.startswith("| `docs/") and ":B" in line.split("`", 2)[1]]
        self.assertEqual(len(behaviors), 11)
        expected.update({key: "Comportamiento contrastado" for key in behaviors})
        contract_prev1 = (ROOT / "docs/contraste-matriz-prev1_release.md").read_text(encoding="utf-8")
        behaviors_prev1 = [line.split("`", 2)[1] for line in contract_prev1.splitlines()
                           if line.startswith("| `docs/") and ":B" in line.split("`", 2)[1]]
        self.assertEqual(len(behaviors_prev1), 17)
        expected.update({key: "Comportamiento contrastado" for key in behaviors_prev1})
        unattended = (ROOT / "docs/contraste-matriz-unattended.md").read_text(encoding="utf-8")
        unattended_ids = [line.split(chr(96), 2)[1] for line in unattended.splitlines()
                          if line.startswith("| " + chr(96) + "docs/unattended-")
                          and ":B" in line.split(chr(96), 2)[1]]
        self.assertEqual(len(unattended_ids), 20)
        expected.update({key: "Comportamiento contrastado" for key in unattended_ids})
        living = (ROOT / "docs/contraste-matriz-living_runner.md").read_text(encoding="utf-8")
        living_ids = [line.split(chr(96), 2)[1] for line in living.splitlines()
                      if line.startswith("| " + chr(96) + "docs/") and
                      ":B" in line.split(chr(96), 2)[1]]
        self.assertEqual(len(living_ids), 23)
        expected.update({key: "Comportamiento contrastado" for key in living_ids})
        actual = {row["id"] for row in self.rows}
        self.assertEqual(actual, set(expected))
        self.assertIn("AGENTES.md:L34-U2", expected)
        self.assertNotEqual(actual - {"AGENTES.md:L34-U2"}, set(expected))

    def test_snapshot_ignora_solo_fuentes_posteriores(self) -> None:
        """Un nuevo documento no cambia el censo viejo; una fuente perdida sí falla."""
        baseline = set(pinned_sources(self.doc))
        self.assertIn("AGENTES.md", baseline)
        self.assertNotIn("docs/matriz-cobertura.md", baseline)
        self.assertNotIn("docs/continuidad-caida-proveedores.md", baseline)
        self.assertEqual(len([p for p in baseline if p.startswith("docs/")]), 103)

        with_future = baseline | {"docs/continuidad-caida-proveedores.md"}
        self.assertEqual(set(pinned_sources(self.doc, with_future)), baseline)
        with self.assertRaisesRegex(ValueError, "Falta fuente auditada"):
            pinned_sources(self.doc, baseline - {"docs/lista-salida-produccion.md"})

    def test_sin_cobertura_tiene_issue(self) -> None:
        registry = new_leaf_registry(self.doc)
        check_statuses(self.rows, registry)
        actual = {r["id"] for r in self.rows if r["state"] == "CUBIERTO"}
        self.assertEqual(actual, set(VERIFIED))
        fake = [dict(self.rows[0], state="SIN_COBERTURA",
                     issue="[Épico #304](https://github.com/pl0n3r/Factory/issues/304)")]
        with self.assertRaises(ValueError):
            check_statuses(fake, registry)

    def test_formato_y_estados(self) -> None:
        self.assertGreater(len(self.rows), 100)
        first = next(line for line in self.doc.splitlines()
                     if line.startswith("| " + chr(96) + "docs/"))
        with self.assertRaises(ValueError):
            parse_rows("## Filas de cobertura\n" +
                       first.replace("NO_VERIFICABLE", "IMAGINARIO", 1) +
                       "\n## Producción y mejoras pendientes")
        with self.assertRaises(ValueError):
            parse_rows("## Filas de cobertura\n" + first + "\n" + first +
                       "\n## Producción y mejoras pendientes")

    def test_resumen_por_estado(self) -> None:
        counts = Counter(row["state"] for row in self.rows)
        part = self.doc.split("## Resumen verificable", 1)[1]
        for state in STATES:
            match = re.search(rf"^\| {state} \| (\d+) \|$", part, re.MULTILINE)
            self.assertIsNotNone(match)
            self.assertEqual(int(match.group(1)), counts[state])
        total = re.search(r"^\| TOTAL \| (\d+) \|$", part, re.MULTILINE)
        self.assertIsNotNone(total)
        self.assertEqual(int(total.group(1)), len(self.rows))
        pct = re.search(
            r"\*\*Porcentaje CUBIERTO:\*\* (\d+\.\d{2})% \((\d+)/(\d+)\)\.",
            part
        )
        self.assertIsNotNone(pct)
        self.assertEqual(int(pct.group(2)), counts["CUBIERTO"])
        self.assertEqual(int(pct.group(3)), len(self.rows))
        self.assertEqual(float(pct.group(1)),
                         round(100 * counts["CUBIERTO"] / len(self.rows), 2))
        new = re.search(r"\*\*Hojas nuevas creadas:\*\* (\d+)\.", part)
        self.assertIsNotNone(new)
        self.assertEqual(int(new.group(1)), len(new_leaf_registry(self.doc)))
        self.assertIn("main@" + BASE_SHA, self.doc)


if __name__ == "__main__":
    unittest.main()
