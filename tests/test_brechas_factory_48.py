"""Factory #1666: 16 contract-gap regressions for construction principles.

Offline evidence is not permission to dispatch, merge, release or claim GREEN.
The source matrix remains NO_VERIFICABLE until its own reconciliation issue.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.release_api_budget import (
    ReleaseBudgetError, classify_transport_failure,
)
from scripts.salud_cola_snapshot import (
    REPOSITORIES, SnapshotError, assemble_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/principios-construccion.md"
MATRIX = "docs/matriz-cobertura.md"
PLAN = "PLAN-AGENTES.md"
UNKNOWN = "UNKNOWN"
OFFLINE = "OFFLINE_VERIFIED"
PREFIX = DOC + ":"

# Each item below has its own assertion or an explicit non-attestable boundary.
CLAUSES = {
    "L23-U2": "UNKNOWN nunca equivale a GREEN.",
    "L23-U3": "Verificar evidencia terminal exact-HEAD",
    "L23-U4": "para puertas D-043 exigir VALIDATED_IN_PRODUCTION",
    "L27-U1": "construccion permite preparar trabajo reversible y offline",
    "L27-U2": "D-063 exige atestación válida",
    "L27-U3": "Factory@v1 mantiene su puerta vigente exact-SHA",
    "L3-U1": "no habilita por sí solo acciones, coordinación, merges ni releases.",
    "L31-U1": "AC-NN debe señalar unittest existente/implementable o check real",
    "L35-U1": "Verificar rate_limit y conservar capacidad para reparaciones",
    "L35-U2": "Autenticación compartida no garantiza 5.000 solicitudes",
    "L39-U1": "Nunca fabricar APPROVED, HEALTH, actividad, throughput o readiness.",
    "L43-U1": "Reportar por repositorio y global conteos separados de disponible",
    "L43-U2": "identificar causa y fuente de cada bloqueo.",
    "L43-U3": "El `estado: requiere recuperación` / `status: recovery required`",
    "L43-U4": "Contarlo por separado solo tras integrar el contrato de Factory #1102",
    "L43-U5": "antes, rechazar snapshots que no puedan representar recovery",
}
IDS = tuple(PREFIX + suffix for suffix in CLAUSES)
# These are contractual boundaries, not things a fixture or repository can attest.
UNOBSERVED = frozenset(PREFIX + suffix for suffix in (
    "L23-U4", "L27-U1", "L27-U2", "L27-U3",
    "L35-U1", "L35-U2", "L39-U1", "L43-U1", "L43-U4", "L43-U5",
))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Reject missing/duplicate/ambiguous/promoted rows for all sixteen IDs."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: matriz no legible")
    found: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if not cells or not cells[0].startswith(chr(96)):
            continue
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if (key in found or len(cells) != 5
                or not cells[1].startswith(CLAUSES[key[len(PREFIX):]])
                or cells[2] != "NO_VERIFICABLE"
                or "[Contraste #1573](contraste-factory_resto_5.md)" not in cells[3]
                or "evidencia candidata" not in cells[3]
                or cells[4] != "—"):
            raise ValueError("UNKNOWN: fila ambigua/promovida " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: falta fila")
    return found


def terminal_check(sample: object, head: str) -> bool:
    """Synthetic shape validation only, NOT an actual GitHub check assertion."""
    return bool(
        type(sample) is dict and type(head) is str
        and len(head) == 40 and all(ch in "0123456789abcdef" for ch in head)
        and sample.get("name") == "Validar"
        and sample.get("status") == "completed"
        and sample.get("conclusion") == "success"
        and sample.get("head_sha") == head
    )


def d043_terminal(sample: object, sha: str, version: str) -> bool:
    """Check exact identity and pending=[]; never contact production."""
    return bool(
        type(sample) is dict and type(sha) is str and type(version) is str
        and len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)
        and sample.get("state") == "VALIDATED_IN_PRODUCTION"
        and sample.get("sha") == sha
        and sample.get("version") == version
        and type(sample.get("pending")) is list
        and sample["pending"] == []
    )


def reports() -> list[dict]:
    """Seven synthetic repositories and verified-shaped terminal page."""
    return [
        {"name": name, "pages": [
            {"page_number": 1, "has_next": False, "issues": []},
        ]}
        for name in REPOSITORIES
    ]


def issue(number: int, state: str, blocker: object = None) -> dict:
    return {
        "number": number, "labels": ["estado: " + state],
        "pull_request": False, "blocker": blocker,
    }


def evidence(doc: str, plan: str) -> dict[str, bool]:
    """One *bounded* offline assertion per matrix ID, no live inference."""
    data = reports()
    data[0]["pages"][0]["issues"] = [
        issue(1, "disponible"), issue(2, "reservado"),
        issue(3, "en revisión"), issue(4, "bloqueado"),
        issue(5, "planificado"), issue(6, "requiere recuperación"),
    ]
    inventory = assemble_inventory(
        data, None, {"limit": 5000, "remaining": 999},
    )
    first = inventory["repositories"][0]
    counts = first["counts"]
    blockers = first["blockers"]
    sha = "a" * 40
    good_ci = {"name": "Validar", "status": "completed",
               "conclusion": "success", "head_sha": sha}
    prod = {"state": "DEPLOY_OBSERVED", "sha": sha,
            "version": "1.0.0", "pending": ["transicion_release"]}
    quota = classify_transport_failure(403, remaining=0, reset_after_seconds=45)
    with_bad_capacity = inventory["agent_capacity"] is None
    checks = {
        "L23-U2": not terminal_check({**good_ci, "conclusion": "neutral"}, sha),
        "L23-U3": (
            terminal_check(good_ci, sha)
            and not terminal_check({**good_ci, "head_sha": "b" * 40}, sha)
            and not terminal_check({**good_ci, "status": "in_progress"}, sha)
        ),
        "L23-U4": (
            not d043_terminal(prod, sha, "1.0.0")
            and not d043_terminal({**prod, "state": "VALIDATED_IN_PRODUCTION"},
                                  sha, "1.0.0")
        ),
        "L27-U1": ("reversible" in doc and "offline" in doc
                    and "**No elimina aprobación humana**" in doc),
        "L27-U2": ("D-063 exige atestación válida" in doc
                    and "D-063" in plan and "D-059" in doc),
        "L27-U3": ("Factory@v1 mantiene su puerta vigente exact-SHA" in doc
                    and "**no** autorización autoejecutable" in doc),
        "L3-U1": ("no habilita por sí solo acciones" in doc
                   and "PLAN-AGENTES.md" in doc
                   and "factory-acceptance" in plan),
        "L31-U1": ("AC-NN debe señalar unittest existente/implementable" in doc
                    and "Contrato ejecutable" in plan
                    and (ROOT / "tests/test_principios_construccion.py").is_file()),
        "L35-U1": (
            quota.must_fail_closed
            and quota.kind == "limite_primario"
            and quota.suggested_retry_seconds is None
            and inventory["rate_limit"]["remaining"] < 1000
        ),
        "L35-U2": (
            inventory["rate_limit"] == {"limit": 5000, "remaining": 999}
            and quota.must_fail_closed
        ),
        "L39-U1": (
            with_bad_capacity and not d043_terminal(prod, sha, "1.0.0")
            and "Nunca fabricar APPROVED" in doc
        ),
        "L43-U1": (
            len(inventory["repositories"]) == 7
            and counts == {"available": 1, "reserved": 1, "blocked": 1,
                           "planned": 1, "in_review": 1, "recovery_required": 1}
            and first["open_issues"] == 6
        ),
        "L43-U2": (
            blockers == [{"number": 4, "cause": "unknown", "roadmap": False}]
            and not blockers[0]["roadmap"]
        ),
        "L43-U3": (
            counts["recovery_required"] == 1 and counts["available"] == 1
            and "recovery_required" not in ("available", "blocked", "planned")
        ),
        "L43-U4": ("Factory #1102" in doc and
                    "Contarlo por separado solo tras integrar" in doc),
        "L43-U5": (with_bad_capacity and
                    "sin fabricar GREEN" in doc and
                    "Utilización = agentes activos verificados" in doc),
    }
    if set(checks) != set(CLAUSES):
        raise ValueError("UNKNOWN: falta cláusula")
    for key, snippet in CLAUSES.items():
        checks[key] = checks[key] and snippet in doc
    return {PREFIX + key: result for key, result in checks.items()}


def assess(matrix: object, doc: object, checks: object) -> dict[str, str]:
    """No complete evidence means ALL UNKNOWN, never GREEN."""
    unknown = dict.fromkeys(IDS, UNKNOWN)
    try:
        matrix_rows(matrix)
    except ValueError:
        return unknown
    if (type(doc) is not str or type(checks) is not dict
            or set(checks) != set(IDS)
            or any(type(checks[k]) is not bool for k in IDS)
            or any(fragment not in doc for fragment in CLAUSES.values())):
        return unknown
    return {key: (OFFLINE if checks[key] and key not in UNOBSERVED
                  else UNKNOWN) for key in IDS}


class BrechasFactory48Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: every ID maps to a real assertion or explicit UNKNOWN."""
        doc, plan, matrix = read(DOC), read(PLAN), read(MATRIX)
        rows = matrix_rows(matrix)
        checks = evidence(doc, plan)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(checks), set(IDS))
        for key in IDS:
            with self.subTest(unit=key):
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertTrue(checks[key], key + " : UNKNOWN")
                self.assertIn(assess(matrix, doc, checks)[key], (OFFLINE, UNKNOWN))
        self.assertEqual(
            {key for key in IDS if assess(matrix, doc, checks)[key] == UNKNOWN},
            UNOBSERVED,
        )

    def test_falla_cerrado(self):
        """AC-02: absent/ambiguous/promoted row, mismatched check, bad quota."""
        doc, matrix = read(DOC), read(MATRIX)
        good = evidence(doc, read(PLAN))
        for key in IDS:
            original = next(x for x in matrix.splitlines()
                            if x.startswith("| " + chr(96) + key + chr(96) + " |"))
            for bad in (
                matrix.replace(original, "", 1),
                matrix + "\n" + original,
                matrix.replace(original,
                               original.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(unit=key):
                    with self.assertRaises(ValueError):
                        matrix_rows(bad)
                    self.assertEqual(set(assess(bad, doc, good).values()),
                                     {UNKNOWN})
            missing = {**good, key: False}
            self.assertEqual(assess(matrix, doc, missing)[key], UNKNOWN)
        for stale in (None, {}, {"unknown-id": True}, {key: 1 for key in IDS}):
            self.assertEqual(set(assess(matrix, doc, stale).values()), {UNKNOWN})
        sha = "a" * 40
        for invalid in (
            {"name": "Validar", "status": "completed", "conclusion": "failure",
             "head_sha": sha},
            {"name": "Validar", "status": "pending", "conclusion": "success",
             "head_sha": sha},
            {"name": "Validar", "status": "completed", "conclusion": "success",
             "head_sha": "b" * 40},
        ):
            self.assertFalse(terminal_check(invalid, sha))
        for invalid in (None, {}, {"limit": 5000}, {"limit": 5000, "remaining": 5001}):
            with self.assertRaises(SnapshotError):
                assemble_inventory(reports(), None, invalid)
        with self.assertRaises(ReleaseBudgetError):
            classify_transport_failure(403, remaining=True)

    def test_sin_datos_reales(self):
        """AC-03: pure scripts with fabricated row IDs, no HTTP/creds/PII."""
        doc = read(DOC)
        sample = reports()
        sample[0]["pages"][0]["issues"] = [
            issue(101, "bloqueado",
                  {"cause": "dependency", "roadmap": True}),
        ]
        encoded = json.dumps(sample, ensure_ascii=False)
        for marker in ("password", "access_token", "authorization",
                       "@gmail", "http://", "https://", "ghp_"):
            self.assertNotIn(marker, encoded.lower())
        result = assemble_inventory(sample, None, {"limit": 120, "remaining": 24})
        self.assertEqual(result["repositories"][0]["blockers"],
                         [{"number": 101, "cause": "dependency", "roadmap": True}])
        self.assertIn("no habilita por sí solo", doc)
        self.assertFalse(d043_terminal({}, "a" * 40, "1.0.0"))

    def test_estados_unknown_explicitos(self):
        """AC-04: operational signals cannot be inferred from synthetic data."""
        doc, matrix = read(DOC), read(MATRIX)
        checks = evidence(doc, read(PLAN))
        verdicts = assess(matrix, doc, checks)
        for key in UNOBSERVED:
            with self.subTest(unit=key):
                self.assertEqual(verdicts[key], UNKNOWN)
        for fake in (
            None, {}, False, {"state": "DEPLOY_OBSERVED"},
            {"state": "VALIDATED_IN_PRODUCTION", "sha": "a" * 40,
             "version": "1.0.0", "pending": ["cache"]},
            {"state": "VALIDATED_IN_PRODUCTION", "sha": "b" * 40,
             "version": "1.0.0", "pending": []},
        ):
            self.assertFalse(d043_terminal(fake, "a" * 40, "1.0.0"))
        with self.assertRaises(SnapshotError):
            broken = reports()
            broken.pop()
            assemble_inventory(broken, None, {"limit": 5000, "remaining": 5000})
        self.assertEqual(set(verdicts.values()), {UNKNOWN, OFFLINE})
        self.assertNotIn("GREEN", verdicts.values())


if __name__ == "__main__":
    unittest.main()
