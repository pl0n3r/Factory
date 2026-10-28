"""Factory #1650: pruebas offline de brechas de release y Living Software.

Las aserciones positivas son estrictamente locales/históricas. Los efectos
externos, cuentas, respaldos, go-live y publicación siguen UNKNOWN.
"""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from recovery.contract import RecoveryContractError, validate_recovery_manifest
from scripts import release_window

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
CHECKLIST = "docs/lista-salida-produccion.md"
LIVING = "docs/living-software-operational-e2e.md"
MATRIX = "docs/matriz-cobertura.md"
MANIFEST = "feedback/data/living-software-operational-e2e.json"

UNIT_NEEDLES = {
    f"{CHECKLIST}:L83-U1": "3-2-1-1-0 auténtico / RPO/RTO",
    f"{CHECKLIST}:L83-U2": "el contrato offline no los acredita",
    f"{CHECKLIST}:L84-U1": "OWNER debe abrir ventana protegida",
    f"{CHECKLIST}:L84-U2": "un PR verde no publica",
    f"{CHECKLIST}:L85-U1": "recepción efectiva de alertas",
    f"{CHECKLIST}:L86-U1": "cada consumidor debe acreditar HTTPS",
    f"{CHECKLIST}:L87-U1": "hoja #1553 cubre el procedimiento fail-closed",
    f"{CHECKLIST}:L87-U2": "permanecen " + chr(96) + "SIN_COBERTURA" + chr(96),
    f"{CHECKLIST}:L88-U1": "no provisionar B2",
    f"{CHECKLIST}:L9-U1": "Fuentes:",
    f"{CHECKLIST}:L9-U2": "El observador real de cada consumidor",
    f"{CHECKLIST}:L90-U1": "no constituye una declaración de "
                          + chr(96) + "VALIDATED_IN_PRODUCTION" + chr(96),
    f"{LIVING}:L10-U1": "36507097760",
    f"{LIVING}:L11-U1": "36507219161",
    f"{LIVING}:L12-U1": "36507269422",
    f"{LIVING}:L14-U1": "validar acceptance contract + available state + factory-plan-task",
}
GAPS = {
    f"{CHECKLIST}:L83-U1": "UNKNOWN: sin offsite D-066 y restore/RPO/RTO medidos",
    f"{CHECKLIST}:L83-U2": "UNKNOWN: manifiesto offline no prueba restore externo",
    f"{CHECKLIST}:L84-U1": "UNKNOWN: sin decisión OWNER y release exact-SHA ejecutados",
    f"{CHECKLIST}:L84-U2": "UNKNOWN: CI verde no autoriza mover Factory@v1",
    f"{CHECKLIST}:L85-U1": "UNKNOWN: faltan recibos reales de alertas, SLA, smoke y restore",
    f"{CHECKLIST}:L86-U1": "UNKNOWN: falta observación HTTPS/legal por consumidor",
    f"{CHECKLIST}:L87-U1": "UNKNOWN: el runbook #1553 no prueba contingencia ejecutada",
    f"{CHECKLIST}:L87-U2": "UNKNOWN: falta integración exact-main por unidad",
    f"{CHECKLIST}:L88-U1": "UNKNOWN: sin autorización ni recibos de gasto/credenciales",
    f"{CHECKLIST}:L9-U2": "UNKNOWN: observadores reales no consultados",
}
RUN_IDS = (36507015627, 36507097760, 36507219161, 36507269422)
RUN_EFFECTS = (
    ("failure", "acceptance_contract_rejected"),
    ("success", "no_reservation_missing_available_state"),
    ("failure", "unplanned_parallel_work_rejected"),
    ("success", "reservation_created"),
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(value: str) -> dict[str, tuple[str, ...]]:
    """Rechaza filas omitidas, duplicadas o malformadas y drift de cobertura."""
    rows = {}
    for line in value.splitlines():
        cells = tuple(part.strip() for part in line.strip().strip("|").split("|"))
        if not cells:
            continue
        key = cells[0].strip(chr(96))
        if key not in UNIT_NEEDLES:
            continue
        if key in rows or len(cells) != 5 or not all(cells[:4]):
            raise ValueError(f"fila ambigua: {key}")
        if UNIT_NEEDLES[key] not in cells[1] or cells[2] != "NO_VERIFICABLE":
            raise ValueError(f"descripción/estado divergente: {key}")
        rows[key] = cells
    if set(rows) != set(UNIT_NEEDLES):
        raise ValueError("unidades incompletas de Factory #1650")
    return rows


def historical_runs(data: object) -> bool:
    """Fixture histórico coherente, sin atribuirle una consulta a GitHub."""
    if not isinstance(data, dict):
        return False
    try:
        attempts = data["coordination_attempts"]
        if not isinstance(attempts, list) or len(attempts) != 4:
            return False
        if [a["run_id"] for a in attempts] != list(RUN_IDS):
            return False
        if [(a["conclusion"], a["effect"]) for a in attempts] != list(RUN_EFFECTS):
            return False
        if data["origin"]["provenance"] != [f"run:{n}" for n in RUN_IDS]:
            return False
        if data["origin"]["issue"] != 247 or data["origin"]["owner_request"] is not False:
            return False
        for attempt in attempts:
            start = datetime.fromisoformat(attempt["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(attempt["completed_at"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                return False
            if type(attempt["duration_seconds"]) is not int:
                return False
            if int((end - start).total_seconds()) != attempt["duration_seconds"]:
                return False
        return data["shadow_candidate"]["external_writes"] == []
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return False


def assess(matrix: object, checklist: object, living: object, data: object) -> dict[str, object]:
    """Solo hechos documentales acotados dan True; resto UNKNOWN."""
    output = {unit: UNKNOWN for unit in UNIT_NEEDLES}
    if not all(isinstance(x, str) for x in (matrix, checklist, living)):
        return output
    try:
        matrix_rows(matrix)
    except ValueError:
        return output
    if not historical_runs(data):
        return output
    sources = (
        "decisiones.yml", "docs/resiliencia-fabrica.md", "docs/release-runbook.md",
        "docs/release-bootstrap.md", "docs/reusable-release-rollback.md",
    )
    if all(chr(96) + p + chr(96) in checklist and (ROOT / p).is_file() for p in sources):
        output[f"{CHECKLIST}:L9-U1"] = True  # Inventario, no ejecución.
    if "no constituye una declaración de " + chr(96) + "VALIDATED_IN_PRODUCTION" + chr(96) in checklist:
        output[f"{CHECKLIST}:L90-U1"] = True  # Límite documental.
    if "workflow success, pero sin reserva efectiva" in living:
        output[f"{LIVING}:L10-U1"] = True
    if "no podía coexistir con #330" in living:
        output[f"{LIVING}:L11-U1"] = True
    if "reserva V3 concedida" in living:
        output[f"{LIVING}:L12-U1"] = True
    hypothesis = data["origin"].get("hypothesis", "")
    if (isinstance(hypothesis, str)
            and all(p in hypothesis for p in (
                "acceptance contract", "available status", "factory-plan-task"))
            and "validar acceptance contract + available state + factory-plan-task" in living):
        output[f"{LIVING}:L14-U1"] = True  # Hipótesis, no política global.
    return output


def manifest_32110() -> dict[str, object]:
    """Ejemplo sintético sin recibos de offsite ni credenciales."""
    return {
        "version": 1, "project": "factory-synthetic",
        "target": {"rpo_minutes": 30, "rto_minutes": 90},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 1, "daily": 7, "weekly": 4, "monthly": 1},
        "sources": {"database": "NOT_APPLICABLE", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "NOT_APPLICABLE"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 30},
    }


class BrechasFactory32Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix, self.checklist, self.living = read(MATRIX), read(CHECKLIST), read(LIVING)
        self.data = json.loads(read(MANIFEST))

    def test_contrato_principal(self) -> None:
        rows = matrix_rows(self.matrix)
        verdicts = assess(self.matrix, self.checklist, self.living, self.data)
        self.assertEqual(len(UNIT_NEEDLES), 16)
        self.assertEqual(set(rows), set(UNIT_NEEDLES))
        self.assertEqual(set(verdicts), set(UNIT_NEEDLES))
        self.assertEqual(set(GAPS), {u for u, v in verdicts.items() if v == UNKNOWN})
        for unit, row in rows.items():
            with self.subTest(unit=unit):
                self.assertIn("Contraste #1571", row[3])
                if unit in GAPS:
                    self.assertEqual(verdicts[unit], UNKNOWN)
                    self.assertTrue(GAPS[unit].startswith("UNKNOWN:"))
                else:
                    self.assertIs(verdicts[unit], True)
        # Contrato 3-2-1-1-0 válido en memoria, pero no copia externa real.
        self.assertEqual(validate_recovery_manifest(manifest_32110())["target"]["rto_minutes"], 90)
        self.assertEqual(verdicts[f"{CHECKLIST}:L83-U1"], UNKNOWN)
        # Una ventana sintética con default B nunca acredita publicación.
        gate = release_window._render_gate(
            "1.0.24", "a" * 40,
            datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc),
            source_issue=1650,
        )
        record = release_window._gate_from_body(gate["body"])
        self.assertIsNotNone(record)
        self.assertEqual(record[0]["safe_default"], "B")
        self.assertEqual(verdicts[f"{CHECKLIST}:L84-U2"], UNKNOWN)

    def test_falla_cerrado(self) -> None:
        for invalid in (None, {}, {"coordination_attempts": []}):
            self.assertEqual(
                set(assess(self.matrix, self.checklist, self.living, invalid).values()),
                {UNKNOWN},
            )
        for index, field, value in (
            (1, "effect", "reservation_created"),
            (2, "conclusion", "success"),
            (3, "run_id", 12345),
            (3, "duration_seconds", 999),
        ):
            changed = copy.deepcopy(self.data)
            changed["coordination_attempts"][index][field] = value
            with self.subTest(index=index, field=field):
                self.assertEqual(
                    set(assess(self.matrix, self.checklist, self.living, changed).values()),
                    {UNKNOWN},
                )
        self.assertEqual(set(assess("", self.checklist, self.living, self.data).values()), {UNKNOWN})
        row = next(x for x in self.matrix.splitlines() if
                   chr(96) + f"{CHECKLIST}:L83-U1" + chr(96) in x)
        with self.assertRaises(ValueError):
            matrix_rows(self.matrix + "\n" + row)
        with self.assertRaises(ValueError):
            matrix_rows(self.matrix.replace(row, ""))
        invalid = manifest_32110()
        invalid["protection"]["immutable_copies"] = 0
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(invalid)

    def test_sin_datos_reales(self) -> None:
        fixture = manifest_32110()
        self.assertEqual(fixture["project"], "factory-synthetic")
        self.assertEqual(fixture["encryption"]["key_material"], "EXTERNAL_ONLY")
        self.assertEqual(self.data["shadow_candidate"]["external_writes"], [])
        self.assertFalse(self.data["origin"]["owner_request"])
        self.assertFalse(self.data["decision"]["authority_expanded"])
        self.assertFalse(self.data["decision"]["stable_mutation"])
        for sensitive in ("password", "credential", "access_token", "email_address"):
            self.assertNotIn(sensitive, fixture)

    def test_estados_unknown_explicitos(self) -> None:
        outcomes = assess(self.matrix, self.checklist, self.living, self.data)
        for unit, reason in GAPS.items():
            with self.subTest(unit=unit):
                self.assertEqual(outcomes[unit], UNKNOWN)
                self.assertTrue(reason.startswith("UNKNOWN:"))
        for args in (
            (None, self.checklist, self.living, self.data),
            (self.matrix, None, self.living, self.data),
            (self.matrix, self.checklist, None, self.data),
        ):
            self.assertEqual(set(assess(*args).values()), {UNKNOWN})
        changed = copy.deepcopy(self.data)
        changed["origin"]["provenance"].pop()
        self.assertEqual(
            set(assess(self.matrix, self.checklist, self.living, changed).values()),
            {UNKNOWN},
        )
        self.assertEqual(outcomes[f"{CHECKLIST}:L9-U2"], UNKNOWN)
        self.assertEqual(outcomes[f"{CHECKLIST}:L85-U1"], UNKNOWN)


if __name__ == "__main__":
    unittest.main()
