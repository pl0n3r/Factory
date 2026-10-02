#!/usr/bin/env python3
"""Preflight offline del contrato completo de un Issue antes de /tomar."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

if __package__:
    from scripts.aceptacion_kit import AcceptanceError, contract_fingerprint, parse_contract
    from scripts.orquestador_kit import (
        PlanError,
        parse_task_marker,
        task_marker_fingerprint,
    )
else:
    from aceptacion_kit import AcceptanceError, contract_fingerprint, parse_contract
    from orquestador_kit import PlanError, parse_task_marker, task_marker_fingerprint


MAX_INPUT_CHARS = 200_000


class IssueContractPreflightError(ValueError):
    """Contrato de Issue inválido antes de coordinación."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code


def evaluate_issue_body(body: object) -> dict[str, Any]:
    """Valida acceptance primero y luego factory-plan-task, sin I/O remoto."""
    if not isinstance(body, str) or not 1 <= len(body) <= MAX_INPUT_CHARS:
        raise IssueContractPreflightError(
            "acceptance_invalid",
            "Body del Issue inválido o demasiado grande.",
        )

    try:
        criteria = parse_contract(body)
        acceptance_sha256 = contract_fingerprint(body)
    except AcceptanceError as exc:
        raise IssueContractPreflightError(
            "acceptance_invalid",
            str(exc),
        ) from exc

    try:
        task = parse_task_marker(body)
    except PlanError as exc:
        raise IssueContractPreflightError(
            "task_invalid",
            str(exc),
        ) from exc

    if task is None:
        raise IssueContractPreflightError(
            "task_missing",
            "Falta factory-plan-task.",
        )

    task_sha256 = task_marker_fingerprint(task)
    if task_sha256 is None:
        raise IssueContractPreflightError(
            "task_invalid",
            "No fue posible fijar factory-plan-task.",
        )

    return {
        "version": 1,
        "valid": True,
        "acceptance_sha256": acceptance_sha256,
        "task_marker_sha256": task_sha256,
        "task_key": task["task_key"],
        "paths": list(task["paths"]),
        "depends_on": list(task["depends_on"]),
        "criteria": [
            {"id": criterion.id, "kind": criterion.kind, "target": criterion.target}
            for criterion in sorted(criteria, key=lambda item: item.id)
        ],
    }


def _emit(stdout: TextIO, payload: dict[str, Any]) -> None:
    stdout.write(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    if argv:
        raise IssueContractPreflightError(
            "usage_error",
            "El body se recibe únicamente por stdin.",
        )

    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    body = input_stream.read(MAX_INPUT_CHARS + 1)

    try:
        result = evaluate_issue_body(body)
    except IssueContractPreflightError as exc:
        _emit(
            output_stream,
            {
                "version": 1,
                "valid": False,
                "code": exc.code,
                "reason": str(exc),
            },
        )
        return 2

    _emit(output_stream, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
