#!/usr/bin/env python3
"""Factory #1667: 16 offline boundaries for construction policy / Project DNA.

A local contract is not permission for parallel jobs, releases or production.
Do not promote any matrix row: this issue claims only its own test file.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from intelligence.project_dna import (
    BASE_FIELDS,
    ProjectDnaError,
    _fingerprint_payload,
    discover_project_dna,
    validate_project_dna,
)
from scripts.validar_claims_issue import inspect_claim_paths


ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
PRINCIPLES = "docs/principios-construccion.md"
DNA = "docs/project-dna.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
BT = chr(96)

CLAUSES = {
    "docs/principios-construccion.md:L43-U6":
        "Sin evidencia autenticada de agentes activos, capacidad, heartbeat y frescura",
    "docs/principios-construccion.md:L47-U1":
        "Esta documentación no cambia Coordinación",
    "docs/principios-construccion.md:L7-U1":
        "serializar solo por dependencia real de datos",
    "docs/principios-construccion.md:L7-U2":
        "Maximizar paralelismo",
    "docs/project-dna.md:L11-U1": "rutas relativas del repositorio;",
    "docs/project-dna.md:L12-U1": "presencia de manifests conocidos;",
    "docs/project-dna.md:L13-U1": "estructura declarada de esos manifests;",
    "docs/project-dna.md:L14-U1": "capacidades declaradas por un caller confiable.",
    "docs/project-dna.md:L26-U1": BT + "frameworks" + BT + ";",
    "docs/project-dna.md:L30-U1": BT + "integrations" + BT + ";",
    "docs/project-dna.md:L31-U1": BT + "capabilities" + BT + ";",
    "docs/project-dna.md:L33-U1": BT + "extensions" + BT + ";",
    "docs/project-dna.md:L34-U1": BT + "fingerprint" + BT + ".",
    "docs/project-dna.md:L37-U1": "No se sustituye por una conjetura.",
    "docs/project-dna.md:L48-U1": "Las capacidades futuras deben añadirse",
    "docs/project-dna.md:L50-U1": "Un cambio incompatible de los campos base requiere una nueva versión",
}
IDS = tuple(CLAUSES)
NOT_OBSERVED = frozenset(k for k in IDS if k.startswith(PRINCIPLES + ":"))
SOURCES = (MATRIX, PRINCIPLES, DNA)


def read_sources() -> dict[str, str]:
    """Only known relative repository files, never remote or user data."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in SOURCES}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Fail closed if any of the sixteen rows is missing, duplicated or promoted."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: missing matrix")
    result: dict[str, tuple[str, ...]] = {}
    for key, phrase in CLAUSES.items():
        matches = [line for line in raw.splitlines()
                   if line.startswith("| " + BT + key + BT + " |")]
        if len(matches) != 1:
            raise ValueError("UNKNOWN: absent or duplicated " + key)
        cells = tuple(part.strip() for part in matches[0].strip("|").split("|"))
        if (len(cells) != 5 or cells[0] != BT + key + BT
                or not cells[1].casefold().startswith(phrase.casefold())
                or cells[2] != "NO_VERIFICABLE"
                or "[Contraste #1573](contraste-factory_resto_5.md)"
                   not in cells[3]
                or "evidencia candidata" not in cells[3]
                or cells[4] != "—"):
            raise ValueError("UNKNOWN: inconsistent row " + key)
        result[key] = cells
    return result


def source_matches(key: str, data: object) -> bool:
    if key not in CLAUSES or type(data) is not dict:
        return False
    path, reference = key.split(":L", 1)
    raw = data.get(path)
    if type(raw) is not str:
        return False
    try:
        lineno = int(reference.split("-", 1)[0])
    except (TypeError, ValueError):
        return False
    lines = raw.splitlines()
    return (0 < lineno <= len(lines)
            and CLAUSES[key].casefold() in lines[lineno - 1].casefold())


def rejects(*, paths: object, manifests: object = None,
            capabilities: object = None) -> bool:
    try:
        discover_project_dna(
            paths=paths, manifests=manifests, capabilities=capabilities)
    except ProjectDnaError:
        return True
    return False


def rejects_dna(candidate: object) -> bool:
    try:
        validate_project_dna(candidate)
    except ProjectDnaError:
        return True
    return False


def evidence() -> dict[str, bool]:
    """Actual deterministic Project DNA functions, no fake remote authority."""
    paths = ["package.json", ".github/workflows/ci.yml", "database/migrations/"]
    manifest = {"package.json": {"dependencies": {
        "fastify": "^5", "@sentry/node": "^9",
    }}}
    dna = discover_project_dna(
        paths=paths, manifests=manifest, capabilities=["web", "api"])
    same = discover_project_dna(
        paths=list(reversed(paths)) + ["package.json"],
        manifests=manifest, capabilities=["api", "web", "web"])
    unknown = discover_project_dna(paths=["README.md", "docs/stripe-notes.md"])
    extended = deepcopy(dna)
    extended["extensions"]["future.runtime"] = {"source": "synthetic", "version": 1}
    extended["fingerprint"] = _fingerprint_payload(extended)
    incompatible = deepcopy(dna)
    incompatible["version"] = 2
    incompatible["fingerprint"] = _fingerprint_payload(incompatible)
    extra_base = deepcopy(dna)
    extra_base["runtime"] = "invented"
    extra_base["fingerprint"] = _fingerprint_payload(extra_base)
    wrong_shape = rejects(
        paths=paths,
        manifests={"package.json": "not a manifest"},
    )
    candidate = inspect_claim_paths(["tests/fixture_a.py", "tests/fixture_b.py"])
    invalid = inspect_claim_paths(["tests/"])
    results = {
        # Source-level, non-attestable operations. False is explicit UNKNOWN.
        "docs/principios-construccion.md:L43-U6": False,
        "docs/principios-construccion.md:L47-U1": False,
        "docs/principios-construccion.md:L7-U1":
            bool(candidate["valid"] and not candidate["can_reserve"]
                 and not invalid["valid"]),
        "docs/principios-construccion.md:L7-U2":
            bool(candidate["valid"] and candidate["can_reserve"] is False),
        "docs/project-dna.md:L11-U1":
            rejects(paths=["../private"]) and rejects(paths=["/root/secret"]),
        "docs/project-dna.md:L12-U1":
            dna["signals"]["manifests"] == ["package.json"]
            and "package.json" in dna["signals"]["paths"],
        "docs/project-dna.md:L13-U1": wrong_shape,
        "docs/project-dna.md:L14-U1":
            discover_project_dna(paths=paths)["capabilities"] == "unknown"
            and dna["capabilities"] == ["api", "web"],
        "docs/project-dna.md:L26-U1":
            dna["frameworks"] == ["fastify"]
            and unknown["frameworks"] == "unknown",
        "docs/project-dna.md:L30-U1":
            dna["integrations"] == ["sentry"]
            and unknown["integrations"] == "unknown",
        "docs/project-dna.md:L31-U1":
            dna["capabilities"] == ["api", "web"]
            and rejects(paths=paths, capabilities=["api", ""]),
        "docs/project-dna.md:L33-U1":
            set(dna) == BASE_FIELDS
            and extended["extensions"]["future.runtime"]["source"] == "synthetic",
        "docs/project-dna.md:L34-U1":
            dna["fingerprint"] == same["fingerprint"]
            and len(dna["fingerprint"]) == 64
            and validate_project_dna(same) == same,
        "docs/project-dna.md:L37-U1":
            all(unknown[field] == "unknown" for field in (
                "stack", "frameworks", "data", "ci", "hosting",
                "integrations", "capabilities")),
        "docs/project-dna.md:L48-U1":
            validate_project_dna(extended) == extended
            and set(extended) == BASE_FIELDS,
        "docs/project-dna.md:L50-U1":
            rejects_dna(incompatible) and rejects_dna(extra_base)
            and dna["version"] == 1,
    }
    if set(results) != set(IDS):
        raise ValueError("UNKNOWN: incomplete evidence")
    return results


def assess(data: object, proof: object) -> dict[str, str]:
    unknown = dict.fromkeys(IDS, UNKNOWN)
    if type(data) is not dict or set(data) != set(SOURCES):
        return unknown
    if type(proof) is not dict or set(proof) != set(IDS):
        return unknown
    if any(type(proof[key]) is not bool for key in IDS):
        return unknown
    try:
        matrix_rows(data[MATRIX])
    except (TypeError, ValueError):
        return unknown
    if not all(source_matches(key, data) for key in IDS):
        return unknown
    return {key: LOCAL if proof[key] and key not in NOT_OBSERVED else UNKNOWN
            for key in IDS}


class BrechasFactory49Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: each exact ID has a local assertion or an explicit UNKNOWN."""
        data = read_sources()
        rows, checks = matrix_rows(data[MATRIX]), evidence()
        result = assess(data, checks)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(result), set(IDS))
        for key in IDS:
            with self.subTest(id=key):
                self.assertTrue(source_matches(key, data))
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertIn(result[key], (LOCAL, UNKNOWN))
                if key not in NOT_OBSERVED:
                    self.assertTrue(checks[key], key + " is UNKNOWN")
                    self.assertEqual(result[key], LOCAL)
                else:
                    self.assertEqual(result[key], UNKNOWN)

    def test_falla_cerrado(self):
        """AC-02: missing, duplicate, promoted, incorrect SHA or stale contract."""
        data, checks = read_sources(), evidence()
        for key in IDS:
            original = next(x for x in data[MATRIX].splitlines()
                            if x.startswith("| " + BT + key + BT + " |"))
            for altered in (
                data[MATRIX].replace(original, "", 1),
                data[MATRIX] + "\n" + original,
                data[MATRIX].replace(
                    original, original.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(id=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(altered)
                    self.assertEqual(
                        set(assess({**data, MATRIX: altered}, checks).values()),
                        {UNKNOWN},
                    )
            self.assertEqual(
                assess(data, {**checks, key: False})[key], UNKNOWN)
            doc = key.split(":L", 1)[0]
            lineno = int(key.split(":L", 1)[1].split("-", 1)[0]) - 1
            bad_lines = data[doc].splitlines()
            bad_lines[lineno] = "[erased source evidence]"
            self.assertEqual(
                set(assess({**data, doc: "\n".join(bad_lines)}, checks).values()),
                {UNKNOWN},
            )
        for bad in (None, {}, {"fake": True}, {key: 1 for key in IDS}):
            self.assertEqual(set(assess(data, bad).values()), {UNKNOWN})
        self.assertTrue(rejects(paths=["../secrets/.env"]))
        self.assertTrue(rejects_dna({**discover_project_dna(paths=[]),
                                     "fingerprint": "0" * 64}))

    def test_sin_datos_reales(self):
        """AC-03: no network, external commands, files beyond own docs or secrets."""
        self.assertEqual(set(SOURCES), {
            "docs/matriz-cobertura.md", "docs/principios-construccion.md",
            "docs/project-dna.md"})
        self.assertTrue(all((ROOT / p).is_file() for p in SOURCES))
        self.assertTrue(all("secrets" not in key.casefold() for key in IDS))
        self.assertTrue(rejects(paths=["../../real-data"]))
        self.assertTrue(rejects(paths=["/etc/passwd"]))
        self.assertEqual(evidence()["docs/project-dna.md:L37-U1"], True)

    def test_estados_unknown_explicitos(self):
        """AC-04: lack of real sessions, approvals, production is not success."""
        data, checks = read_sources(), evidence()
        for key in NOT_OBSERVED:
            with self.subTest(id=key):
                self.assertEqual(assess(data, checks)[key], UNKNOWN)
                self.assertEqual(assess(data, {**checks, key: True})[key],
                                 UNKNOWN)
        for invented in (None, {}, {"active_agents": 4, "capacity": 4},
                         {"status": "GREEN"}, {"badge": "success"}):
            self.assertEqual(
                assess(invented, checks),
                dict.fromkeys(IDS, UNKNOWN),
            )
        unknown = discover_project_dna(paths=["README.md"])
        self.assertEqual(unknown["capabilities"], "unknown")
        self.assertEqual(unknown["integrations"], "unknown")


if __name__ == "__main__":
    unittest.main()
