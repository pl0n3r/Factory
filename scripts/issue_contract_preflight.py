#!/usr/bin/env python3
"""Preflight offline del contrato completo de un Issue antes de /tomar."""

from __future__ import annotations

import json
import re
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


# Clasificador conservador: .js/.ts solo cuando su ruta identifica una pantalla
# o un frontend; scripts internos de automatización no son UI.
_UI_SUFFIXES = (".css", ".scss", ".sass", ".less", ".html", ".htm", ".twig", ".blade.php", ".tsx", ".jsx", ".vue", ".svelte")
_UI_SCRIPT_SUFFIXES = (".js", ".mjs", ".cjs", ".ts")
_UI_PATH_PARTS = frozenset({
    "frontend", "ui", "components", "pages", "screens", "views",
    "templates", "assets", "public", "static", "client", "web",
})
_UI_CAPTURE = re.compile(r"capturas?|screenshots?", re.IGNORECASE)
_UI_BEFORE_AFTER = re.compile(
    r"(?:antes\s*(?:/|y|-)\s*despu[eé]s|before\s*(?:/|and|-)\s*after)",
    re.IGNORECASE,
)
_DESIGN_HEADING = re.compile(r"(?m)^#{2,4}\s+Diseño\s*$")
_NEXT_HEADING = re.compile(r"(?m)^#{1,4}\s+")


def _ui_claimed_paths(paths: list[str]) -> list[str]:
    """Detecta únicamente superficies visuales; respeta tareas backend."""
    result: list[str] = []
    for path in paths:
        lower = path.casefold()
        parts = lower.rstrip("/").split("/")
        if lower.endswith("/") and any(p in _UI_PATH_PARTS for p in parts):
            result.append(path)
        elif lower.endswith(_UI_SUFFIXES):
            result.append(path)
        elif lower.endswith(_UI_SCRIPT_SUFFIXES) and (
            any(p in _UI_PATH_PARTS for p in parts[:-1])
            or len(parts) == 1 and parts[0] in {"app.js", "main.js", "admin.js", "index.js"}
        ):
            result.append(path)
    return result


def _require_ui_design(body: str, paths: list[str]) -> None:
    """La aceptación humana debe fijar capturas reales en dos breakpoints."""
    claimed = _ui_claimed_paths(paths)
    if not claimed:
        return

    headings = list(_DESIGN_HEADING.finditer(body))
    if len(headings) != 1:
        raise IssueContractPreflightError(
            "ui_design_invalid",
            "Rutas de UI requieren una única sección ### Diseño con las dos skills de Factory.",
        )
    start = headings[0].end()
    next_heading = _NEXT_HEADING.search(body, start)
    design = body[start:next_heading.start() if next_heading else len(body)]
    skills = (
        ".claude/skills/impeccable/SKILL.md",
        ".claude/skills/make-interfaces-feel-better/SKILL.md",
    )
    if any(skill not in design for skill in skills):
        raise IssueContractPreflightError(
            "ui_design_invalid",
            "La sección Diseño debe citar .claude/skills/impeccable/SKILL.md "
            "y .claude/skills/make-interfaces-feel-better/SKILL.md.",
        )

    criteria_heading = body.find("### Criterios de aceptación")
    criteria_end = body.find("\n### ", criteria_heading + 1)
    criteria = body[criteria_heading:criteria_end if criteria_end >= 0 else len(body)]
    descriptions = re.findall(r"(?m)^- \[[ xX]\] \[AC-\d{2}\] (.+)$", criteria)
    if not any(
        _UI_CAPTURE.search(description)
        and re.search(r"(?<!\d)390(?:\s*px)?(?!\d)", description)
        and re.search(r"(?<!\d)1440(?:\s*px)?(?!\d)", description)
        and _UI_BEFORE_AFTER.search(description)
        for description in descriptions
    ):
        raise IssueContractPreflightError(
            "ui_design_invalid",
            "Un criterio [AC-NN] debe exigir capturas antes/después a 390 px y 1440 px.",
        )


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

    _require_ui_design(body, list(task["paths"]))

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
    args = sys.argv[1:] if argv is None else argv
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout

    if args:
        _emit(
            output_stream,
            {
                "version": 1,
                "valid": False,
                "code": "usage_error",
                "reason": "El body se recibe únicamente por stdin.",
            },
        )
        return 2

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
