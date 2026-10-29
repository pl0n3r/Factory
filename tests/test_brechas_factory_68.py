"""Factory #1686: 16 fail-closed rollback and Risk Compiler contracts.

All inputs are synthetic. A rollback plan cannot authorize a v1 tag move;
local unit results cannot certify an administrative decision, recovery in a
consumer, a post-rollback run, or a production risk decision.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from scripts.release_auto_rollback_plan import plan_rollback
from intelligence.project_dna import discover_project_dna
from intelligence import risk_compiler as risk

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
RUNBOOK = ROOT / "docs/reusable-release-rollback.md"
RISKDOC = ROOT / "docs/risk-compiler.md"
ROLLBACK_PREFIX = "docs/reusable-release-rollback.md:"
RISK_PREFIX = "docs/risk-compiler.md:"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_SYNTHETIC"
GAP = "BRECHA_DOCUMENTADA"
AFFECTED = "a" * 40
STABLE = "b" * 40

# The source line AND unique matrix row must match the original requirement.
ROLLBACK_LINES = {
    "L57-U1": (57, "SHA estable restaurado"),
    "L58-U1": (58, "repos/workflows afectados"),
    "L59-U1": (59, "run IDs antes y después"),
    "L60-U1": (60, "evidencia de al menos un consumidor recuperado"),
    "L61-U1": (61, "decisión humana/administrativa"),
    "L63-U1": (63, "Después del rollback, la corrección de fondo"),
    "L63-U2": (63, "Nunca uses el rollback como bypass"),
    "L9-U1": (9, "SHA exacto de Factory que está resolviendo"),
}
RISK_LINES = {
    "L12-U1": (12, "señales operativas"),
    "L13-U1": (13, "contexto del proyecto"),
    "L16-U1": (16, "No se usa una media"),
    "L23-U1": (23, "signal"),
    "L24-U1": (24, "source"),
    "L25-U1": (25, "risk"),
    "L26-U1": (26, "reason"),
    "L36-U1": (36, "low: CI, revisión sin hallazgos"),
}
IDS = tuple(ROLLBACK_PREFIX + key for key in ROLLBACK_LINES) + tuple(
    RISK_PREFIX + key for key in RISK_LINES)
# These are not assertions that can be fulfilled without a real incident,
# GitHub provenance, the OWNER, and a new post-rollback consumer run.
GAPS = {
    "L57-U1": "no authenticated proof that stable SHA was restored to v1",
    "L59-U1": "no authenticated post-rollback consumer run IDs",
    "L60-U1": "no new observed recovered consumer after tag restoration",
    "L61-U1": "no human/administrative decision to move v1",
    "L63-U1": "no independent corrective PR and release gate after rollback",
    "L63-U2": "a pure planner cannot attest compatibility of live caller and reusable",
}
POSTCHECKS = [
    "new_consumer_run_materializes_jobs",
    "new_consumer_run_is_not_startup_failure",
    "published_v1_ref_matches_stable_sha",
]


def snapshot() -> dict:
    """Fake chronology: stable consumer run 100 precedes failed run 200."""
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "tag_protected": True,
        "evidence_authenticated": True,  # Fixture claim, NOT real auth.
        "incident_type": "startup_failure",
        "affected_factory_sha": AFFECTED,
        "current_v1_sha": AFFECTED,
        "stable_factory_sha": STABLE,
        "affected_consumer_runs": [{
            "repository": "synthetic/consumer",
            "workflow": "synthetic-validate",
            "run_id": 200,
            "factory_sha": AFFECTED,
            "conclusion": "startup_failure",
            "authenticated": True,
            "materialized_jobs": False,
        }],
        "stable_consumer_runs": [{
            "repository": "synthetic/consumer",
            "workflow": "synthetic-validate",
            "run_id": 100,
            "factory_sha": STABLE,
            "conclusion": "success",
            "authenticated": True,
            "materialized_jobs": True,
        }],
    }


def signals(**changes: object) -> dict:
    data = {
        "production": False, "destructive": False, "migration": False,
        "touches_auth": False, "external_integration": False,
    }
    data.update(changes)
    return data


def dna(*, sparse: bool = False) -> dict:
    if sparse:
        return discover_project_dna(
            paths=["package.json"],
            manifests={"package.json": {
                "dependencies": {"fastify": "^5"}}},
            capabilities=["api"])
    return discover_project_dna(
        paths=["package.json", ".github/workflows/ci.yml", "vercel.json",
               "database/schema.sql", ".sentryclirc"],
        manifests={"package.json": {
            "dependencies": {"fastify": "^5", "@sentry/node": "^9"}}},
        capabilities=["api", "auth"])


def task(change_type: str, surface: str, **flags: object) -> dict:
    return {"id": "synthetic/factory#1686", "title": "Synthetic contract",
            "change_type": change_type, "surfaces": [surface],
            "signals": signals(**flags)}


def risk_cases() -> dict[str, dict]:
    context = dna()
    return {
        "low": risk.compile_risk(
            project_dna=context, task=task("docs", "docs")),
        "medium": risk.compile_risk(
            project_dna=context, task=task("code", "api")),
        "high": risk.compile_risk(
            project_dna=context,
            task=task("security", "auth", touches_auth=True)),
        "doc_high": risk.compile_risk(
            project_dna=context,
            task=task("docs", "docs", production=True)),
        "sparse": risk.compile_risk(
            project_dna=dna(sparse=True),
            task=task("release", "api", production=UNKNOWN)),
    }


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matrix missing")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| " + chr(96) + "docs/"):
            continue
        cells = tuple(piece.strip() for piece in line.strip("|").split("|"))
        if not cells:
            continue
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if (key in found or len(cells) != 5
                or cells[0] != chr(96) + key + chr(96)
                or cells[2] != "NO_VERIFICABLE"
                or "No se confirmó test + PR fusionado" not in cells[3]
                or "[contraste #1574]" not in cells[3]
                or cells[4] != "—"):
            raise ValueError(UNKNOWN + ": changed or duplicated " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": missing clauses " +
                         repr(sorted(set(IDS) - set(found))))
    return found


def source_ok(key: object, documents: object, cells: object) -> bool:
    if type(key) is not str or key not in IDS or not isinstance(documents, dict):
        return False
    if type(cells) not in (tuple, list) or len(cells) != 5:
        return False
    if key.startswith(ROLLBACK_PREFIX):
        path = "rollback"
        line_no, fragment = ROLLBACK_LINES[key[len(ROLLBACK_PREFIX):]]
    else:
        path = "risk"
        line_no, fragment = RISK_LINES[key[len(RISK_PREFIX):]]
    src = documents.get(path)
    if type(src) is not str:
        return False
    lines = src.splitlines()
    return (len(lines) >= line_no
            and fragment.casefold() in lines[line_no - 1].casefold()
            and cells[1] in lines[line_no - 1])


def blocked(**changes: object) -> bool:
    case = snapshot()
    case.update(changes)
    decision = plan_rollback(case)
    return (decision["decision"] == "BLOCKED"
            and decision["authorizes_tag_move"] is False
            and decision["mutations"] == 0
            and decision["proposed_stable_sha"] is None)


def risk_witness(suffix: str, cases: dict) -> bool:
    low, medium, high = (cases[k] for k in ("low", "medium", "high"))
    doc_high, sparse = cases["doc_high"], cases["sparse"]
    trace = high["trace"]
    sources = {row["source"] for row in trace}
    controls = {key: {c["target"] for c in cases[key]["controls"]}
                for key in ("low", "medium", "high")}
    probes = {
        "L12-U1": lambda: (
            high["dimensions"]["signals"] == "high"
            and any(row["source"] == "task.signals.touches_auth"
                    and row["risk"] == "high" for row in trace)),
        "L13-U1": lambda: (
            sparse["risk"] == "high"
            and sparse["context_complete"] is False
            and "project_dna.hosting" in sparse["unknown_critical_signals"]),
        "L16-U1": lambda: (
            doc_high["dimensions"]["change"] == "low"
            and doc_high["dimensions"]["signals"] == "high"
            and doc_high["risk"] == "high"
            and high["risk"] == "high"),
        "L23-U1": lambda: all(type(row["signal"]) is str
                              and bool(row["signal"]) for row in trace)
                              and any(row["signal"] == "touches_auth:true"
                                      for row in trace),
        "L24-U1": lambda: (
            all(type(row["source"]) is str and row["source"] for row in trace)
            and "task.signals.touches_auth" in sources
            and all(set(c["sources"]) <= sources for c in high["controls"])),
        "L25-U1": lambda: (
            all(row["risk"] in risk.RISK_LEVELS for row in trace)
            and any(row["risk"] == "high" for row in trace)
            and all(b["risk"] in ("medium", "high")
                    for b in high["blast_radius"])),
        "L26-U1": lambda: all(type(row["reason"]) is str
                              and bool(row["reason"].strip()) for row in trace),
        "L36-U1": lambda: (
            low["risk"] == "low"
            and set(risk.BASE_CONTROLS) == controls["low"]
            and controls["low"] < controls["medium"] < controls["high"]),
    }
    try:
        return probes[suffix]() is True
    except (KeyError, TypeError, ValueError):
        return False


def evidence(key: object, docs: object, rollback: object,
             decision: object, risks: object) -> str:
    """No synthetic result can demonstrate real v1 restoration or promotion."""
    if (type(key) is not str or key not in IDS
            or not isinstance(docs, dict) or not isinstance(rollback, dict)
            or not isinstance(decision, dict) or not isinstance(risks, dict)):
        return UNKNOWN
    try:
        found = matrix_rows(docs.get("matrix"))
    except ValueError:
        return UNKNOWN
    if not source_ok(key, docs, found[key]):
        return UNKNOWN
    if key.startswith(ROLLBACK_PREFIX):
        expected = snapshot()
        computed = plan_rollback(expected)
        if (rollback != expected or decision != computed
                or computed["decision"] != "HUMAN_GATE_REQUIRED"
                or computed["reason"] != "owner_must_authorize_v1_rollback"
                or computed["proposed_stable_sha"] != STABLE
                or computed["authorizes_tag_move"] is not False
                or computed["mutations"] != 0
                or computed["postrollback_verification_required"] != POSTCHECKS):
            return UNKNOWN
        suffix = key[len(ROLLBACK_PREFIX):]
        witnesses = {
            "L9-U1": lambda: (
                rollback["affected_factory_sha"] == rollback["current_v1_sha"]
                and blocked(current_v1_sha="c" * 40)
                and blocked(affected_factory_sha="not-a-sha")),
            "L58-U1": lambda: (
                rollback["affected_consumer_runs"][0]["repository"]
                == rollback["stable_consumer_runs"][0]["repository"]
                and rollback["affected_consumer_runs"][0]["workflow"]
                == rollback["stable_consumer_runs"][0]["workflow"]
                and blocked(stable_consumer_runs=[])
                and blocked(affected_consumer_runs=[])),
        }
        if suffix in GAPS:
            return GAP
        return LOCAL if witnesses[suffix]() else UNKNOWN
    expected_cases = risk_cases()
    if risks != expected_cases:
        return UNKNOWN
    suffix = key[len(RISK_PREFIX):]
    return LOCAL if risk_witness(suffix, risks) else UNKNOWN


def operational(_key: object, _claims: object = None) -> str:
    return UNKNOWN


class BrechasFactory68Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.docs = {
            "matrix": MATRIX.read_text(encoding="utf-8"),
            "rollback": RUNBOOK.read_text(encoding="utf-8"),
            "risk": RISKDOC.read_text(encoding="utf-8"),
        }
        cls.snapshot = snapshot()
        cls.before = deepcopy(cls.snapshot)
        cls.planned = plan_rollback(cls.snapshot)
        cls.risks = risk_cases()

    def test_contrato_principal(self) -> None:
        self.assertEqual(16, len(IDS))
        self.assertEqual(16, len(set(IDS)))
        self.assertEqual(set(IDS), set(matrix_rows(self.docs["matrix"])))
        self.assertEqual(self.snapshot, self.before)
        for key in IDS:
            with self.subTest(row=key):
                self.assertTrue(source_ok(key, self.docs,
                                          matrix_rows(self.docs["matrix"])[key]))
                outcome = evidence(key, self.docs, self.snapshot,
                                   self.planned, self.risks)
                suffix = key[len(ROLLBACK_PREFIX):] if key.startswith(
                    ROLLBACK_PREFIX) else ""
                self.assertEqual(GAP if suffix in GAPS else LOCAL, outcome)
                self.assertEqual(UNKNOWN, operational(key, outcome))
        self.assertEqual(POSTCHECKS,
                         self.planned["postrollback_verification_required"])

    def test_falla_cerrado(self) -> None:
        matrix = self.docs["matrix"]
        for key in IDS:
            row = next(line for line in matrix.splitlines()
                       if line.startswith("| " + chr(96) + key + chr(96) + " |"))
            for bad_matrix in (
                matrix.replace(row, "", 1),
                matrix + "\n" + row,
                matrix.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(bad_matrix)
                self.assertEqual(UNKNOWN, evidence(
                    key, {**self.docs, "matrix": bad_matrix},
                    self.snapshot, self.planned, self.risks))
            doc_key = "rollback" if key.startswith(ROLLBACK_PREFIX) else "risk"
            self.assertEqual(UNKNOWN, evidence(
                key, {**self.docs, doc_key: ""},
                self.snapshot, self.planned, self.risks))
        for changes in (
            {"tag_protected": False},
            {"evidence_authenticated": False},
            {"stable_factory_sha": AFFECTED},
            {"affected_consumer_runs": []},
            {"stable_consumer_runs": []},
            {"kill_switch_state": "PAUSED"},
        ):
            with self.subTest(change=changes):
                self.assertTrue(blocked(**changes))
        self.assertEqual(UNKNOWN, evidence(
            IDS[0], self.docs, {"ci": "success"}, self.planned, self.risks))
        self.assertEqual(UNKNOWN, evidence(
            IDS[-1], self.docs, self.snapshot, self.planned, {"risk": "low"}))
        self.assertEqual(UNKNOWN, evidence(
            "docs/risk-compiler.md:L999-U1", self.docs, self.snapshot,
            self.planned, self.risks))
        with self.assertRaises(risk.RiskCompilerError):
            risk.compile_risk(project_dna=dna(),
                              task={**task("docs", "docs"), "signals": {}})

    def test_sin_datos_reales(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        syntax = ast.parse(source)
        modules = {alias.name.split(".")[0] for node in ast.walk(syntax)
                   if isinstance(node, ast.Import) for alias in node.names}
        modules |= {node.module.split(".")[0] for node in ast.walk(syntax)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(modules & {
            "requests", "httpx", "urllib", "socket", "subprocess", "os",
            "boto3", "mysql", "playwright", "selenium", "github"})
        self.assertEqual("synthetic/consumer",
                         self.snapshot["affected_consumer_runs"][0]["repository"])
        self.assertEqual(100, self.snapshot["stable_consumer_runs"][0]["run_id"])
        self.assertEqual(200, self.snapshot["affected_consumer_runs"][0]["run_id"])
        self.assertNotIn("BEGIN " + "PRIVATE KEY", source)
        self.assertEqual(self.snapshot, self.before)

    def test_estados_unknown_explicitos(self) -> None:
        rows = matrix_rows(self.docs["matrix"])
        self.assertEqual(set(IDS), set(rows))
        for key in IDS:
            with self.subTest(row=key):
                self.assertEqual("NO_VERIFICABLE", rows[key][2])
                self.assertEqual(UNKNOWN, operational(key, {
                    "ci": "success", "review": "approved",
                    "v1": "restored", "consumer_recovered": True}))
        for suffix in GAPS:
            key = ROLLBACK_PREFIX + suffix
            self.assertEqual(GAP, evidence(
                key, self.docs, self.snapshot, self.planned, self.risks))
        self.assertEqual("HUMAN_GATE_REQUIRED", self.planned["decision"])
        self.assertFalse(self.planned["authorizes_tag_move"])
        self.assertEqual(0, self.planned["mutations"])
        self.assertNotIn("VALIDATED_IN_PRODUCTION",
                         {evidence(key, self.docs, self.snapshot,
                                   self.planned, self.risks) for key in IDS})


if __name__ == "__main__":
    unittest.main()
