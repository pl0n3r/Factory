#!/usr/bin/env python3
"""Summarize local CodeQL SARIF and fail closed on blocking security findings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
        payload = json.loads(path.read_text(encoding="utf-8"))
        runs = payload.get("runs")
        if not isinstance(runs, list) or not runs:
            raise ValueError(f"{path}: SARIF has no analysis runs")
        for run in runs:
            if not isinstance(run, dict):
                raise ValueError(f"{path}: SARIF run must be an object")
            tool = run.get("tool")
            driver = tool.get("driver") if isinstance(tool, dict) else None
            driver_name = driver.get("name") if isinstance(driver, dict) else None
            if not isinstance(driver_name, str) or not driver_name.strip():
                raise ValueError(f"{path}: SARIF run has no tool driver name")
            summary["analysis_run_count"] += 1
            by_id, driver_rules = _rules(run)
            for result in run.get("results", []) or []:
                summary["result_count"] += 1
                rule_id = str(result.get("ruleId") or "")
                descriptor = by_id.get(rule_id)
                if descriptor is None and isinstance(result.get("ruleIndex"), int):
                    index = result["ruleIndex"]
                    if 0 <= index < len(driver_rules):
                        descriptor = driver_rules[index]
                        rule_id = rule_id or str(descriptor.get("id") or "")

                severity = _security_severity(descriptor)
                if severity > 0:
                    summary["security_result_count"] += 1

                blocks_by_severity = severity >= threshold
                blocks_by_rule = rule_id in zero_rules
                if blocks_by_severity:
                    summary["high_or_critical_count"] += 1
                if blocks_by_rule:
                    summary["required_zero_rule_count"] += 1

                if blocks_by_severity or blocks_by_rule:
                    summary["findings"].append(
                        {
                            "rule_id": rule_id,
                            "security_severity": severity,
                            "level": result.get("level", ""),
                            "location": _location(result),
                            "source": path.name,
                        }
                    )

    return summary


def _write_markdown(path: Path, summary: dict[str, Any], zero_rules: set[str], threshold: float) -> None:
    lines = [
        "## CodeQL Actions evidence",
        "",
        "| Señal | Valor |",
        "| --- | ---: |",
        f"| SARIF files | {summary['sarif_files']} |",
        f"| Analysis runs | {summary['analysis_run_count']} |",
        f"| Results | {summary['result_count']} |",
        f"| Security results | {summary['security_result_count']} |",
        f"| Severity >= {threshold:g} | {summary['high_or_critical_count']} |",
        f"| Required-zero rules | {summary['required_zero_rule_count']} |",
        "",
        "Required-zero rule IDs: " + (", ".join(sorted(zero_rules)) or "(none)"),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sarif_dir", type=Path)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--github-summary", type=Path)
    parser.add_argument("--fail-severity", type=float, default=7.0)
    parser.add_argument("--require-zero-rule", action="append", default=[])
    args = parser.parse_args()

    paths = sorted(args.sarif_dir.rglob("*.sarif"))
    paths += sorted(args.sarif_dir.rglob("*.sarif.json"))
    paths = list(dict.fromkeys(paths))
    if not paths:
        print("::error::No SARIF files found; evidence is incomplete")
        return 2

    zero_rules = set(args.require_zero_rule)
    try:
        summary = summarize(paths, args.fail_severity, zero_rules)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"::error::Invalid SARIF evidence: {error}")
        return 2
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.github_summary:
        _write_markdown(args.github_summary, summary, zero_rules, args.fail_severity)

    print(
        "CodeQL evidence: "
        f"files={summary['sarif_files']} "
        f"runs={summary['analysis_run_count']} "
        f"results={summary['result_count']} "
        f"high_or_critical={summary['high_or_critical_count']} "
        f"required_zero={summary['required_zero_rule_count']}"
    )

    if summary["high_or_critical_count"] or summary["required_zero_rule_count"]:
        print("::error::Blocking CodeQL findings remain in local SARIF evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
