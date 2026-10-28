"""Factory #1653: sixteen offline observer/consumer coverage gaps.

Only local, synthetic documentation and pure-state contracts are checked.
A successful CI run is not an authenticated schedule receipt or Phase B grant.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from scripts.lease_auto_release_integration import (
    IntegrationPreview, local_active_issue_ids,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT_ONLY"
DOC = "docs/observador-reservas-consumidor.md"
MATRIX = "docs/matriz-cobertura.md"
CONTRAST = "docs/contraste-factory_resto_3.md"
CALLER = "template/.github/workflows/observador-reservas-consumidor.yml"
REUSABLE = ".github/workflows/observador-reservas-consumidor.yml"
LEGACY = ".github/workflows/liberar-reservas.yml"
SOURCES = (DOC, MATRIX, CONTRAST, CALLER, REUSABLE, LEGACY)
LINES = (10, 13, 24, 27, 31, 33, 34, 36, 39, 41, 43, 49, 50, 53, 61, 63)
UNITS = tuple(
    f"{DOC}:L{line}-U1" for line in LINES
)


def sources() -> dict[str, str]:
    """All inputs come from the checkout; no GitHub API or browser."""
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in SOURCES}


def evidence_rows(document: object, kind: str) -> dict[str, tuple[str, ...]] | None:
    """Count a table identifier once; whitespace variants cannot hide duplicates."""
    if not isinstance(document, str) or kind not in ("matrix", "contrast"):
        return None
    found: dict[str, tuple[str, ...]] = {}
    for line in document.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if not cells:
            continue
        identifier = cells[0].strip(chr(96)).strip()
        if identifier not in UNITS:
            continue
        if identifier in found or len(cells) != (5 if kind == "matrix" else 6):
            return None
        if (not all(cells) or cells[2] != "NO_VERIFICABLE"
                or (kind == "matrix" and "Contraste #1571" not in cells[3])
                or (kind == "contrast" and "Sin aserción exacta" not in cells[5])):
            return None
        found[identifier] = cells
    return found if set(found) == set(UNITS) else None


def classify(identifier: object, source: object) -> str:
    """Local evidence consistency, never real consumer observation."""
    if not isinstance(identifier, str) or identifier not in UNITS:
        return UNKNOWN
    if not isinstance(source, dict) or any(
        not isinstance(source.get(path), str) or not source[path]
        for path in SOURCES
    ):
        return UNKNOWN
    matrix = evidence_rows(source[MATRIX], "matrix")
    contrast = evidence_rows(source[CONTRAST], "contrast")
    if matrix is None or contrast is None:
        return UNKNOWN
    lines = source[DOC].splitlines()
    for key in UNITS:
        line_number = int(key.rsplit(":L", 1)[1].split("-", 1)[0])
        if (line_number > len(lines)
                or matrix[key][1] not in lines[line_number - 1].strip()
                or contrast[key][1] not in lines[line_number - 1].strip()):
            return UNKNOWN

    # Static proof of a read-only, non-deployed observer. Comments and
    # documentation are NOT proof that a consumer actually ran this workflow.
    legacy, caller, reusable = (source[name] for name in (LEGACY, CALLER, REUSABLE))
    required_caller = (
        "schedule:", "workflow_dispatch:", "contents: read", "issues: read",
        "checks: read", "actions: read",
        "lease-consumer-caller-", "observador-reservas-consumidor.yml@v1",
    )
    required_reusable = (
        "workflow_call:", "factory-coordination-", "contents: read",
        "issues: read", "checks: read", "actions: read",
        "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'",
        "release_authorized: false", "terminal_certified: false",
        "mutations: 0",
    )
    if (any(item not in caller for item in required_caller)
            or any(item not in reusable for item in required_reusable)
            or "github.repository == 'pl0n3r/Factory'" not in legacy
            or "group: lease-consumer-caller-" not in caller
            or "group: factory-coordination-" not in reusable
            or "group: factory-coordination-" in caller
            or any(banned in doc for doc in (caller, reusable)
                   for banned in ("contents: write", "issues: write",
                                  "pull-requests: write", "gh pr merge",
                                  "gh issue edit"))):
        return UNKNOWN
    return LOCAL


def operational_evidence(_identifier: object, _claim: object = None) -> str:
    """No synthetic event, proposed release or CI result authorizes Phase B."""
    return UNKNOWN


class BrechasFactory35Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: a separate source-grounded assertion for all sixteen IDs."""
        local = sources()
        matrix, contrast = (evidence_rows(local[p], kind) for p, kind in (
            (MATRIX, "matrix"), (CONTRAST, "contrast"),
        ))
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(matrix), set(UNITS))
        self.assertEqual(set(contrast), set(UNITS))
        for identifier in UNITS:
            with self.subTest(identifier=identifier):
                self.assertEqual(classify(identifier, local), LOCAL)
                self.assertEqual(matrix[identifier][2], "NO_VERIFICABLE")
                self.assertEqual(contrast[identifier][2], "NO_VERIFICABLE")
                self.assertEqual(operational_evidence(identifier), UNKNOWN)

        # The existing pure observer never acquires release/lock/CAS authority.
        preview = IntegrationPreview(
            837, "read_only", "release", "inactive_after_recovery_grace",
            40, "issue_comment",
        )
        self.assertFalse(preview.release_authorized)
        self.assertFalse(preview.lock_verified)
        self.assertFalse(preview.cas_verified)
        local_issue = {
            "number": 837, "state": "open",
            "labels": [{"name": "estado: reservado"}],
        }
        self.assertEqual(
            local_active_issue_ids([[local_issue]], "pl0n3r/ControlBot"), [837],
        )

    def test_falla_cerrado(self):
        """AC-02: missing, ambiguous or promoted evidence is always UNKNOWN."""
        local = sources()
        for path, kind in ((MATRIX, "matrix"), (CONTRAST, "contrast")):
            for identifier in UNITS:
                original = next(
                    row for row in local[path].splitlines()
                    if row.strip().startswith("|")
                    and row.strip().strip("|").split("|")[0].strip().strip(chr(96))
                    == identifier
                )
                for damaged in (
                    local[path].replace(original, "", 1),
                    local[path] + "\n" + original,
                    local[path] + "\n" + original.replace("| ", "|", 1),
                    local[path].replace(
                        original,
                        original.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1,
                    ),
                ):
                    with self.subTest(kind=kind, identifier=identifier):
                        broken = dict(local)
                        broken[path] = damaged
                        self.assertEqual(classify(identifier, broken), UNKNOWN)
        for identifier in UNITS:
            line_number = int(identifier.rsplit(":L", 1)[1].split("-", 1)[0])
            line = local[DOC].splitlines()[line_number - 1]
            broken = dict(local)
            broken[DOC] = local[DOC].replace(line, "MISSING CONTRACT", 1)
            self.assertEqual(classify(identifier, broken), UNKNOWN)
        for path, token in (
            (CALLER, "schedule:"),
            (CALLER, "issues: read"),
            (REUSABLE, "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'"),
            (REUSABLE, "release_authorized: false"),
            (LEGACY, "github.repository == 'pl0n3r/Factory'"),
        ):
            broken = dict(local)
            self.assertIn(token, broken[path])
            broken[path] = broken[path].replace(token, "UNVERIFIED", 1)
            self.assertEqual(classify(UNITS[0], broken), UNKNOWN)
        self.assertIsNone(local_active_issue_ids([], "pl0n3r/ControlBot"))
        self.assertIsNone(local_active_issue_ids(
            [[{"number": 837, "state": "open", "labels": []},
              {"number": 837, "state": "open", "labels": []}]],
            "pl0n3r/ControlBot",
        ))
        self.assertEqual(classify(UNITS[0], {}), UNKNOWN)
        self.assertEqual(classify([], local), UNKNOWN)

    def test_sin_datos_reales(self):
        """AC-03: deterministic synthetic data; no external access or secrets."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {a.name.split(".")[0] for n in ast.walk(tree)
                   if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(imports & {
            "requests", "urllib", "socket", "http", "httpx",
            "subprocess", "selenium", "playwright",
        })
        self.assertEqual(set(SOURCES), {
            DOC, MATRIX, CONTRAST, CALLER, REUSABLE, LEGACY,
        })
        self.assertTrue(all(name.startswith("docs/") or
                            name.startswith(".github/") or
                            name.startswith("template/")
                            for name in SOURCES))
        self.assertEqual(
            operational_evidence(UNITS[0], {"token": "synthetic-only"}), UNKNOWN,
        )

    def test_estados_unknown_explicitos(self):
        """AC-04: synthetic runs never prove actual 100 cycles / 24 hours."""
        local = sources()
        for identifier in UNITS:
            with self.subTest(identifier=identifier):
                self.assertEqual(classify(identifier, local), LOCAL)
                for claim in (
                    None, {}, True, {"ci": "success"},
                    {"candidate_terminal": True},
                    {"schedule": "success", "repo": "pl0n3r/ControlBot"},
                    {"cycles": 100, "hours": 24, "false_positives": 0},
                    {"owner": "approved", "factory_v1": "released"},
                    {"lock_verified": True, "cas_verified": True},
                    {"release_authorized": True},
                ):
                    self.assertEqual(
                        operational_evidence(identifier, claim), UNKNOWN,
                    )
        self.assertEqual(classify("not-a-unit", local), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
