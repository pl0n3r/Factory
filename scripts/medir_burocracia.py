#!/usr/bin/env python3
"""Medidor offline de tiempos por puerta a partir de issues y PR sintéticos.

No consulta GitHub ni archivos, ni autoriza una transición de estado. Una etapa
incompleta tiene duración UNKNOWN y no se incluye en el ranking de cuellos.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys

MAX_INPUT_BYTES = 256_000
MAX_CASES = 100
MAX_SECONDS_PER_STEP = 366 * 86400
REFERENCE = re.compile(r"fixture:(issue|pr)/[a-z][a-z0-9_-]{0,39}\Z", re.ASCII)
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
STEPS = (
    ("reserva", "created_at", "reserved_at"),
    ("pr", "reserved_at", "opened_at"),
    ("checks", "opened_at", "checks_passed_at"),
    ("politica", "checks_passed_at", "policy_passed_at"),
    ("revision", "policy_passed_at", "reviewed_at"),
    ("merge", "reviewed_at", "merged_at"),
)
PR_TIME_FIELDS = ("opened_at", "checks_passed_at", "policy_passed_at", "reviewed_at", "merged_at")


class BurocracyMeasurementError(ValueError):
    """Entrada inválida sin revelar ningún dato incluido en el fixture."""


def _object(value: object, mandatory: set[str], allowed: set[str], reason: str) -> dict:
    if not isinstance(value, dict) or not mandatory <= set(value) or not set(value) <= allowed:
        raise BurocracyMeasurementError(reason)
    return value


def _reference(value: object, category: str) -> str:
    if not isinstance(value, str) or REFERENCE.fullmatch(value) is None or not value.startswith(f"fixture:{category}/"):
        raise BurocracyMeasurementError("invalid_fixture_reference")
    if re.search(r"\d{7,}", value):
        raise BurocracyMeasurementError("invalid_fixture_reference")
    return value


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or TIMESTAMP.fullmatch(value) is None:
        raise BurocracyMeasurementError("invalid_timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise BurocracyMeasurementError("invalid_timestamp") from exc
    if not 2000 <= parsed.year <= 2100:
        raise BurocracyMeasurementError("invalid_timestamp")
    return parsed


def evaluate(payload: object) -> dict:
    """Retorna mediciones deterministas; sin red, efecto lateral ni datos reales."""
    root = _object(payload, {"version", "issues", "pull_requests"},
                   {"version", "issues", "pull_requests"}, "invalid_root")
    if type(root["version"]) is not int or root["version"] != 1:
        raise BurocracyMeasurementError("invalid_version")
    issues, prs = root["issues"], root["pull_requests"]
    if (not isinstance(issues, list) or not 1 <= len(issues) <= MAX_CASES
            or not isinstance(prs, list) or len(prs) > len(issues)):
        raise BurocracyMeasurementError("invalid_collections")

    timeline: dict[str, dict[str, datetime | None]] = {}
    for item in issues:
        issue = _object(item, {"issue_ref", "created_at"},
                        {"issue_ref", "created_at", "reserved_at"}, "invalid_issue")
        ref = _reference(issue["issue_ref"], "issue")
        if ref in timeline:
            raise BurocracyMeasurementError("duplicate_issue")
        created = _timestamp(issue["created_at"])
        if created is None:
            raise BurocracyMeasurementError("missing_issue_creation")
        timeline[ref] = {"created_at": created, "reserved_at": _timestamp(issue.get("reserved_at"))}

    seen_prs: set[str] = set()
    linked: set[str] = set()
    for item in prs:
        pr = _object(item, {"pr_ref", "issue_ref"},
                     {"pr_ref", "issue_ref", *PR_TIME_FIELDS}, "invalid_pr")
        pr_ref = _reference(pr["pr_ref"], "pr")
        issue_ref = _reference(pr["issue_ref"], "issue")
        if pr_ref in seen_prs or issue_ref in linked:
            raise BurocracyMeasurementError("duplicate_pr")
        if issue_ref not in timeline:
            raise BurocracyMeasurementError("orphan_pr")
        seen_prs.add(pr_ref)
        linked.add(issue_ref)
        for field in PR_TIME_FIELDS:
            timeline[issue_ref][field] = _timestamp(pr.get(field))

    durations: dict[str, list[int]] = {step: [] for step, _, _ in STEPS}
    observations: list[dict] = []
    for issue_ref in sorted(timeline):
        item = timeline[issue_ref]
        # Detect incompatible ordering even when an intermediate milestone is UNKNOWN.
        prior: datetime | None = None
        for field in ("created_at", "reserved_at", *PR_TIME_FIELDS):
            value = item.get(field)
            if value is not None:
                if prior is not None and value < prior:
                    raise BurocracyMeasurementError("out_of_order")
                prior = value
        stages: list[dict] = []
        for name, start, end in STEPS:
            first, last = item.get(start), item.get(end)
            if first is None or last is None:
                stages.append({"step": name, "status": "UNKNOWN", "seconds": None})
                continue
            seconds = int((last - first).total_seconds())
            if seconds > MAX_SECONDS_PER_STEP:
                raise BurocracyMeasurementError("duration_too_large")
            durations[name].append(seconds)
            stages.append({"step": name, "status": "MEASURED", "seconds": seconds})
        observations.append({"issue_ref": issue_ref, "stages": stages})

    ranking: list[dict] = []
    for step, _, _ in STEPS:
        vals = durations[step]
        complete = len(vals) == len(issues)
        ranking.append({
            "step": step, "status": "MEASURED" if complete else "UNKNOWN",
            "samples": len(vals), "unknown": len(issues) - len(vals),
            "total_seconds": sum(vals) if complete else None,
            "mean_seconds": sum(vals) // len(vals) if complete else None,
            "rank": None,
        })
    ranking.sort(key=lambda x: (x["status"] != "MEASURED",
                                -(x["total_seconds"] or 0), x["step"]))
    rank = 1
    for item in ranking:
        if item["status"] == "MEASURED":
            item["rank"] = rank
            rank += 1
    return {
        "version": 1, "mode": "synthetic_offline", "authority": "none",
        "read_only": True, "execute_actions": False,
        "status": "MEASURED" if all(x["status"] == "MEASURED" for x in ranking) else "UNKNOWN",
        "case_count": len(issues), "ranking": ranking, "cases": observations,
    }


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise BurocracyMeasurementError("duplicate_json_key")
        value[key] = item
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tiempos por etapa, solo JSON sintético vía stdin")
    parser.add_argument("--input", required=True, choices=("-",))
    args = parser.parse_args(argv)
    try:
        source = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(source) > MAX_INPUT_BYTES:
            raise BurocracyMeasurementError("input_too_large")
        data = json.loads(source.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              BurocracyMeasurementError("invalid_number")))
        print(json.dumps(evaluate(data), sort_keys=True, ensure_ascii=True, separators=(",", ":")))
        return 0
    except (BurocracyMeasurementError, OSError, UnicodeError, ValueError,
            TypeError, OverflowError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, BurocracyMeasurementError) else "invalid_fixture"
        print(json.dumps({"status": "UNKNOWN", "reason": reason, "execute_actions": False},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
