#!/usr/bin/env python3
"""Medición determinista offline de latencias de CI con entrada sintética.

No consulta GitHub, no infiere causalidad, no cambia baselines ni ejecuta acciones.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

MAX_FILE_BYTES = 256_000
MAX_WORKFLOWS = 100
MAX_SAMPLES = 1000
MAX_DURATION_MS = 86_400_000
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_. -]{0,63}\Z", re.ASCII)


class CiMeasurementError(ValueError):
    """La entrada es ambigua o excede los límites del contrato."""


def _keys(obj: object, expected: set[str], where: str) -> dict:
    if not isinstance(obj, dict) or set(obj) != expected:
        raise CiMeasurementError(f"invalid_{where}")
    return obj


def _positive_int(value: object, where: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_DURATION_MS:
        raise CiMeasurementError(f"invalid_{where}")
    return value


def _percentile_nearest_rank(values: list[int], percentile: int) -> int:
    """pXX con nearest-rank, explícito y reproducible incluso con n pequeño."""
    ordered = sorted(values)
    index = (percentile * len(ordered) + 99) // 100 - 1
    return ordered[index]


def evaluate(data: object) -> dict:
    """Salida sin efectos secundarios; entradas adicionales se rechazan."""
    payload = _keys(data, {"version", "workflows"}, "root")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise CiMeasurementError("invalid_version")
    workflows = payload["workflows"]
    if not isinstance(workflows, list) or not 1 <= len(workflows) <= MAX_WORKFLOWS:
        raise CiMeasurementError("invalid_workflows")
    results: list[dict] = []
    seen: set[str] = set()
    for item in workflows:
        if not isinstance(item, dict) or set(item) not in (
            {"workflow", "durations_ms"},
            {"workflow", "durations_ms", "baseline"},
        ):
            raise CiMeasurementError("invalid_workflow_entry")
        name = item["workflow"]
        if not isinstance(name, str) or NAME.fullmatch(name) is None or name in seen:
            raise CiMeasurementError("invalid_workflow_name")
        seen.add(name)
        samples = item["durations_ms"]
        if not isinstance(samples, list) or len(samples) > MAX_SAMPLES:
            raise CiMeasurementError("invalid_samples")
        durations = [_positive_int(v, "duration_ms") for v in samples]
        if not durations:
            results.append({"workflow": name, "samples": 0, "p50_ms": None,
                            "p95_ms": None, "status": "UNKNOWN", "reason": "no_samples",
                            "regression_p50": None, "regression_p95": None})
            continue
        p50 = _percentile_nearest_rank(durations, 50)
        p95 = _percentile_nearest_rank(durations, 95)
        base = item.get("baseline")
        row = {"workflow": name, "samples": len(durations), "p50_ms": p50,
               "p95_ms": p95, "status": "UNKNOWN", "reason": "no_baseline",
               "regression_p50": None, "regression_p95": None}
        if base is not None:
            _keys(base, {"p50_ms", "p95_ms", "threshold_pct"}, "baseline")
            old50 = _positive_int(base["p50_ms"], "baseline_p50")
            old95 = _positive_int(base["p95_ms"], "baseline_p95")
            threshold = base["threshold_pct"]
            if old50 > old95 or type(threshold) is not int or not 0 <= threshold <= 100:
                raise CiMeasurementError("invalid_baseline")
            row["regression_p50"] = p50 * 100 > old50 * (100 + threshold)
            row["regression_p95"] = p95 * 100 > old95 * (100 + threshold)
            row["status"] = ("REGRESSION" if row["regression_p50"] or
                             row["regression_p95"] else "WITHIN_BASELINE")
            row["reason"] = None
        results.append(row)
    results.sort(key=lambda r: r["workflow"])
    return {"version": 1, "mode": "synthetic_offline", "authority": "none",
            "execute_actions": False, "baseline_mutated": False, "workflows": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Medidor offline de CI (JSON sintético)")
    parser.add_argument("--input", required=True, choices=("-",),
                        help="Fixture JSON sintético por stdin; no leer rutas externas")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read(MAX_FILE_BYTES + 1)
        if len(text.encode("utf-8")) > MAX_FILE_BYTES:
            raise CiMeasurementError("input_too_large")
        def reject_duplicates(pairs):
            result = {}
            for key, val in pairs:
                if key in result:
                    raise CiMeasurementError("duplicate_json_key")
                result[key] = val
            return result
        data = json.loads(text, object_pairs_hook=reject_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(CiMeasurementError("invalid_number")))
        print(json.dumps(evaluate(data), ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        return 0
    except (CiMeasurementError, OSError, UnicodeError, ValueError, RecursionError) as err:
        # No se imprime el payload, ni rutas/valores potencialmente sensibles.
        reason = str(err) if isinstance(err, CiMeasurementError) else "invalid_fixture"
        print(json.dumps({"status": "UNKNOWN", "reason": reason,
                          "execute_actions": False}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
