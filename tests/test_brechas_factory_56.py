"""Factory #1674: 16 fail-closed Sonar Watch units using synthetic evidence.

Never start Sonar Watch, contact Sonar/GitHub, sync actual Issues, or claim live
readiness from a local test.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from quality.sonar import normalize_sonar_snapshot

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN, LOCAL, NOW = "UNKNOWN", "CONTRATO_LOCAL", "2026-09-30T12:00:00Z"
BT = chr(96)
MATRIX = "docs/matriz-cobertura.md"
GUIDE = "docs/quality-sonar-watch.md"
SCRIPT = "scripts/sonar-watch.py"
CONFIG = "quality/sonar-watch-config.json"
CI = ".github/workflows/sonar.yml"
CODEQL = ".github/workflows/codeql-evidence.yml"
TESTS = "tests/test_sonar_watch.py"
FILES = (MATRIX, GUIDE, SCRIPT, CONFIG, CI, CODEQL, TESTS)
CLAUSES = {
    "L30-U1": (30, "Si alguno exige"),
    "L32-U1": (32, "Payload ausente o ambiguo falla cerrado"),
    "L32-U2": (32, "no se convierte en política implícita"),
    "L42-U1": (42, "El parser exige exactamente un setting"),
    "L42-U2": (42, "Ausencia, duplicidad, key inesperada"),
    "L46-U1": (46, "esto **no autoriza ejecutarlo**"),
    "L48-U1": (48, "Los checks **Sonar CI-based**"),
    "L52-U1": (52, "solo lo cierra con freshness"),
    "L52-U2": (52, "Una señal"),
    "L54-U1": (54, "Todo Issue abierto"),
    "L54-U2": (54, "Las alertas son observaciones"),
    "L54-U3": (54, "En cierre verificado"),
    "L54-U4": (54, "el contenido histórico no se reescribe como PASS"),
    "L54-U5": (54, "Se preservan etiquetas fuera"),
    "L56-U1": (56, "El cuerpo conserva estado"),
    "L60-U1": (60, "ControlBot y Factory usan CI"),
}
IDS = tuple(GUIDE + ":" + label for label in CLAUSES)


def sources():
    return {name: (ROOT / name).read_text(encoding="utf-8") for name in FILES}


def rows(matrix):
    if type(matrix) is not str or not matrix:
        raise ValueError("UNKNOWN: missing matrix")
    found = {}
    for line in matrix.splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        if not cells:
            continue
        key = cells[0].strip(BT)
        if key not in IDS:
            continue
        if (key in found or len(cells) != 5 or cells[0] != BT + key + BT
                or cells[2] != "NO_VERIFICABLE"
                or "Contraste #1573" not in cells[3]
                or "faltan aserción exacta y PR MERGED" not in cells[3]
                or cells[4] != "—"):
            raise ValueError("UNKNOWN: missing/duplicate/promoted " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: incomplete sixteen rows")
    return found


def source_clause(key, data):
    if type(key) is not str or key not in IDS or type(data) is not dict:
        return False
    text = data.get(GUIDE)
    if type(text) is not str:
        return False
    n, anchor = CLAUSES[key.rsplit(":", 1)[1]]
    lines = text.splitlines()
    return n <= len(lines) and anchor in lines[n-1]


def watcher():
    spec = importlib.util.spec_from_file_location("factory_1674_sonar", ROOT / SCRIPT)
    if spec is None or spec.loader is None:
        raise ValueError("UNKNOWN: watcher absent")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(project="factory", method="ci", coverage=True, visibility="public"):
    return {
        "project": project, "snapshot_at": "2026-09-30T11:55:00Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {"analyzed_at": "2026-09-30T11:50:00Z",
                     "method": method, "coverage_available": coverage},
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50}, "visibility": visibility,
        "debt": [], "evidence_refs": ["sonar:synthetic:snapshot:001"],
    }


class FakeIssues:
    def __init__(self):
        self.items, self.comments, self.actions = [], {}, []

    def find(self, marker):
        return [x.copy() for x in self.items if marker in x["body"]]

    def create(self, *, title, body, labels):
        row = {"number": len(self.items) + 1, "title": title, "body": body,
               "labels": list(labels), "state": "open"}
        self.items.append(row)
        self.actions.append(("create", row["number"]))

    def update(self, number, *, title, body, state, labels):
        row = next(x for x in self.items if x["number"] == number)
        row.update(title=title, body=body, labels=list(labels), state=state)
        self.actions.append(("update", number, state))

    def comment_once(self, number, *, marker, body):
        existing = self.comments.setdefault(number, [])
        if any(marker in item for item in existing):
            return False
        existing.append(body)
        return True


def sync(watch, cfg, observation, issues, now=NOW):
    return watch.sync_project(
        contract=cfg["contract"], snapshot=observation, observed_at=now,
        project_ref=cfg["github_repo"], origin_ref="sonar:synthetic:reference",
        origin_url=watch._origin_url(cfg["sonar_key"]), issues=issues,
    )


def rejects(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except (ValueError, TypeError, KeyError):
        return True
    return False


def behavior(data):
    watch = watcher()
    configs = watch.load_runtime_config()
    cfg = {item["project"]: item for item in configs}
    factory, brvtal = cfg["factory"], cfg["brvtal"]
    proof = {}
    with patch.object(watch, "urlopen",
                      side_effect=AssertionError("network prohibited")) as network:
        api = watch.SonarApi(token="")
        calls = []
        api.get = lambda *_args, **_kwargs: calls.append("network")
        private = deepcopy(configs)
        private[0]["contract"]["sonar"]["expected_visibility"] = "private"
        proof["L30-U1"] = rejects(api.preflight_visibility, private) and not calls

        api.get = lambda *_a, **_kw: {}
        absent = rejects(api.preflight_visibility, [factory])
        api.get = lambda *_a, **_kw: {"component": {"visibility": "indeterminate"}}
        ambiguous = rejects(api.preflight_visibility, [factory])
        proof["L32-U1"] = absent and ambiguous
        api.get = lambda *_a, **_kw: {"component": {"visibility": "private"}}
        observed = api.preflight_visibility([factory])
        drift = snapshot(visibility=observed["factory"])
        signals = normalize_sonar_snapshot(factory["contract"], drift,
                                           observed_at=NOW)["signals"]
        visibility = next(x for x in signals if x["signal"] == "visibility")
        proof["L32-U2"] = (
            observed == {"factory": "private"} and visibility["status"] == "FAIL"
            and factory["contract"]["sonar"]["expected_visibility"] == "public"
        )

        parse = watch.SonarApi.analysis_method_from_settings
        valid = lambda value: {"settings": [{"key": "sonar.autoscan.enabled",
                                             "value": value}]}
        proof["L42-U1"] = (parse(valid("true")) == "automatic"
                          and parse(valid("false")) == "ci")
        bad = (None, {}, {"settings": []},
               {"settings": valid("true")["settings"] * 2},
               {"settings": [{"key": "wrong", "value": "true"}]},
               valid(True), valid("TRUE"), valid(""))
        proof["L42-U2"] = all(rejects(parse, item) for item in bad)
        proof["L46-U1"] = (
            "def run_live()" in data[SCRIPT]
            and not (ROOT / ".github/workflows/sonar-watch.yml").exists()
            and "test_runtime_auth_and_settings_scenarios_are_fail_closed" in data[TESTS]
        )
        readonly = watch.HttpJson(token="", base_url="https://sonarcloud.io",
                                  read_only=True)
        proof["L48-U1"] = (
            rejects(readonly.request, "/api/autoscan/activation", method="POST")
            and "sonar" in data[CI].lower() and "codeql" in data[CODEQL].lower()
            and not (ROOT / ".github/workflows/sonar-watch.yml").exists()
        )

        # A real classifier and synchronizer, but only an in-memory Issues API.
        issues = FakeIssues()
        marker = watch.issue_marker("factory", "visibility")
        fail_ops = sync(watch, factory, snapshot(visibility="private"), issues)
        first = issues.find(marker)
        previous = deepcopy(first[0]) if len(first) == 1 else {}
        repeat = sync(watch, factory, snapshot(visibility="private"), issues)
        pass_ops = sync(watch, factory, snapshot(), issues)
        closed_rows = issues.find(marker)
        closed = closed_rows[0] if len(closed_rows) == 1 else {}
        proof["L52-U1"] = (
            len(first) == len(closed_rows) == 1
            and previous.get("state") == "open"
            and closed.get("state") == "closed"
            and {"created", "updated", "closed"} <= {
                x["action"] for x in fail_ops + repeat + pass_ops
                if x["signal"] == "visibility"
            }
        )
        proof["L54-U1"] = previous.get("labels") == [
            "tipo: calidad", "prioridad: media", "estado: bloqueado"
        ]
        proof["L54-U2"] = all(
            phrase in previous.get("body", "") for phrase in (
                "Motivo del bloqueo:", "Condición de desbloqueo:",
                "PASS/CURRENT", "NOT_APPLICABLE",
            )
        )
        proof["L54-U3"] = (
            closed.get("state") == "closed"
            and "estado: completado" in closed.get("labels", [])
            and "estado: bloqueado" not in closed.get("labels", [])
        )
        proof["L54-U4"] = (
            closed.get("body") == previous.get("body")
            and "Estado: " + BT + "FAIL" + BT in closed.get("body", "")
        )
        proof["L56-U1"] = all(
            phrase in previous.get("body", "") for phrase in (
                "Estado:", "Razón:", "Freshness:", "### Evidencia",
                "sonar:synthetic:snapshot:001",
                "https://sonarcloud.io/project/overview?id=pl0n3r_factory",
            )
        ) and rejects(watch._origin_url, "invalid/?token=synthetic")

        # Genuine NOT_APPLICABLE comes only from the pinned Factory #516
        # coverage policy; close a historical alert once without rewriting it.
        history = "Historical coverage FAIL; never rewrite this as PASS"
        na = FakeIssues()
        na_marker = watch.issue_marker("brvtal", "coverage")
        na.create(title="historical", body=na_marker + "\n" + history,
                  labels=["tipo: calidad", "prioridad: media",
                          "estado: bloqueado", "audit: synthetic"])
        automatic = snapshot("brvtal", "automatic", False)
        na_ops = sync(watch, brvtal, automatic, na)
        sync(watch, brvtal, automatic, na)
        na_rows = na.find(na_marker)
        item = na_rows[0] if len(na_rows) == 1 else {}
        notes = na.comments.get(item.get("number"), [])
        proof["L52-U2"] = (
            len(na_rows) == 1 and item.get("state") == "closed"
            and len(notes) == 1 and "NOT_APPLICABLE" in notes[0]
            and "pl0n3r/Factory#516" in notes[0]
            and any(x["action"] == "closed_not_applicable"
                    and x["signal"] == "coverage" for x in na_ops)
        )
        proof["L54-U5"] = (
            "audit: synthetic" in item.get("labels", [])
            and history in item.get("body", "")
            and rejects(watch._auto_issue_labels,
                        {"labels": ["tipo: unexpected"]}, state="open")
            and rejects(watch._auto_issue_labels,
                        {"labels": ["estado: disponible", "audit: synthetic"]},
                        state="open")
        )

        coverage_checks = []
        for name in ("factory", "controlbot"):
            cfg_item = cfg[name]
            raw = snapshot(name, "ci", False)
            normalized = normalize_sonar_snapshot(cfg_item["contract"], raw,
                                                  observed_at=NOW)
            coverage = next(x for x in normalized["signals"]
                            if x["signal"] == "coverage")
            coverage_checks.append(
                cfg_item["contract"]["sonar"]["analysis_method"] == "ci"
                and cfg_item["contract"]["sonar"]["applicability"]["coverage"]["state"]
                == "required"
                and coverage["status"] == "FAIL"
                and coverage["reason"] == "coverage_missing_for_ci"
            )
        proof["L60-U1"] = len(configs) == 6 and all(coverage_checks)
        network.assert_not_called()
    return {GUIDE + ":" + unit: proof[unit] for unit in CLAUSES}


def verdict(unit, data, proof):
    if (type(unit) is not str or unit not in IDS or type(data) is not dict
            or set(data) != set(FILES) or type(proof) is not dict
            or set(proof) != set(IDS)
            or any(type(value) is not bool for value in proof.values())
            or any(type(value) is not str or not value for value in data.values())
            or not source_clause(unit, data)):
        return UNKNOWN
    try:
        rows(data[MATRIX])
    except ValueError:
        return UNKNOWN
    return LOCAL if proof[unit] else UNKNOWN


def operational(_unit, _claim=None):
    return UNKNOWN


class BrechasFactory56Tests(unittest.TestCase):
    def test_contrato_principal(self):
        data = sources()
        proof = behavior(data)
        self.assertEqual(16, len(IDS))
        self.assertEqual(set(IDS), set(rows(data[MATRIX])))
        self.assertEqual(set(IDS), set(proof))
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertTrue(source_clause(unit, data))
                self.assertTrue(proof[unit], unit)
                self.assertEqual(LOCAL, verdict(unit, data, proof))

    def test_falla_cerrado(self):
        data, proof = sources(), behavior(sources())
        raw = data[MATRIX]
        for unit in IDS:
            row = next(x for x in raw.splitlines()
                       if x.startswith("| " + BT + unit + BT + " |"))
            for damaged in (
                raw.replace(row, "", 1), raw + "\n" + row,
                raw.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(unit=unit):
                    self.assertEqual(UNKNOWN, verdict(unit, {**data, MATRIX: damaged}, proof))
            self.assertEqual(UNKNOWN, verdict(unit, data, {}))
            self.assertEqual(UNKNOWN, verdict(unit, data, {**proof, unit: None}))
            self.assertEqual(UNKNOWN, verdict(unit, {**data, GUIDE: ""}, proof))
        self.assertEqual(UNKNOWN, verdict("not-a-row", data, proof))

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {x.module.split(".")[0] for x in ast.walk(tree)
                   if isinstance(x, ast.ImportFrom) and x.module}
        imports.update(y.name.split(".")[0] for x in ast.walk(tree)
                       if isinstance(x, ast.Import) for y in x.names)
        self.assertFalse(imports & {"requests", "httpx", "socket", "subprocess",
                                    "urllib", "pymysql", "playwright"})
        self.assertFalse((ROOT / ".github/workflows/sonar-watch.yml").exists())
        self.assertEqual(set(FILES), set(sources()))
        self.assertEqual(set(IDS), set(behavior(sources())))

    def test_estados_unknown_explicitos(self):
        data, proof = sources(), behavior(sources())
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual("NO_VERIFICABLE", rows(data[MATRIX])[unit][2])
                self.assertEqual(LOCAL, verdict(unit, data, proof))
                for fake in (None, True, "GREEN", {"ci": "success"},
                             {"sonar_live": "PASS"}, {"issues": "synced"}):
                    self.assertEqual(UNKNOWN, operational(unit, fake))


if __name__ == "__main__":
    unittest.main()
