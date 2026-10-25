"""Diagnóstico puro de la duración unittest en logs CI autenticados por caller.

El resultado NO acredita identidad HTTP, mejora causal, ADOPT ni autoridad de
ejecución. No registra, reproduce ni devuelve el texto arbitrario del log.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

MAX_LOG_BYTES = 256_000
MAX_LOG_LINES = 4_000
_TIMESTAMP = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"
_SUMMARY = re.compile(
    _TIMESTAMP + r"Ran ([1-9][0-9]{0,5}) tests? in ([0-9]{1,5}(?:\.[0-9]{1,3})?)s",
    re.ASCII,
)
_OK = re.compile(_TIMESTAMP + r"OK", re.ASCII)
_FAILED = re.compile(_TIMESTAMP + r"FAILED(?:\s|$).*", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)


class SuiteBenchmarkError(ValueError):
    """Evidencia sintácticamente incompleta o incomprensible: falla cerrada."""


def parse_unittest_summary(log: str) -> dict[str, Any]:
    """Extrae una observación numérica, sin revelar texto ni darle autoridad."""
    if not isinstance(log, str) or "\x00" in log or "\r" in log:
        raise SuiteBenchmarkError("Log ilegible o inválido.")
    try:
        size = len(log.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise SuiteBenchmarkError("Log ilegible o inválido.") from exc
    if not 0 < size <= MAX_LOG_BYTES:
        raise SuiteBenchmarkError("Log ausente o excesivo.")
    lines = log.splitlines()
    if len(lines) > MAX_LOG_LINES:
        raise SuiteBenchmarkError("Demasiadas líneas.")
    found = [(index, match) for index, line in enumerate(lines)
             if (match := _SUMMARY.fullmatch(line)) is not None]
    if len(found) != 1:
        raise SuiteBenchmarkError("Resumen ausente o ambiguo.")
    index, match = found[0]
    outcome = lines[index + 1:index + 6]
    if sum(_OK.fullmatch(line) is not None for line in outcome) != 1:
        raise SuiteBenchmarkError("No hay final OK único.")
    if any(_FAILED.fullmatch(line) for line in outcome):
        raise SuiteBenchmarkError("El runner informó un fallo.")
    tests = int(match.group(1))
    try:
        millis = int(Decimal(match.group(2)) * 1000)
    except (InvalidOperation, ValueError) as exc:
        raise SuiteBenchmarkError("Duración inválida.") from exc
    if not 1 <= millis <= 86_400_000:
        raise SuiteBenchmarkError("Duración fuera de límites.")
    return {
        "suite": "python.unittest", "tests": tests,
        "duration_ms": millis, "status": "DIAGNOSTIC_ONLY",
    }


def _validate_evidence(evidence: Mapping[str, Any]) -> None:
    if not isinstance(evidence, Mapping):
        raise SuiteBenchmarkError("Falta identidad del run.")
    if (evidence.get("repository") != "pl0n3r/FactoryRunner"
            or evidence.get("event") != "push"
            or evidence.get("branch") != "main"
            or evidence.get("suite") != "python.unittest"
            or type(evidence.get("run_id")) is not int
            or evidence["run_id"] <= 0
            or type(evidence.get("job_id")) is not int
            or evidence["job_id"] <= 0
            or not isinstance(evidence.get("head_sha"), str)
            or _SHA.fullmatch(evidence["head_sha"]) is None):
        raise SuiteBenchmarkError("Identidad CI no comparable.")


def compare_unittest_summaries(
    before: Mapping[str, Any], after: Mapping[str, Any],
    before_evidence: Mapping[str, Any], after_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Delta de dos ejecuciones, nunca aprobación o adopción automática."""
    _validate_evidence(before_evidence)
    _validate_evidence(after_evidence)
    if (before_evidence["run_id"] == after_evidence["run_id"]
            or before_evidence["head_sha"] == after_evidence["head_sha"]):
        raise SuiteBenchmarkError("Se requiere un par de runs y SHA distintos.")
    for sample in (before, after):
        if (not isinstance(sample, Mapping)
                or set(sample) != {"suite", "tests", "duration_ms", "status"}
                or sample["suite"] != "python.unittest"
                or sample["status"] != "DIAGNOSTIC_ONLY"
                or type(sample["tests"]) is not int
                or not 1 <= sample["tests"] <= 999_999
                or type(sample["duration_ms"]) is not int
                or not 1 <= sample["duration_ms"] <= 86_400_000):
            raise SuiteBenchmarkError("Resumen numérico no canónico.")
    same_count = before["tests"] == after["tests"]
    return {
        "status": "COMPARABLE_DIAGNOSTIC" if same_count else "NO_COMPARABLE",
        "reason": "descriptive_only" if same_count else "different_test_count",
        "before_tests": before["tests"],
        "after_tests": after["tests"],
        "duration_delta_ms": after["duration_ms"] - before["duration_ms"]
        if same_count else None,
        "sample_pairs": 1, "causality": "unproven",
        "adopt": False, "create_work_item": False,
        "execute_actions": False, "authority": "unchanged",
    }
