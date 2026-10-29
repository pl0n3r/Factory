"""Factory #1675: 16 Sonar Watch / Sonar contracts with synthetic evidence.

A local contract is not evidence of live Sonar, CI, approval or production.
Unobservable synchronization remains UNKNOWN; no network or credentials.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from quality.sonar import SonarEvidenceError, normalize_sonar_snapshot

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
WATCH = "docs/quality-sonar-watch.md"
DOC = "docs/quality-sonar.md"
CONFIG = "quality/sonar-watch-config.json"
FILES = (MATRIX, WATCH, DOC, CONFIG)
NOW = "2026-09-30T12:00:00Z"
UNKNOWN, LOCAL = "UNKNOWN", "CONTRATO_LOCAL"
BT = chr(96)
UNITS = (
    "docs/quality-sonar-watch.md:L60-U2",
    "docs/quality-sonar-watch.md:L64-U1",
    "docs/quality-sonar.md:L10-U1",
    "docs/quality-sonar.md:L11-U1",
    "docs/quality-sonar.md:L12-U1",
    "docs/quality-sonar.md:L13-U1",
    "docs/quality-sonar.md:L15-U1",
    "docs/quality-sonar.md:L21-U1",
    "docs/quality-sonar.md:L22-U1",
    "docs/quality-sonar.md:L24-U1",
    "docs/quality-sonar.md:L25-U1",
    "docs/quality-sonar.md:L26-U1",
    "docs/quality-sonar.md:L28-U1",
    "docs/quality-sonar.md:L32-U1",
    "docs/quality-sonar.md:L32-U2",
    "docs/quality-sonar.md:L32-U3",
)


def sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in FILES}


def rows(data: object) -> dict[str, tuple[str, ...]]:
    if type(data) is not dict or set(data) != set(FILES) or any(
        type(data[p]) is not str or not data[p] for p in FILES
    ):
        raise ValueError("UNKNOWN: incomplete sources")
    found = {}
    for line in data[MATRIX].splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in re.split(r"(?<!\\)\|", line)[1:-1])
        if not cells or not cells[0].startswith(BT):
            continue
        key = cells[0].strip(BT)
        if key not in UNITS:
            continue
        if (key in found or len(cells) != 5 or cells[0] != BT + key + BT
                or not cells[1] or cells[2] != "NO_VERIFICABLE"
                or "[Contraste #1573](contraste-factory_resto_5.md)" not in cells[3]
                or "faltan aserción exacta y PR MERGED" not in cells[3]
                or cells[4] != "—"):
            raise ValueError("UNKNOWN: invalid or duplicated " + key)
        found[key] = cells
    if set(found) != set(UNITS):
        raise ValueError("UNKNOWN: missing Sonar row")
    return found


def doc_matches(key: object, data: object) -> bool:
    if type(key) is not str or key not in UNITS or type(data) is not dict:
        return False
    match = re.fullmatch(r"(docs/quality-sonar(?:-watch)?\.md):L([1-9]\d*)-U[1-9]\d*", key)
    if match is None or type(data.get(match[1])) is not str:
        return False
    lines = data[match[1]].splitlines()
    number = int(match[2])
    if number > len(lines):
        return False
    try:
        phrase = rows(data)[key][1].replace(r"\|", "|")
    except (ValueError, KeyError):
        return False
    return phrase.casefold() in lines[number - 1].casefold()


def policy(data: dict[str, str], project: str = "factory") -> dict:
    contents = json.loads(data[CONFIG])
    if type(contents) is not dict or contents.get("version") != 1:
        raise ValueError("UNKNOWN: invalid versioned policy")
    entries = [x for x in contents["projects"] if x["project"] == project]
    if len(entries) != 1:
        raise ValueError("UNKNOWN: absent or ambiguous policy")
    return deepcopy(entries[0]["contract"])


def snapshot(project: str = "factory") -> dict:
    return {
        "project": project, "snapshot_at": "2026-09-30T11:55:00Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {"analyzed_at": "2026-09-30T11:50:00Z",
                     "method": "ci" if project == "factory" else "automatic",
                     "coverage_available": True},
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50},
        "visibility": "public", "debt": [],
        "evidence_refs": ["sonar:" + project + ":synthetic:001"],
    }


def normal(data, raw=None, project="factory", custom=None):
    return normalize_sonar_snapshot(
        policy(data, project) if custom is None else custom,
        snapshot(project) if raw is None else raw, observed_at=NOW)


def sig(result, name):
    return next(x for x in result["signals"] if x["signal"] == name)


def watch_module():
    spec = importlib.util.spec_from_file_location(
        "sonar_watch_factory_57", ROOT / "scripts/sonar-watch.py")
    if spec is None or spec.loader is None:
        raise ValueError("UNKNOWN: no watch source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rejects(func, error):
    try:
        func()
    except error:
        return True
    return False


def proof(data):
    """Executable, independent source and contract checks for each row."""
    base = normal(data)
    altered = snapshot()
    altered["analysis"]["method"] = "automatic"
    altered["visibility"] = "private"
    drift = normal(data, altered)

    null = snapshot()
    null["ce_task"] = None
    null_task = normal(data, null)
    null = snapshot()
    null["quality_gate"] = None
    null_gate = normal(data, null)
    null = snapshot()
    null["analysis"] = None
    null_analysis = normal(data, null)

    failure = snapshot()
    failure["quality_gate"] = {"status": "ERROR", "conditions": [
        {"metric": "new_bugs", "status": "ERROR", "actual": "2", "threshold": "0"}]}
    failed_gate = normal(data, failure)

    ce = snapshot()
    ce["ce_task"] = {
        "status": "FAILED",
        "error_message": "failed; https://invalid.example/path token=supersecret123",
    }
    failed_ce = normal(data, ce)

    aged = snapshot()
    aged["analysis"]["analyzed_at"] = "2026-09-27T11:00:00Z"
    stale = normal(data, aged)

    historical = snapshot()
    historical["debt"] = [{
        "type": "vulnerability", "severity": "CRITICAL",
        "opened_at": "2026-08-01T12:00:00Z",
        "evidence_ref": "sonar:factory:synthetic:vulnerability:1"}]
    with_debt = normal(data, historical)

    uncovered = snapshot()
    uncovered["analysis"]["coverage_available"] = False
    no_coverage = normal(data, uncovered)

    auto = snapshot("brvtal")
    auto["analysis"]["coverage_available"] = False
    automatic = normal(data, auto, "brvtal")

    private_contract = policy(data)
    private_contract["sonar"]["expected_visibility"] = "private"
    del private_contract["sonar"]["applicability"]
    private_raw = snapshot()
    private_raw["visibility"] = "private"
    private_raw["organization"] = None
    private_result = normal(data, private_raw, custom=private_contract)

    watch = watch_module()
    bad_settings = ({}, {"settings": []},
                    {"settings": [{"key": "unexpected", "value": "true"}]},
                    {"settings": [{"key": "sonar.autoscan.enabled", "value": "maybe"}]},
                    {"settings": [
                        {"key": "sonar.autoscan.enabled", "value": "false"},
                        {"key": "sonar.autoscan.enabled", "value": "false"}]})
    parser_closed = all(rejects(
        lambda item=item: watch.SonarApi.analysis_method_from_settings(item),
        watch.SonarWatchError) for item in bad_settings)
    malformed = snapshot()
    malformed["surprise"] = True
    malformed_closed = rejects(lambda: normal(data, malformed), SonarEvidenceError)
    missing = snapshot()
    del missing["ce_task"]
    missing_closed = rejects(lambda: normal(data, missing), SonarEvidenceError)
    malformed_analysis = snapshot()
    del malformed_analysis["analysis"]["analyzed_at"]
    analysis_closed = rejects(
        lambda: normal(data, malformed_analysis), SonarEvidenceError)

    return {
        UNITS[0]: (sig(drift, "analysis_method")["status"] == "FAIL"
                   and sig(drift, "visibility")["status"] == "FAIL"),
        # The remote watcher projection is not executed; document it explicitly.
        UNITS[1]: False if parser_closed and malformed_closed else False,
        UNITS[2]: (sig(base, "analysis_freshness")["status"] == "PASS"
                   and sig(base, "analysis_method")["status"] == "PASS"
                   and sig(base, "coverage")["status"] == "PASS"
                   and analysis_closed),
        UNITS[3]: (sig(failed_ce, "ce_task")["status"] == "FAIL"
                   and "[sensitive removed]" in
                   sig(failed_ce, "ce_task")["details"]["error_message"]
                   and "supersecret123" not in
                   sig(failed_ce, "ce_task")["details"]["error_message"]),
        UNITS[4]: (sig(base, "organization_line_usage")["status"] == "NOT_APPLICABLE"
                   and sig(base, "visibility")["status"] == "PASS"
                   and sig(base, "historical_debt")["status"] == "PASS"),
        UNITS[5]: (missing_closed and len(null_task["signals"]) == 8
                   and sig(null_task, "ce_task")["status"] == UNKNOWN),
        UNITS[6]: (sig(null_gate, "quality_gate")["status"] == UNKNOWN
                   and sig(null_analysis, "analysis_freshness")["status"] == UNKNOWN
                   and sig(null_task, "ce_task")["status"] == UNKNOWN),
        UNITS[7]: (sig(failed_gate, "quality_gate")["status"] == "FAIL"
                   and len(sig(failed_gate, "quality_gate")
                           ["details"]["failed_conditions"]) == 1),
        UNITS[8]: sig(stale, "analysis_freshness")["status"] == "STALE",
        UNITS[9]: (sig(base, "organization_line_usage")["status"] == "NOT_APPLICABLE"
                   and sig(private_result, "organization_line_usage")["status"] == UNKNOWN),
        UNITS[10]: sig(drift, "visibility")["status"] == "FAIL",
        UNITS[11]: sig(drift, "analysis_method")["status"] == "FAIL",
        UNITS[12]: (sig(with_debt, "historical_debt")["status"] == "FAIL"
                    and sig(with_debt, "historical_debt")["details"]["counts"][0]["count"] == 1),
        UNITS[13]: (sig(no_coverage, "coverage")["status"] == "FAIL"
                    and sig(no_coverage, "coverage")["reason"]
                    == "coverage_missing_for_ci"),
        UNITS[14]: (sig(automatic, "coverage")["status"] == "NOT_APPLICABLE"
                    and sig(automatic, "coverage")["details"]["source_ref"]
                    == "pl0n3r/Factory#516"),
        UNITS[15]: (sig(base, "organization_line_usage")["status"] == "NOT_APPLICABLE"
                    and sig(private_result, "organization_line_usage")["status"] == UNKNOWN),
    }


def local_verdict(unit, data, results):
    if type(unit) is not str or unit not in UNITS or type(results) is not dict:
        return UNKNOWN
    try:
        rows(data)
        if not doc_matches(unit, data):
            return UNKNOWN
        return LOCAL if results.get(unit) is True else UNKNOWN
    except (ValueError, KeyError, TypeError, IndexError):
        return UNKNOWN


def operational_verdict(_unit, _evidence=None):
    return UNKNOWN


class BrechasFactory57Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = sources()

    def test_contrato_principal(self):
        """AC-01: 16 independent evidence rows or explicit UNKNOWN."""
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(len(set(UNITS)), 16)
        self.assertEqual(set(rows(self.data)), set(UNITS))
        results = proof(self.data)
        self.assertEqual(set(results), set(UNITS))
        for unit in UNITS:
            with self.subTest(unit=unit):
                self.assertTrue(doc_matches(unit, self.data))
                expected = UNKNOWN if unit == UNITS[1] else LOCAL
                self.assertEqual(local_verdict(unit, self.data, results), expected)

    def test_falla_cerrado(self):
        """AC-02: duplicate/missing/promoted rows and spoofed proof fail."""
        good = {unit: True for unit in UNITS}
        for unit in UNITS:
            with self.subTest(unit=unit):
                line = next(x for x in self.data[MATRIX].splitlines()
                            if x.startswith("| " + BT + unit + BT + " |"))
                variants = (
                    self.data[MATRIX].replace(line, "", 1),
                    self.data[MATRIX] + "\n" + line,
                    self.data[MATRIX].replace(
                        line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1),
                )
                for variant in variants:
                    self.assertEqual(local_verdict(
                        unit, {**self.data, MATRIX: variant}, good), UNKNOWN)
                self.assertEqual(local_verdict(unit, self.data, {}), UNKNOWN)
                doc = unit.partition(":")[0]
                number = int(unit.split(":L")[1].split("-")[0])
                lines = self.data[doc].splitlines()
                lines[number - 1] = "unknown source"
                self.assertEqual(local_verdict(unit, {
                    **self.data, doc: "\n".join(lines) + "\n"}, good), UNKNOWN)
        for invalid in (None, "", "unknown", {"approved": True}):
            self.assertEqual(local_verdict(invalid, self.data, good), UNKNOWN)
        self.assertEqual(local_verdict(UNITS[0], None, good), UNKNOWN)
        self.assertTrue(rejects(
            lambda: normal(self.data, {**snapshot(), "extra": "invalid"}),
            SonarEvidenceError))

    def test_sin_datos_reales(self):
        """AC-03: offline versioned fixtures, no provider or credentials."""
        self.assertEqual(set(self.data), set(FILES))
        for name in FILES:
            file = Path(name)
            self.assertFalse(file.is_absolute())
            self.assertNotIn("..", file.parts)
            self.assertTrue((ROOT / file).is_file())
        watch = watch_module()
        with patch.object(watch, "urlopen", side_effect=AssertionError("network")) as net:
            method = watch.SonarApi.analysis_method_from_settings({
                "settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]})
            self.assertEqual(method, "ci")
            self.assertFalse(normal(self.data)["execute_actions"])
            net.assert_not_called()
        data = json.dumps(snapshot(), sort_keys=True)
        for secret in ("@gmail", "@outlook", "Bearer ", "password=", "api_key="):
            self.assertNotIn(secret, data)

    def test_estados_unknown_explicitos(self):
        """AC-04: synthetic evidence never promotes CI or live status."""
        index = rows(self.data)
        for unit in UNITS:
            with self.subTest(unit=unit):
                self.assertEqual(index[unit][2], "NO_VERIFICABLE")
                for spoof in (None, {}, {"ci": "success", "sha": "a" * 40},
                              {"owner": True}, {"live": "GREEN"},
                              {"production": "VALIDATED_IN_PRODUCTION"}):
                    self.assertEqual(operational_verdict(unit, spoof), UNKNOWN)
        self.assertEqual(local_verdict(UNITS[1], self.data, {UNITS[1]: False}),
                         UNKNOWN)


if __name__ == "__main__":
    unittest.main()
