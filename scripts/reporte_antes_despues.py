#!/usr/bin/env python3
"""Compara snapshots existentes del orquestador, sin red ni estimaciones.

Entrada JSON: version=1, periods={antes,despues} con start/end UTC y
complete booleano; issues (number, created_at, closed_at) y pull_requests
(number, created_at, merged_at). Timestamps UTC ISO 8601 terminados en Z.
Las columnas adicionales de exportaciones existentes se ignoran, no se publican.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import stat
import re
import sys
from zoneinfo import ZoneInfo

MAX_INPUT_BYTES = 256_000
MAX_RECORDS = 5000
UNKNOWN = "UNKNOWN"
UTC_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
BOGOTA = ZoneInfo("America/Bogota")
INPUT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.json\Z", re.ASCII)


class ReportError(ValueError):
    """Contrato de datos no acreditado (no divulga contenido de entrada)."""


def _timestamp(value: object, required: bool = False) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not UTC_PATTERN.fullmatch(value):
        raise ReportError("invalid_timestamp")
    try:
        stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReportError("invalid_timestamp") from exc
    if not 2000 <= stamp.year <= 2100:
        raise ReportError("invalid_timestamp")
    return stamp


def _period(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"start", "end", "complete"}:
        raise ReportError("invalid_period")
    start, end = _timestamp(value["start"], True), _timestamp(value["end"], True)
    if start >= end or type(value["complete"]) is not bool:
        raise ReportError("invalid_period")
    return {"start": start, "end": end, "complete": value["complete"]}


def _records(values: object, category: str) -> list[dict]:
    if not isinstance(values, list) or len(values) > MAX_RECORDS:
        raise ReportError("invalid_records")
    completed_key = "closed_at" if category == "issue" else "merged_at"
    seen = set()
    result = []
    for item in values:
        if not isinstance(item, dict):
            raise ReportError("invalid_record")
        number = item.get("number")
        if type(number) is not int or number <= 0 or number in seen or completed_key not in item:
            raise ReportError("invalid_record")
        seen.add(number)
        created = _timestamp(item.get("created_at"))
        completed = _timestamp(item[completed_key])
        if created and completed and completed < created:
            raise ReportError("invalid_chronology")
        if completed is None and (item.get("state") == "closed" if category == "issue" else item.get("merged") is True):
            raise ReportError("incomplete_completion_record")
        result.append({"created": created, "completed": completed})
    return result


def _local(stamp: datetime) -> str:
    return stamp.astimezone(BOGOTA).strftime("%Y-%m-%d %I:%M %p")


def _measure(period: dict, issues: list[dict], prs: list[dict]) -> dict:
    start, end = period["start"], period["end"]
    closed = [r for r in issues if r["completed"] is not None and start <= r["completed"] < end]
    merged = [r for r in prs if r["completed"] is not None and start <= r["completed"] < end]
    durations = [(r["completed"] - r["created"]).total_seconds() for r in closed if r["created"]]
    complete = period["complete"]
    return {
        "inicio_bogota_12h": _local(start),
        "fin_bogota_12h": _local(end),
        "estado": "COMPLETO" if complete else UNKNOWN,
        "issues_cerrados": len(closed) if complete else UNKNOWN,
        "prs_fusionados": len(merged) if complete else UNKNOWN,
        "horas_promedio_por_issue": (
            round(sum(durations) / len(durations) / 3600, 2)
            if complete and closed and len(durations) == len(closed) else UNKNOWN
        ),
    }


def _delta(a: object, b: object) -> int | float | str:
    if type(a) not in (int, float) or type(b) not in (int, float):
        return UNKNOWN
    return round(b - a, 2)


def evaluate(payload: object) -> dict:
    """Mide eventos observables; UNKNOWN conserva la falta de evidencia."""
    if not isinstance(payload, dict) or payload.get("version") != 1 or type(payload.get("version")) is not int:
        raise ReportError("invalid_version")
    periods = payload.get("periods")
    if not isinstance(periods, dict) or set(periods) != {"antes", "despues"}:
        raise ReportError("invalid_periods")
    before, after = _period(periods["antes"]), _period(periods["despues"])
    if before["end"] > after["start"]:
        raise ReportError("overlapping_periods")
    issues = _records(payload.get("issues"), "issue")
    prs = _records(payload.get("pull_requests"), "pr")
    a = _measure(before, issues, prs)
    b = _measure(after, issues, prs)
    keys = ("issues_cerrados", "prs_fusionados", "horas_promedio_por_issue")
    return {
        "version": 1, "fuente": "snapshot_orquestador", "modo": "offline_solo_lectura",
        "zona_horaria": "America/Bogota", "formato_hora": "12h",
        "antes": a, "despues": b,
        "diferencia_despues_menos_antes": {key: _delta(a[key], b[key]) for key in keys},
        "costo": {"gasto_nuevo_cop": 0, "costo_operativo_total_cop": UNKNOWN},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reporte antes/después, solo lectura y sin gasto")
    parser.add_argument("--input", required=True, help="JSON exportado del orquestador, o '-' para stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            if not INPUT_NAME.fullmatch(args.input):
                raise ReportError("invalid_input_name")
            directory_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
            try:
                fd = os.open(args.input, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory_fd)
            finally:
                os.close(directory_fd)
            with os.fdopen(fd, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise ReportError("invalid_input_type")
                raw = file.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ReportError("input_too_large")
        output = evaluate(json.loads(raw))
    except (OSError, UnicodeError, ValueError, RecursionError):
        print("ERROR: datos inválidos o incompletos", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
