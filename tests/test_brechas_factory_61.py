"""Factory #1679: sixteen Recovery and release gaps, offline and fail closed.

Local contracts are not evidence of authenticated release, ownership, production
backup, restore, published v1 or a merged candidate PR.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

from recovery.status import derive_recovery_health, project_recovery_readiness
from scripts import release_window

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
RECOVERY = "docs/recovery-status.md"
BOOTSTRAP = "docs/release-bootstrap.md"
RUNBOOK = "docs/release-runbook.md"
RW = "scripts/release_window.py"
RB = "scripts/release_bootstrap.py"
WINFLOW = ".github/workflows/release-window.yml"
BOOTFLOW = ".github/workflows/release-bootstrap.yml"
RELEASEFLOW = ".github/workflows/release.yml"
CI = ".github/workflows/factory-ci.yml"
SONAR = ".github/workflows/sonar.yml"
CODEQL = ".github/workflows/codeql-evidence.yml"
WATCHDOG = ".github/workflows/reusable-release-watchdog.yml"
HUMAN = "docs/puertas-humanas.md"
PLAN = "PLAN-AGENTES.md"
VERSION = "config/version.json"
PATHS = {MATRIX, RECOVERY, BOOTSTRAP, RUNBOOK, RW, RB, WINFLOW,
         BOOTFLOW, RELEASEFLOW, CI, SONAR, CODEQL, WATCHDOG, HUMAN,
         PLAN, VERSION}
UNKNOWN, LOCAL, GAP = "UNKNOWN", "LOCAL_CONTRACT", "BRECHA_DOCUMENTADA"
REC = "docs/recovery-status.md:L"
REL = "docs/release-runbook.md:L"
BOOT = "docs/release-bootstrap.md:B"
CLAUSES = {
    REC + "8-U1": (RECOVERY, "UNKNOWN", 8),
    REC + "8-U2": (RECOVERY, "Nunca cuenta como sano.", 8),
    REC + "9-U1": (RECOVERY, "BLOCKED", 9),
    BOOT + "01": (BOOTSTRAP, "trust root v1", None),
    BOOT + "02": (BOOTSTRAP, "factory-release", None),
    BOOT + "03": (BOOTSTRAP, "channel-ready", None),
    BOOT + "04": (BOOTSTRAP, "deriva", None),
    BOOT + "05": (BOOTSTRAP, "compatibilidad", None),
    REL + "100-U1": (RUNBOOK, "Workflow de ventana y evaluador.", 100),
    REL + "101-U1": (RUNBOOK, "Bootstrap, reusable release y guía de release.", 101),
    REL + "102-U1": (RUNBOOK, "CI factory, Sonar y CodeQL.", 102),
    REL + "103-U1": (RUNBOOK, "Puertas humanas, reglas de agentes y reparación #1436.", 103),
    REL + "18-U1": (RUNBOOK, "Verificar la prueba concreta del nuevo número", 18),
    REL + "18-U2": (RUNBOOK, "Fusionar el PR del candidato solo tras", 18),
    REL + "24-U1": (RUNBOOK, "solo OWNER", 24),
    REL + "31-U1": (RUNBOOK, "Revalida para el HEAD exacto", 31),
}
GAPS = {
    BOOT + "05": "freeze, TTL y provenance no acreditados por lectura local",
    REL + "18-U1": "versión candidata y fuentes de release externas sin evidencia",
    REL + "18-U2": "PR y CI exact-HEAD externos no acreditados",
}
FIXED_NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)
SYNTHETIC_SHA = "a" * 40


def documents():
    return {name: (ROOT / name).read_text(encoding="utf-8") for name in PATHS}


def rows(raw):
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matrix missing")
    result = {}
    for line in raw.splitlines():
        if not line.startswith("|"):
            continue
        cells = tuple(x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = cells[0].strip(chr(96)) if cells else ""
        if key not in CLAUSES:
            continue
        phrase = CLAUSES[key][1]
        if (key in result or len(cells) != 5 or
                cells[0] != chr(96) + key + chr(96) or
                cells[2] != "NO_VERIFICABLE" or
                phrase.casefold() not in cells[1].casefold() or
                not cells[3] or not cells[4]):
            raise ValueError(UNKNOWN + ": invalid, duplicate or promoted " + key)
        if key.startswith(BOOT):
            if "Contrastado por comportamiento" not in cells[3]:
                raise ValueError(UNKNOWN + ": bootstrap evidence missing")
        elif "No se confirmó test + PR fusionado" not in cells[3]:
            raise ValueError(UNKNOWN + ": missing merge evidence")
        result[key] = cells
    if set(result) != set(CLAUSES):
        raise ValueError(UNKNOWN + ": incomplete rows")
    return result


def anchor(key, docs):
    if key not in CLAUSES:
        return False
    path, phrase, number = CLAUSES[key]
    if type(docs.get(path)) is not str:
        return False
    if number is None:
        return phrase.casefold() in docs[path].casefold()
    lines = docs[path].splitlines()
    return 1 <= number <= len(lines) and phrase.casefold() in lines[number - 1].casefold()


def manifest():
    return {
        "version": 1, "project": "factory",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "NOT_APPLICABLE"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def proofs(docs):
    """Only synthetic domain functions and checked-in files are inspected."""
    missing = derive_recovery_health(
        manifest(), None, None, observed_at="2026-10-29T00:00:00Z")
    invalid = derive_recovery_health(
        manifest(), {"version": 1, "status": "VERIFIED"},
        None, observed_at="2026-10-29T00:00:00Z")
    readiness = project_recovery_readiness(missing, critical=True)
    denied = release_window.plan_request({
        "owner_requested": False, "actor": "anonymous", "owner": "pl0n3r"})
    no_checks = release_window.plan_request({
        "owner_requested": True, "actor": "pl0n3r", "owner": "pl0n3r",
        "now": "2026-10-29T00:00:00Z", "main_sha": SYNTHETIC_SHA,
        "version": "1.0.40", "candidate_version": "1.0.40",
        "workflows": [], "gates": [],
    })
    release = docs[RELEASEFLOW]
    bootstrap = docs[BOOTFLOW]
    code = docs[RB]
    gate = release_window._render_gate(
        "1.0.40", SYNTHETIC_SHA, FIXED_NOW, source_issue=1679)["body"]
    different = release_window._render_gate(
        "1.0.40", "b" * 40, FIXED_NOW, source_issue=1679)["body"]
    return {
        REC + "8-U1": missing["state"] == "UNKNOWN"
            and "backup_missing" in missing["work_item_classes"],
        REC + "8-U2": not readiness["ready"]
            and readiness["critical_blocker"]
            and readiness["recovery_health"] == "UNKNOWN",
        REC + "9-U1": invalid["state"] == "BLOCKED"
            and project_recovery_readiness(invalid)["ready"] is False,
        BOOT + "01": "repository: pl0n3r/factory" in release
            and "ref: v1" in release and "inputs.kit_ref" not in release
            and "kit_ref:" not in release,
        BOOT + "02": denied == {
            "action": "rejected", "reason": "owner_request_required"}
            and "factory-release-window" in gate
            and "factory-human-decision" in code
            and "fingerprint" in code,
        BOOT + "03": "channel-ready:" in bootstrap
            and "selftest-published:" in bootstrap
            and "needs: channel-ready" in bootstrap,
        BOOT + "04": gate != different
            and f"main@{SYNTHETIC_SHA}" in gate
            and "MAX_REARM_DEPTH" in code,
        BOOT + "05": release_window.freeze_gate([], FIXED_NOW) is None
            and "freeze" in docs[RW].lower()
            and "channel-ready:" in bootstrap,
        REL + "100-U1": ("release-window.yml" in docs[RUNBOOK]
                           and "plan_request" in docs[RW]
                           and "workflow_dispatch:" in docs[WINFLOW]),
        REL + "101-U1": ("release-bootstrap.yml" in docs[RUNBOOK]
                           and "release.yml" in docs[RUNBOOK]
                           and "expected_sha" in bootstrap),
        REL + "102-U1": all(
            name in docs[RUNBOOK] for name in
            ("factory-ci.yml", "sonar.yml", "codeql-evidence.yml"))
            and all(docs[name].strip() for name in (CI, SONAR, CODEQL)),
        REL + "103-U1": ("puertas-humanas.md" in docs[RUNBOOK]
                           and "PLAN-AGENTES.md" in docs[RUNBOOK]
                           and "#1436" in docs[RUNBOOK]
                           and bool(docs[HUMAN].strip())),
        REL + "18-U1": ("test_release_candidate_" in docs[RUNBOOK]
                          and "config/version.json" in docs[RUNBOOK]
                          and bool(docs[VERSION].strip())),
        REL + "18-U2": ("Validar" in docs[RUNBOOK]
                          and "exact-HEAD" in docs[RUNBOOK]
                          and "revalidation_required" in docs[RW]),
        REL + "24-U1": denied.get("reason") == "owner_request_required"
            and "solo OWNER" in docs[RUNBOOK]
            and "workflow_dispatch:" in docs[WINFLOW],
        REL + "31-U1": no_checks.get("reason") == "revalidation_required"
            and len(no_checks.get("missing_checks", [])) == 5
            and "main_sha" in docs[RW]
            and all(docs[name].strip() for name in (CI, SONAR, CODEQL, WATCHDOG)),
    }


def assess(docs, observations):
    if (type(docs) is not dict or set(docs) != PATHS
            or any(type(v) is not str or not v for v in docs.values())):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    try:
        rows(docs[MATRIX])
    except ValueError:
        return dict.fromkeys(CLAUSES, UNKNOWN)
    if (type(observations) is not dict or set(observations) != set(CLAUSES)
            or any(type(value) is not bool for value in observations.values())):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    return {key: (LOCAL if observations[key] and anchor(key, docs)
                  else UNKNOWN) if key not in GAPS
            else (GAP if observations[key] and anchor(key, docs) else UNKNOWN)
            for key in CLAUSES}


def operational(_key, _observation=None):
    """Never claim actual release, backup, restore or deployed CI here."""
    return UNKNOWN


class BrechasFactory61Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = documents()
        cls.observed = proofs(cls.docs)

    def test_contrato_principal(self):
        self.assertEqual(set(CLAUSES), set(rows(self.docs[MATRIX])))
        self.assertEqual(set(CLAUSES), set(self.observed))
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertTrue(anchor(key, self.docs))
                self.assertIs(self.observed[key], True)
                self.assertEqual(GAP if key in GAPS else LOCAL,
                                 assess(self.docs, self.observed)[key])
                self.assertEqual(UNKNOWN, operational(key, self.observed[key]))

    def test_falla_cerrado(self):
        raw = self.docs[MATRIX]
        for key in CLAUSES:
            line = next(x for x in raw.splitlines()
                        if x.startswith("| " + chr(96) + key + chr(96) + " |"))
            for invalid in (
                raw.replace(line, "", 1),
                raw + "\n" + line,
                raw.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1),
                raw.replace(line, line.replace(CLAUSES[key][1], "INDEFINIDO", 1), 1),
            ):
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        rows(invalid)
                    self.assertEqual(UNKNOWN, assess(
                        {**self.docs, MATRIX: invalid}, self.observed)[key])
            self.assertEqual(UNKNOWN, assess(self.docs, {})[key])
            for path in PATHS:
                self.assertEqual(UNKNOWN, assess(
                    {**self.docs, path: ""}, self.observed)[key])
        self.assertEqual(set(assess({}, self.observed).values()), {UNKNOWN})
        self.assertEqual(set(assess(self.docs, {**self.observed, "ci": True}).values()),
                         {UNKNOWN})

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {alias.name.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.Import) for alias in node.names}
        names |= {node.module.split(".")[0] for node in ast.walk(tree)
                  if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(names & {"requests", "urllib", "httpx", "socket",
                                  "playwright", "selenium", "pymysql"})
        self.assertEqual(SYNTHETIC_SHA, "a" * 40)
        self.assertEqual(0, len([x for x in PATHS if x.startswith("storage/")]))
        self.assertEqual(UNKNOWN, operational(REC + "8-U1", {"production": "GREEN"}))

    def test_estados_unknown_explicitos(self):
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual("NO_VERIFICABLE", rows(self.docs[MATRIX])[key][2])
                for claim in (None, True, {"ci": "success"},
                              {"main": SYNTHETIC_SHA}, {"release": "published"},
                              {"backup": "VERIFIED"}, {"restore": "PASSED"}):
                    self.assertEqual(UNKNOWN, operational(key, claim))
                self.assertEqual(UNKNOWN, assess(
                    self.docs, {**self.observed, key: False})[key])
        self.assertFalse(anchor(BOOT + "01", {**self.docs, BOOTSTRAP: ""}))


if __name__ == "__main__":
    unittest.main()
