"""Factory #1680: sixteen release and resilience clauses, offline fail-closed."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest
from scripts import release_window as rw
from scripts import release_bootstrap as rb
from seguridad import resiliencia as security

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
GUIDE = "docs/release-runbook.md"
RES = "docs/resiliencia-fabrica.md"
BOOT = ".github/workflows/release-bootstrap.yml"
WIN = ".github/workflows/release-window.yml"
RB_CODE = "scripts/release_bootstrap.py"
RW_CODE = "scripts/release_window.py"
SEC_CODE = "seguridad/resiliencia.py"
PATHS = {MATRIX, GUIDE, RES, BOOT, WIN, RB_CODE, RW_CODE, SEC_CODE}
R = "docs/release-runbook.md:L"
S = "docs/resiliencia-fabrica.md:L"
UNKNOWN, LOCAL = "UNKNOWN", "LOCAL_CONTRACT"
SHA = "a" * 40
NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)
TICK = chr(96)

# Exact original line and meaningful independently specified phrase.
CLAUSES = {
    R+"31-U2": (GUIDE, "Ausencia o carrera de resultados"),
    R+"33-U1": (GUIDE, "La puerta"),
    R+"43-U1": (GUIDE, "Un mensaje libre o"),
    R+"43-U2": (GUIDE, "El número de Issue se obtiene"),
    R+"45-U1": (GUIDE, "se movió desde que se abrió la ventana"),
    R+"5-U1": (GUIDE, "El kill switch Factory #767"),
    R+"57-U1": (GUIDE, "El workflow actual también admite"),
    R+"57-U2": (GUIDE, "fue un fallo"),
    R+"59-U1": (GUIDE, "Mientras el canal"),
    R+"61-U1": (GUIDE, "La aprobación anterior no autoriza"),
    R+"65-U1": (GUIDE, "Solo el OWNER autorizado puede mover"),
    R+"81-U1": (GUIDE, "La validación terminal exige"),
    R+"9-U1": (GUIDE, "Si la generación modifica otras copias"),
    R+"96-U1": (GUIDE, "Para cualquier acción futura"),
    S+"10-U1": (RES, "Observador"),
    S+"10-U2": (RES, "los health checks del producto usan endpoints públicos"),
}
# OWNER authority, real claims, release status and public health are external.
GAPS = {R+"5-U1", R+"65-U1", R+"9-U1", R+"96-U1", S+"10-U2"}
LOCAL_KEYS = set(CLAUSES) - GAPS


def documents():
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in PATHS}


def rows(raw):
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: missing coverage")
    found = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = cells[0].strip(TICK) if cells else ""
        if key not in CLAUSES:
            continue
        anchor = CLAUSES[key][1]
        if (key in found or len(cells) != 5 or cells[0] != TICK+key+TICK
                or cells[2] != "NO_VERIFICABLE"
                or anchor.casefold() not in cells[1].casefold()
                or "No se confirmó test + PR fusionado" not in cells[3]
                or not cells[4]):
            raise ValueError("UNKNOWN: malformed, duplicated or promoted row " + key)
        found[key] = cells
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: missing rows")
    return found


def anchor_ok(key, docs):
    if key not in CLAUSES:
        return False
    path, phrase = CLAUSES[key]
    text = docs.get(path)
    if type(text) is not str:
        return False
    try:
        n = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    lines = text.splitlines()
    return 1 <= n <= len(lines) and phrase.casefold() in lines[n-1].casefold()


def rejected(error, fn, *args):
    try:
        fn(*args)
    except error:
        return True
    return False


def evidence(docs):
    """Exercise current pure domain validators; no GitHub/network operations."""
    gate = rw._render_gate("1.0.40", SHA, NOW, source_issue=1680)["body"]
    other = rw._render_gate("1.0.40", "b"*40, NOW, source_issue=1680)["body"]
    missing = rw.plan_request({
        "owner_requested": True, "actor": "pl0n3r", "owner": "pl0n3r",
        "now": "2026-10-29T00:00:00Z", "main_sha": SHA,
        "version": "1.0.40", "candidate_version": "1.0.40",
        "workflows": [], "gates": [],
    })
    not_owner = rw.plan_request({"owner_requested": False,
                                 "actor": "pl0n3r", "owner": "pl0n3r"})
    approved = {"execution_mechanisms": {
        "ci": "github-token:ephemeral", "observer": "github-token:ephemeral",
        "deploy": "hostinger:git",
    }}
    invalid = {"execution_mechanisms": {
        **approved["execution_mechanisms"], "observer": "github-token:persistent",
    }}
    security._validate_execution_mechanisms(approved)
    blocks_persistent = rejected(
        security.ValidationError, security._validate_execution_mechanisms, invalid)
    workflow, code = docs[BOOT], docs[RB_CODE]
    return {
        R+"31-U2": missing.get("reason") == "revalidation_required"
             and len(missing.get("missing_checks", [])) == 5,
        R+"33-U1": "factory-release-window" in gate
             and rw.freeze_gate([], NOW) is None and "factory-release" in docs[WIN],
        R+"43-U1": not_owner == {
            "action": "rejected", "reason": "owner_request_required"}
             and '"safe_default":"B"' in gate,
        R+"43-U2": '"source_issue":1680' in gate
             and "Puerta rearmada desde #1680" in gate,
        R+"45-U1": "la decisión anterior no se hereda" in gate
             and f"main@{SHA}" in gate and gate != other
             and "MAX_REARM_DEPTH = 64" in code,
        R+"5-U1": False,
        R+"57-U1": rb._sha(SHA, "expected_sha") == SHA
             and rejected(rb.ReleaseBootstrapError, rb._sha, "invalid", "expected_sha")
             and "expected_sha:" in workflow and "latest" in workflow,
        R+"57-U2": "require_exact_main_success() {" in workflow
             and "require_exact_main_success" in workflow.split(
                 "require_exact_main_success() {", 1)[1],
        R+"59-U1": "channel-ready:" in workflow
             and '[[ "$v1_sha" == "$APPROVED_SHA" ]]' in workflow
             and "needs: channel-ready" in workflow,
        R+"61-U1": gate != other and '"sha":"'+SHA+'"' in gate
             and '"sha":"'+"b"*40+'"' in other,
        R+"65-U1": False,
        R+"81-U1": "selftest-published:" in workflow
             and "needs: channel-ready" in workflow
             and "uses: pl0n3r/factory/.github/workflows/ci.yml@v1" in workflow
             and "REQUIRED_EXACT_MAIN_CHECKS" in code,
        R+"9-U1": False,
        R+"96-U1": False,
        S+"10-U1": blocks_persistent
             and security._V2_EXECUTION_MECHANISMS["observer"]
                == approved["execution_mechanisms"]["observer"]
             and "cross_repo_write" in docs[SEC_CODE],
        S+"10-U2": False,
    }


def assess(docs, proof):
    if type(docs) is not dict or set(docs) != PATHS:
        return dict.fromkeys(CLAUSES, UNKNOWN)
    if any(type(v) is not str or not v for v in docs.values()):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    try:
        rows(docs[MATRIX])
    except ValueError:
        return dict.fromkeys(CLAUSES, UNKNOWN)
    if (type(proof) is not dict or set(proof) != set(CLAUSES)
            or any(type(v) is not bool for v in proof.values())):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    return {key: LOCAL if key in LOCAL_KEYS and proof[key] and anchor_ok(key, docs)
            else UNKNOWN for key in CLAUSES}


def operational_status(_key, _claim=None):
    """A synthetic test never attests approval, deployment or live health."""
    return UNKNOWN


class BrechasFactory62Tests(unittest.TestCase):
    def test_contrato_principal(self):
        docs = documents()
        proof = evidence(docs)
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(set(rows(docs[MATRIX])), set(CLAUSES))
        self.assertEqual(set(proof), set(CLAUSES))
        for key, result in assess(docs, proof).items():
            with self.subTest(key=key):
                self.assertTrue(anchor_ok(key, docs))
                self.assertEqual(LOCAL if key in LOCAL_KEYS else UNKNOWN, result)

    def test_falla_cerrado(self):
        docs = documents()
        proof = evidence(docs)
        for key, (path, phrase) in CLAUSES.items():
            with self.subTest(key=key):
                line = next(x for x in docs[MATRIX].splitlines()
                            if x.startswith("| "+TICK+key+TICK+" |"))
                for wrong in (
                    docs[MATRIX].replace(line, "", 1),
                    docs[MATRIX]+"\n"+line,
                    docs[MATRIX].replace(line, line.replace(
                        "NO_VERIFICABLE", "CUBIERTO", 1), 1),
                ):
                    self.assertEqual(UNKNOWN, assess({**docs, MATRIX: wrong}, proof)[key])
                number = int(key.split(":L", 1)[1].split("-", 1)[0])
                lines = docs[path].splitlines(keepends=True)
                lines[number - 1] = "CLAUSE_REDACTED_FOR_NEGATIVE_TEST\n"
                self.assertEqual(UNKNOWN, assess({
                    **docs, path: "".join(lines)}, proof)[key])
                self.assertEqual(UNKNOWN, assess(docs, {**proof, key: None})[key])
        self.assertEqual({UNKNOWN}, set(assess({}, proof).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        self.assertTrue(rejected(rw.ReleaseWindowError, rw._sha, "bad", "sha"))
        self.assertTrue(rejected(security.ValidationError,
                                 security.validate_manifest, {"version": 1}))

    def test_sin_datos_reales(self):
        docs = documents()
        self.assertEqual(set(docs), PATHS)
        text = (ROOT/"tests/test_brechas_factory_62.py").read_text(encoding="utf-8")
        nodes = ast.parse(text)
        imported = {alias.name.split(".")[0] for node in ast.walk(nodes)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {(node.module or "").split(".")[0] for node in ast.walk(nodes)
                     if isinstance(node, ast.ImportFrom)}
        self.assertFalse(imported & {"requests", "socket", "urllib", "httpx", "subprocess"})
        self.assertTrue(all(not Path(path).is_absolute() and ".." not in Path(path).parts
                            for path in PATHS))
        self.assertEqual(UNKNOWN, operational_status("v1", {"approved": True}))

    def test_estados_unknown_explicitos(self):
        docs = documents()
        result = assess(docs, evidence(docs))
        self.assertEqual(GAPS, {key for key, value in result.items()
                                if value == UNKNOWN})
        for key in CLAUSES:
            for claim in (None, {}, {"sha": SHA, "CI": "success"},
                          {"owner": "approved", "tag": "v1"},
                          {"live_health": "GREEN", "deployed": True}):
                with self.subTest(key=key, claim=claim):
                    self.assertEqual(UNKNOWN, operational_status(key, claim))


if __name__ == "__main__":
    unittest.main()
