#!/usr/bin/env python3
"""Summarize local CodeQL SARIF and fail closed on blocking security findings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SARIF_DIR = Path("codeql-results")
SUMMARY_PATH = SARIF_DIR / "summary.json"


def _rules(run: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    driver = run.get("tool", {}).get("driver", {})
    driver_rules = driver.get("rules", []) or []
    by_id: dict[str, dict[str, Any]] = {}

    for descriptor in driver_rules:
        rule_id = descriptor.get("id")
        if rule_id:
            by_id[str(rule_id)] = descriptor

    for extension in run.get("tool", {}).get("extensions", []) or []:
        for descriptor in extension.get("rules", []) or []:
            rule_id = descriptor.get("id")
            if rule_id:
                by_id[str(rule_id)] = descriptor

    return by_id, driver_rules


def _security_severity(descriptor: dict[str, Any] | None) -> float:
    if not descriptor:
        return 0.0
    raw = descriptor.get("properties", {}).get("security-severity", 0)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if 0.0 < value <= 10.0 else 0.0


def _location(result: dict[str, Any]) -> str:
    locations = result.get("locations") or []
    if not locations:
        return ""
    physical = locations[0].get("physicalLocation", {})
    uri = physical.get("artifactLocation", {}).get("uri", "")
    region = physical.get("region", {})
    line = region.get("startLine")
    return f"{uri}:{line}" if uri and line else str(uri)


def _validated_runs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError(f"{path}: SARIF has no analysis runs")

    validated: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError(f"{path}: SARIF run must be an object")
        tool = run.get("tool")
        driver = tool.get("driver") if isinstance(tool, dict) else None
        driver_name = driver.get("name") if isinstance(driver, dict) else None
        if not isinstance(driver_name, str) or not driver_name.strip():
            raise ValueError(f"{path}: SARIF run has no tool driver name")
        results = run.get("results")
        if not isinstance(results, list):
            raise ValueError(f"{path}: SARIF run has no results array")
        validated.append(run)
    return validated


def _descriptor(
    run: dict[str, Any],
    result: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    by_id, driver_rules = _rules(run)
    nested_rule = result.get("rule")
    nested_rule_id = nested_rule.get("id") if isinstance(nested_rule, dict) else ""
    rule_id = str(result.get("ruleId") or nested_rule_id or "")
    if not rule_id:
        raise ValueError("SARIF result has no rule identifier")

    descriptor = by_id.get(rule_id)
    index = result.get("ruleIndex")
    if descriptor is None and isinstance(index, int) and 0 <= index < len(driver_rules):
        descriptor = driver_rules[index]

    descriptor_rule_id = (
        str(descriptor.get("id") or rule_id)
        if isinstance(descriptor, dict)
        else rule_id
    )
    return rule_id, descriptor_rule_id, descriptor


def _record_result(
    summary: dict[str, Any],
    result: dict[str, Any],
    run: dict[str, Any],
    source: str,
    threshold: float,
    zero_rules: set[str],
) -> None:
    summary["result_count"] += 1
    rule_id, descriptor_rule_id, descriptor = _descriptor(run, result)
    severity = _security_severity(descriptor)
    if severity > 0:
        summary["security_result_count"] += 1

    blocks_by_severity = severity >= threshold
    blocks_by_rule = descriptor_rule_id in zero_rules
    summary["high_or_critical_count"] += int(blocks_by_severity)
    summary["required_zero_rule_count"] += int(blocks_by_rule)

    if not (blocks_by_severity or blocks_by_rule):
        return

    summary["findings"].append(
        {
            "rule_id": rule_id,
            "security_severity": severity,
            "level": result.get("level", ""),
            "location": _location(result),
            "source": source,
        }
    )


def summarize(paths: list[Path], threshold: float, zero_rules: set[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "sarif_files": len(paths),
        "analysis_run_count": 0,
        "result_count": 0,
        "security_result_count": 0,
        "high_or_critical_count": 0,
        "required_zero_rule_count": 0,
        "findings": [],
    }

    for path in paths:
        for run in _validated_runs(path):
            summary["analysis_run_count"] += 1
            for result in run["results"]:
                if not isinstance(result, dict):
                    raise ValueError(f"{path}: SARIF result must be an object")
                _record_result(summary, result, run, path.name, threshold, zero_rules)

    return summary


def _sarif_paths() -> list[Path]:
    paths = sorted(SARIF_DIR.rglob("*.sarif"))
    paths += sorted(SARIF_DIR.rglob("*.sarif.json"))
    return list(dict.fromkeys(paths))


def _write_summary(summary: dict[str, Any]) -> None:
    SARIF_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_summary(summary: dict[str, Any]) -> None:
    print(
        "CodeQL evidence: "
        f"files={summary['sarif_files']} "
        f"runs={summary['analysis_run_count']} "
        f"results={summary['result_count']} "
        f"high_or_critical={summary['high_or_critical_count']} "
        f"required_zero={summary['required_zero_rule_count']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-severity", type=float, default=7.0)
    parser.add_argument("--require-zero-rule", action="append", default=[])
    args = parser.parse_args()

    paths = _sarif_paths()
    if not paths:
        print("::error::No SARIF files found; evidence is incomplete")
        return 2

    zero_rules = set(args.require_zero_rule)
    try:
        summary = summarize(paths, args.fail_severity, zero_rules)
        _write_summary(summary)
    except (OSError, ValueError) as error:
        print(f"::error::Invalid SARIF evidence: {error}")
        return 2

    _print_summary(summary)
    if summary["high_or_critical_count"] or summary["required_zero_rule_count"]:
        print("::error::Blocking CodeQL findings remain in local SARIF evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
