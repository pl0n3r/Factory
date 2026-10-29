"""Factory #1619: 16 brechas de coordinación, release y construcción.

Tests offline sintéticos; no demuestran autoridad humana, permisos, release,
propagación real a consumidores ni habilitan la Fase B. Esas brechas son UNKNOWN.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from scripts.aceptacion_kit import AcceptanceError, parse_contract
from scripts.coordinar_trabajo import (
    CoordinationError, parse_comment_command, reservation_from_pr_body,
)
from scripts.lease_auto_release_run import (
    evaluate_phase_a_candidate, observe_recent_activity, run_cycle,
)
from scripts.orquestador_kit import claims_overlap
from scripts.release_bootstrap import ReleaseBootstrapError, validate_payload
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
UUID = "11111111-2222-4333-8444-555555555555"
IDS = tuple(f"AGENTES.md:B0{i}" for i in range(1, 5)) + tuple(
    f"ISSUE-{number}:AC-0{criterion}"
    for number in (1080, 1082, 1382)
    for criterion in range(1, 5)
)
# Los guards locales no prueban el predicado extremo a extremo de ninguna fila.
GAPS = {
    "AGENTES.md:B01": "recibo V3, PR y Validar exact-SHA vivos son externos",
    "AGENTES.md:B02": "adopción en todos los callers no auditada",
    "AGENTES.md:B03": "tag v1 y aprobación OWNER no verificables offline",
    "AGENTES.md:B04": "roles/revisión cruzada de cada PR no acreditados",
    "ISSUE-1080:AC-01": "release autónomo sin puerta humana no demostrado",
    "ISSUE-1080:AC-02": "puertas de fase live y maquinaria no probadas en runtime",
    "ISSUE-1080:AC-03": "release automático detenido por switch no observado",
    "ISSUE-1080:AC-04": "rollback de v1 no ejecutado ni autorizado",
    "ISSUE-1082:AC-01": "principios escritos no prueban adopción real",
    "ISSUE-1082:AC-02": "sync de los seis consumidores no verificado",
    "ISSUE-1082:AC-03": "incidente real por cola vacía/cuota no acreditado",
    "ISSUE-1082:AC-04": "normalizador en consumidores no verificado",
    "ISSUE-1382:AC-01": "24 h/100 ciclos y censo autenticado insuficientes",
    "ISSUE-1382:AC-02": "lock y cuota API reales no acreditados en Fase B",
    "ISSUE-1382:AC-03": "paginación/carreras de fuentes reales no acreditadas",
    "ISSUE-1382:AC-04": "Fase A solo informa, no autoriza liberaciones",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Rechaza ausencia, duplicados, columnas ambiguas y promoción sin pruebas."""
    if type(raw) is not str:
        raise ValueError("matriz ilegible")
    found: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        if not cells or cells[0].strip(chr(96)) not in IDS:
            continue
        unit = cells[0].strip(chr(96))
        if unit in found or len(cells) != 5 or not all(cells):
            raise ValueError(f"fila ambigua: {unit}")
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError(f"promoción sin evidencia: {unit}")
        found[unit] = cells
    if set(found) != set(IDS):
        raise ValueError("filas ausentes")
    return found


def verdicts(matrix: object, evidence: object) -> dict[str, str]:
    unknown = dict.fromkeys(IDS, UNKNOWN)
    try:
        matrix_rows(matrix)
    except ValueError:
        return unknown
    if (type(evidence) is not dict or set(evidence) != set(IDS)
            or any(type(value) is not bool for value in evidence.values())):
        return unknown
    return {unit: UNKNOWN if unit in GAPS or not evidence[unit]
            else "OFFLINE_VERIFIED" for unit in IDS}


def local_evidence() -> dict[str, bool]:
    """Ejercita código real sin consultas de red ni efectos remotos."""
    agents = read("AGENTES.md")
    reusable = read(".github/workflows/ci.yml")
    release = read("docs/release-bootstrap.md")
    principles = read("docs/principios-construccion.md")
    template = read("template/AGENTES.md")
    scheduled = read(".github/workflows/liberar-reservas.yml")

    command = parse_comment_command("/tomar")
    reservation = reservation_from_pr_body(
        f"Closes #1619\n<!-- condor-reserva-id: {UUID} -->"
    )
    phase_a = evaluate_phase_a_candidate(
        [], [], [], repository="pl0n3r/Factory",
    )
    observation = observe_recent_activity([], None, now=None)
    disabled = run_cycle([1619], None)
    pause = evaluate_unattended_kill_switch(None)

    return {
        "AGENTES.md:B01": (
            command == ("tomar", None) and reservation == UUID
            and chr(96) + "trabajo/issue-N" + chr(96) in agents
            and "**" + chr(96) + "Validar" + chr(96) + "**" in agents
        ),
        "AGENTES.md:B02": (
            "event_guard:" in reusable
            and "Rechazar eventos privilegiados" in reusable
            and "pull_request|push|merge_group" in reusable
            and "cache-mode: read" in reusable
        ),
        "AGENTES.md:B03": (
            "vN.M.P" in agents and "factory-release" in release
            and "SHA exacto" in release
        ),
        "AGENTES.md:B04": (
            "aceptación ejecutable" in agents
            and "Uso eficiente de Remote Desktop Commander" in agents
            and (ROOT / "agentes/roles/ingenieria-software.md").is_file()
            and (ROOT / "agentes/roles/qa.md").is_file()
        ),
        "ISSUE-1080:AC-01": "v1" in release,
        "ISSUE-1080:AC-02": "/decidir A" in release,
        "ISSUE-1080:AC-03": pause.global_pause and pause.state == UNKNOWN,
        "ISSUE-1080:AC-04": "rollback" in release.lower(),
        "ISSUE-1082:AC-01": all(
            f"## Principio {i} " in principles for i in range(1, 9)
        ),
        "ISSUE-1082:AC-02": "Principios de construcción" in template,
        "ISSUE-1082:AC-03": (
            "cola" in principles and "rate" in principles.lower()
        ),
        "ISSUE-1082:AC-04": (
            claims_overlap("tests/", "tests/candidato.py")
            and not claims_overlap("tests/uno.py", "tests/dos.py")
        ),
        "ISSUE-1382:AC-01": (
            phase_a.status == "invalid_evidence"
            and not phase_a.release_authorized
        ),
        "ISSUE-1382:AC-02": (
            disabled.state == "feature_disabled"
            and "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'" in scheduled
        ),
        "ISSUE-1382:AC-03": (
            observation.state == "invalid_input"
            and not observation.release_authorized
        ),
        "ISSUE-1382:AC-04": (
            not observation.release_authorized
            and not phase_a.release_authorized
        ),
    }


class BrechasFactory01Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read("docs/matriz-cobertura.md")
        found = matrix_rows(matrix)
        evidence = local_evidence()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        self.assertEqual(set(found), set(IDS))
        self.assertEqual(set(evidence), set(IDS))
        self.assertEqual(set(GAPS), set(IDS))
        result = verdicts(matrix, evidence)
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(found[unit][2], "NO_VERIFICABLE")
                self.assertTrue(evidence[unit], f"Guard local roto: {unit}")
                self.assertTrue(GAPS[unit])
                self.assertEqual(result[unit], UNKNOWN)

    def test_falla_cerrado(self):
        matrix = read("docs/matriz-cobertura.md")
        row = next(line for line in matrix.splitlines()
                   if f"{chr(96)}{IDS[0]}{chr(96)}" in line)
        for broken in (
            None, "", matrix.replace(row, "", 1), matrix + "\n" + row,
            matrix.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO", 1)),
            matrix.replace(row, row.rpartition(" | ")[0] + " |  |", 1),
        ):
            with self.subTest(sample=str(broken)[:35]):
                with self.assertRaises(ValueError):
                    matrix_rows(broken)
                self.assertEqual(
                    set(verdicts(broken, local_evidence()).values()), {UNKNOWN},
                )
        for invalid in (
            None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
            {**dict.fromkeys(IDS, True), "EXTRA": True},
        ):
            self.assertEqual(set(verdicts(matrix, invalid).values()), {UNKNOWN})
        with self.assertRaises(CoordinationError):
            parse_comment_command("/tomar --force")
        with self.assertRaises(ReleaseBootstrapError):
            validate_payload({})
        with self.assertRaises(AcceptanceError):
            parse_contract("### Criterios de aceptación\n- [ ] [AC-01] X")

    def test_sin_datos_reales(self):
        source = read("tests/test_brechas_factory_01.py")
        tree = ast.parse(source)
        modules = {
            node.module or ""
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        } | {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        self.assertFalse(any(
            name == forbidden or name.startswith(forbidden + ".")
            for name in modules
            for forbidden in ("requests", "urllib", "subprocess", "httpx")
        ))
        self.assertEqual(
            reservation_from_pr_body(
                f"<!-- condor-reserva-id: {UUID} -->"
            ), UUID,
        )
        self.assertFalse(evaluate_phase_a_candidate(
            [], [], [], repository="pl0n3r/Factory",
        ).release_authorized)

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        evidence = local_evidence()
        self.assertTrue(all(evidence.values()))
        self.assertEqual(set(verdicts(matrix, evidence).values()), {UNKNOWN})
        evidence["ISSUE-1080:AC-01"] = False
        self.assertEqual(set(verdicts(matrix, evidence).values()), {UNKNOWN})
        self.assertTrue(evaluate_unattended_kill_switch(None).global_pause)
        self.assertEqual(
            observe_recent_activity([], None, now=None).state, "invalid_input",
        )


if __name__ == "__main__":
    unittest.main()
