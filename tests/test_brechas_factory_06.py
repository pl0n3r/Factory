#!/usr/bin/env python3
"""Factory #1624: 16 contract gaps with synthetic witnesses; never live proof."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
GAP = "BRECHA_DOCUMENTADA"
CLAUSES = {
    "docs/arquitectura-tecnica.md:B03": "Releases y deploys deben respetar rollback, gates y autorización de tag `v1`.",
    "docs/arquitectura-tecnica.md:B04": "Separar ControlBot, FactoryRunner y productos en planos con autoridad limitada y sin credenciales compartidas.",
    "docs/auditoria-pre-v1.md:B01": "La auditoría de v1.0.0 se limita al SHA histórico auditado y no certifica el estado actual de Factory.",
    "docs/auditoria-pre-v1.md:B02": "Los hallazgos altos del caller de bootstrap y trust-root de v1 exigen verificación de mitigación y puerta humana antes de publicar.",
    "docs/auditoria-pre-v1.md:B03": "Las dependencias externas ejecutadas en CI deben acreditar integridad criptográfica y no solo fijación por versión.",
    "docs/auditoria-pre-v1.md:B04": "Los eventos de coordinación y el costo de Actions deben medirse antes de recortar disparadores de seguridad.",
    "docs/automerge-construccion.md:B01": "Automerge de construcción es diagnostico dry-run sin operaciones de merge",
    "docs/automerge-construccion.md:B02": "Diagnostico exige CI success, identidad exact-SHA y sin findings graves",
    "docs/automerge-construccion.md:B03": "Freeze, permisos, release v1 y go-live conservan vetos duros",
    "docs/autonomy-engine.md:L17-U1": "Una promoción exige:",
    "docs/autonomy-engine.md:L19-U1": "Fitness completo, sin dimensiones faltantes ni regresiones protegidas;",
    "docs/autonomy-engine.md:L20-U1": "claim `equal` o `improved`;",
    "docs/autonomy-engine.md:L21-U1": "Risk con contexto crítico completo;",
    "docs/autonomy-engine.md:L22-U1": "evidencia no vacía.",
    "docs/autonomy-engine.md:L24-U1": "El nivel `autonomous` no se concede con riesgo `high`.",
    "docs/autonomy-engine.md:L28-U1": "Los fallos nunca se esconden:",
}
IDS = tuple(CLAUSES)
DOCS = frozenset(k.rsplit(":", 1)[0] for k in IDS)
DOCUMENT_ONLY = frozenset(("docs/arquitectura-tecnica.md", "docs/auditoria-pre-v1.md"))
# Historical B IDs describe aggregate contracts, not a literal line number.
ANCHORS = {
    "docs/arquitectura-tecnica.md:B03": ("### 9.3 Deploy con rollback", "release-bootstrap.yml"),
    "docs/arquitectura-tecnica.md:B04": ("**ControlBot:** control plane", "**FactoryRunner:** execution plane"),
    "docs/auditoria-pre-v1.md:B01": ("**SHA auditado:** `4b2be9fcf827278631caa3e3e68603b6e2a680d7`",),
    "docs/auditoria-pre-v1.md:B02": ("### AUD-SEC-002", "#82", "#83"),
    "docs/auditoria-pre-v1.md:B03": ("### AUD-SC-003", "integridad criptográfica"),
    "docs/auditoria-pre-v1.md:B04": ("### AUD-COST-006", "Eventos de coordinación"),
    "docs/automerge-construccion.md:B01": ("observador dry-run", "no permisos de merge"),
    "docs/automerge-construccion.md:B02": ("exact-SHA", "findings"),
    "docs/automerge-construccion.md:B03": ("freeze", "go-live", "permisos"),
}
# Independently named existing synthetic tests, not identity derived from docs.
WITNESSES = {
    "promote": ("test_autonomy_engine.py", "AutonomyEngineTests",
                "test_capability_progresses_through_evidence_ladder"),
    "fitness": ("test_autonomy_engine.py", "AutonomyEngineTests",
                "test_forged_fitness_evidence_is_rejected"),
    "risk": ("test_autonomy_engine.py", "AutonomyEngineTests",
             "test_forged_risk_evidence_is_rejected"),
    "no_high": ("test_autonomy_engine.py", "AutonomyEngineTests",
                "test_forbidden_authority_capabilities_cannot_gain_autonomy"),
    "downgrade": ("test_autonomy_engine.py", "AutonomyEngineTests",
                  "test_failures_reduce_or_revoke_autonomy"),
    "dry_run": ("test_automerge_construccion.py", "AutoMergeConstruccionTests",
                "test_valid_construction_candidate_is_diagnostic_only"),
    "exact_sha": ("test_automerge_construccion.py", "AutoMergeConstruccionTests",
                  "test_draft_checks_reviews_threads_and_sha_drift_fail_closed"),
    "gates": ("test_automerge_construccion.py", "AutoMergeConstruccionTests",
              "test_live_sensitive_paths_and_freeze_require_human_gate"),
}
WITNESS_FOR = dict(zip(
    [f"docs/automerge-construccion.md:B0{i}" for i in (1, 2, 3)] +
    [f"docs/autonomy-engine.md:L{n}-U1" for n in (17, 19, 20, 21, 22, 24, 28)],
    ["dry_run", "exact_sha", "gates", "promote", "fitness", "promote",
     "risk", "promote", "no_high", "downgrade"],
))


def read_sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8")
            for p in (MATRIX, *sorted(DOCS))}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Detect duplicate known IDs even when whitespace is nonstandard."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz ilegible")
    rows = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        m = re.fullmatch(r"`([^`]+)`", cells[0]) if cells else None
        if m is None or m.group(1) not in CLAUSES:
            continue
        key = m.group(1)
        doc = key.rsplit(":", 1)[0]
        if (key in rows or len(cells) != 5 or cells[0] != f"`{key}`"
                or cells[1] != CLAUSES[key] or cells[2] != "NO_VERIFICABLE"
                or not cells[3] or not cells[4]
                or (doc == "docs/autonomy-engine.md" and
                    "[Contraste #1569]" not in cells[3])
                or (doc == "docs/arquitectura-tecnica.md" and cells[4] != "—")
                or (doc == "docs/auditoria-pre-v1.md" and "#1562" not in cells[4])
                or (doc == "docs/automerge-construccion.md" and "#1563" not in cells[4])):
            raise ValueError(UNKNOWN + ": fila contradictoria " + key)
        rows[key] = cells
    if set(rows) != set(IDS):
        raise ValueError(UNKNOWN + ": filas ausentes")
    return rows


def source_matches(key: object, data: object) -> bool:
    if type(key) is not str or key not in CLAUSES or type(data) is not dict:
        return False
    doc = key.rsplit(":", 1)[0]
    raw = data.get(doc)
    if type(raw) is not str:
        return False
    if key in ANCHORS:
        return all(x in raw for x in ANCHORS[key])
    n = key.rsplit(":L", 1)[-1].split("-", 1)[0]
    if not n.isdecimal():
        return False
    lines = raw.splitlines()
    return 0 < int(n) <= len(lines) and CLAUSES[key] in lines[int(n)-1]


def run_witnesses() -> dict[str, bool]:
    """Only allowlisted preexisting synthetic unittest cases (no network)."""
    old = sys.path[:]
    successes = {}
    try:
        for directory in (ROOT, ROOT / "tests"):
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
        modules = {}
        for name, (filename, klass, method) in WITNESSES.items():
            if filename not in modules:
                modules[filename] = runpy.run_path(str(ROOT / "tests" / filename))
            result = unittest.TestResult()
            modules[filename][klass](method).run(result)
            if result.testsRun != 1 or not result.wasSuccessful():
                raise AssertionError(UNKNOWN + ": testigo fallido " + name)
            successes[name] = True
    finally:
        sys.path[:] = old
    return successes


def assess(data: object, proofs: object) -> dict[str, str]:
    no = dict.fromkeys(IDS, UNKNOWN)
    if (type(data) is not dict or set(data) != {MATRIX, *DOCS}
            or any(type(v) is not str or not v for v in data.values())
            or type(proofs) is not dict or set(proofs) != set(WITNESSES)
            or any(type(v) is not bool for v in proofs.values())):
        return no
    try:
        matrix_rows(data[MATRIX])
    except ValueError:
        return no
    return {
        key: UNKNOWN if not source_matches(key, data)
        else LOCAL if key in WITNESS_FOR and proofs[WITNESS_FOR[key]]
        else GAP if key.rsplit(":", 1)[0] in DOCUMENT_ONLY else UNKNOWN
        for key in IDS
    }


def operational_attestation(_key: object, _evidence: object = None) -> str:
    """No document or synthetic unit test grants external or live authority."""
    return UNKNOWN


class BrechasFactory06Tests(unittest.TestCase):
    def test_contrato_principal(self):
        data = read_sources()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(matrix_rows(data[MATRIX])), set(IDS))
        proofs = run_witnesses()
        self.assertEqual(set(proofs), set(WITNESSES))
        for key in IDS:
            with self.subTest(clause=key):
                self.assertTrue(source_matches(key, data))
                expected = GAP if key.rsplit(":", 1)[0] in DOCUMENT_ONLY else LOCAL
                self.assertEqual(assess(data, proofs)[key], expected)
                self.assertEqual(operational_attestation(key, proofs), UNKNOWN)

    def test_falla_cerrado(self):
        data, proofs = read_sources(), dict.fromkeys(WITNESSES, True)
        for key in IDS:
            row = next(x for x in data[MATRIX].splitlines()
                       if x.startswith(f"| `{key}` |"))
            for wrong in (data[MATRIX].replace(row, "", 1),
                          data[MATRIX] + "\n" + row,
                          data[MATRIX] + "\n" + row.replace(f"| `{key}`", f"|  `{key}`", 1),
                          data[MATRIX].replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
                          data[MATRIX].replace(row, row.replace(CLAUSES[key],
                                                                CLAUSES[key] + " alterado"), 1)):
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(wrong)
                    self.assertEqual(assess({**data, MATRIX: wrong}, proofs)[key],
                                     UNKNOWN)
            doc = key.rsplit(":", 1)[0]
            if key in ANCHORS:
                changed = data[doc].replace(ANCHORS[key][0], "UNKNOWN", 1)
            else:
                lines = data[doc].splitlines(keepends=True)
                n = int(key.rsplit(":L", 1)[-1].split("-", 1)[0])
                lines[n - 1] = "UNKNOWN: absent\n"
                changed = "".join(lines)
            self.assertEqual(assess({**data, doc: changed}, proofs)[key], UNKNOWN)
            if key in WITNESS_FOR:
                missing = {**proofs, WITNESS_FOR[key]: False}
                self.assertEqual(assess(data, missing)[key], UNKNOWN)
        for wrong in (None, {}, "success", {MATRIX: data[MATRIX]}):
            self.assertEqual(set(assess(wrong, proofs).values()), {UNKNOWN})
        self.assertEqual(set(assess(data, {}).values()), {UNKNOWN})

    def test_sin_datos_reales(self):
        own = (ROOT / "tests/test_brechas_factory_06.py").read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(own)):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertEqual(imports, {"__future__", "ast", "pathlib", "re",
                                   "runpy", "sys", "unittest"})
        self.assertEqual(set(WITNESS_FOR.values()), set(WITNESSES))
        self.assertTrue(all((ROOT / "tests" / p).is_file()
                            for p, _, _ in WITNESSES.values()))

    def test_estados_unknown_explicitos(self):
        data = read_sources()
        for key in IDS:
            for claim in (None, True, {"ci": "success", "sha": "f" * 40},
                          {"owner": "APPROVED", "tag": "v1"},
                          {"consumer": "granted", "scopes": ["*"]},
                          {"state": "VALIDATED_IN_PRODUCTION", "backup": True}):
                with self.subTest(key=key):
                    self.assertEqual(operational_attestation(key, claim), UNKNOWN)
            self.assertEqual(assess(data, {})[key], UNKNOWN)
        self.assertEqual(operational_attestation("unknown", {}), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
