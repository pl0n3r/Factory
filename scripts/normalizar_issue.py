#!/usr/bin/env python3
"""Normalización determinista de Issues legacy al contrato ejecutable de Factory."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable

from scripts.aceptacion_kit import CHECK_NAME, FORBIDDEN_CHECKS, TEST_TARGET

MAX_BODY = 200_000
CANONICAL_HEADINGS = (
    "### Contexto",
    "### Alcance",
    "### Fuera de alcance",
    "### Criterios de aceptación",
    "### Contrato ejecutable",
)
HEADING_ALIASES = {
    "contexto": "### Contexto",
    "problema": "### Contexto",
    "qué pasó": "### Contexto",
    "que paso": "### Contexto",
    "evidencia": "### Contexto",
    "alcance": "### Alcance",
    "trabajo": "### Alcance",
    "propuesta": "### Alcance",
    "objetivo": "### Alcance",
    "fuera de alcance": "### Fuera de alcance",
    "fuera": "### Fuera de alcance",
    "límites": "### Fuera de alcance",
    "limites": "### Fuera de alcance",
    "criterios": "### Criterios de aceptación",
    "criterios de aceptación": "### Criterios de aceptación",
    "criterios de aceptacion": "### Criterios de aceptación",
    "contrato ejecutable": "### Contrato ejecutable",
}
AC_LINE = re.compile(r"^- \[[ xX]\] \[(AC-[0-9]{2})\] (.{1,500})$")
TEST_IN_TEXT = re.compile(
    r"(tests/[A-Za-z0-9_/-]+\.py::[A-Za-z_][A-Za-z0-9_]*::test_[A-Za-z0-9_]+)"
)
CHECK_IN_TEXT = re.compile(r"(?:Check|check)\s+`([^`\r\n]{1,120})`")
PATH_LINE = re.compile(r"^\s*[-*]\s+`([^\r\n`]+)`\s*$")
FORMAT_COMMENT_MARKER = "factory-format-repair"


class NormalizationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizationResult:
    body: str
    complete: bool
    changed: bool
    missing: tuple[str, ...]
    comment: str | None
    dedup_key: str


def _heading_level(line: str) -> int:
    stripped = line.lstrip()
    hashes = len(stripped) - len(stripped.lstrip("#"))
    return hashes if hashes and len(stripped) > hashes and stripped[hashes] == " " else 0


def _heading_name(line: str) -> str | None:
    stripped = line.strip()
    if _heading_level(line) not in {2, 3}:
        return None
    title = stripped.lstrip("#").strip().casefold()
    return HEADING_ALIASES.get(title)


def _split_sections(body: str) -> tuple[list[str], dict[str, list[str]], list[str]]:
    lines = body.splitlines()
    prelude: list[str] = []
    sections: dict[str, list[str]] = {}
    extras: list[str] = []
    current: str | None = None
    for line in lines:
        mapped = _heading_name(line)
        if mapped is not None:
            current = mapped
            sections.setdefault(current, [])
            continue
        level = _heading_level(line)
        if level in {2, 3}:
            current = None
            extras.append(line)
            continue
        if level > 3 and current is not None:
            sections[current].append(line)
            continue
        if current is None:
            if not sections:
                prelude.append(line)
            else:
                extras.append(line)
        else:
            sections[current].append(line)
    return prelude, sections, extras


def _criterion_rows(section: str) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    missing: list[str] = []
    seen: set[str] = set()
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("- ["):
            continue
        match = AC_LINE.fullmatch(line)
        if not match:
            missing.append("criterio AC-* con sintaxis canónica")
            continue
        criterion_id, description = match.groups()
        if criterion_id in seen:
            missing.append(f"{criterion_id} duplicado")
            continue
        seen.add(criterion_id)

        test_match = TEST_IN_TEXT.search(description)
        if test_match and TEST_TARGET.fullmatch(test_match.group(1)):
            rows.append({"id": criterion_id, "kind": "test", "target": test_match.group(1)})
            continue

        check_match = CHECK_IN_TEXT.search(description)
        if check_match:
            target = check_match.group(1).strip()
            if CHECK_NAME.fullmatch(target) and target not in FORBIDDEN_CHECKS:
                rows.append({"id": criterion_id, "kind": "check", "target": target})
                continue

        missing.append(f"{criterion_id} sin target ejecutable explícito")
    if not rows and not missing:
        missing.append("al menos un criterio AC-*")
    return rows, missing


def _acceptance_marker(section: str) -> tuple[str | None, tuple[str, ...]]:
    rows, missing = _criterion_rows(section)
    if missing:
        return None, tuple(dict.fromkeys(missing))
    payload = json.dumps(
        {"version": 1, "criteria": rows},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"<!-- factory-acceptance {payload} -->", ()


def _extract_claim_paths(body: str) -> tuple[str, ...]:
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().casefold() in {"### rutas reclamadas", "## rutas reclamadas"}:
            start = index + 1
            break
    if start is None:
        return ()
    paths: list[str] = []
    for line in lines[start:]:
        if line.lstrip().startswith("#"):
            break
        match = PATH_LINE.fullmatch(line)
        if match:
            value = match.group(1).strip()
            if (
                value
                and not value.startswith(("/", "./"))
                and "\\" not in value
                and ".." not in value.split("/")
                and value not in paths
            ):
                paths.append(value)
    return tuple(paths)


def _task_marker(body: str, metadata: dict[str, object] | None) -> tuple[str | None, tuple[str, ...]]:
    if "<!-- factory-plan-task " in body:
        return None, ()
    paths = _extract_claim_paths(body)
    if not paths:
        return None, ("Rutas reclamadas",)
    if metadata is None:
        return None, ("metadata factory-plan-task",)

    required = ("epic", "task_key", "order", "owner", "roles", "depends_on")
    absent = [name for name in required if name not in metadata]
    if absent:
        return None, tuple(f"metadata {name}" for name in absent)

    epic = metadata["epic"]
    order = metadata["order"]
    task_key = metadata["task_key"]
    owner = metadata["owner"]
    roles = metadata["roles"]
    depends_on = metadata["depends_on"]
    if (
        isinstance(epic, bool)
        or not isinstance(epic, int)
        or epic < 1
        or isinstance(order, bool)
        or not isinstance(order, int)
        or order < 1
        or not isinstance(task_key, str)
        or not 1 <= len(task_key) <= 32
        or not task_key.isascii()
        or not task_key[0].isalpha()
        or not task_key[0].isupper()
        or any(not (char.isupper() or char.isdigit() or char in "_-") for char in task_key)
        or not isinstance(owner, str)
        or not owner
        or not owner.isascii()
        or any(not (char.isalnum() or char == "-") for char in owner)
        or not isinstance(roles, list)
        or not roles
        or not all(isinstance(role, str) and role.strip() for role in roles)
        or not isinstance(depends_on, list)
        or not all(
            isinstance(number, int) and not isinstance(number, bool) and number > 0
            for number in depends_on
        )
    ):
        return None, ("metadata factory-plan-task inválida",)

    payload = {
        "version": 1,
        "epic": epic,
        "task_key": task_key,
        "order": order,
        "owner": owner,
        "roles": sorted(dict.fromkeys(role.strip() for role in roles)),
        "depends_on": list(dict.fromkeys(depends_on)),
        "paths": list(paths),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"<!-- factory-plan-task {encoded} -->", ()


def _dedup_key(body: str) -> str:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"issue-format:{digest}"


def _repair_comment(missing: Iterable[str], dedup_key: str) -> str:
    details = "; ".join(dict.fromkeys(item for item in missing if item))
    return (
        f"<!-- {FORMAT_COMMENT_MARKER} {dedup_key} -->\n"
        "No puedo normalizar este Issue sin inventar información. "
        f"Falta: {details}. "
        "Añade targets ejecutables como "
        "`tests/test_x.py::Clase::test_caso` o `Check \`Nombre\``, "
        "y conserva rutas reclamadas explícitas."
    )


def comment_already_present(comments: Iterable[str], dedup_key: str) -> bool:
    marker = f"<!-- {FORMAT_COMMENT_MARKER} {dedup_key} -->"
    return any(marker in str(comment) for comment in comments)


def normalize_issue_body(
    body: str,
    *,
    task_metadata: dict[str, object] | None = None,
) -> NormalizationResult:
    """Normaliza encabezados y markers sin fabricar targets, rutas ni metadata."""
    if not isinstance(body, str) or not 1 <= len(body) <= MAX_BODY:
        raise NormalizationError("Body del Issue inválido o demasiado grande.")

    original = body
    prelude, sections, extras = _split_sections(body)
    missing: list[str] = []
    rendered: list[str] = []

    if any(line.strip() for line in prelude):
        rendered.extend(line for line in prelude if line.strip())
        rendered.append("")

    for heading in CANONICAL_HEADINGS:
        content = "\n".join(sections.get(heading, [])).strip()
        if heading == "### Contrato ejecutable":
            existing = "<!-- factory-acceptance " in body
            if not content and not existing:
                criteria = "\n".join(sections.get("### Criterios de aceptación", [])).strip()
                marker, marker_missing = _acceptance_marker(criteria)
                if marker is not None:
                    content = marker
                else:
                    missing.extend(marker_missing)
            elif content and "<!-- factory-acceptance " not in content and not existing:
                marker, marker_missing = _acceptance_marker(
                    "\n".join(sections.get("### Criterios de aceptación", [])).strip()
                )
                if marker is not None:
                    content = content + "\n\n" + marker
                else:
                    missing.extend(marker_missing)
        if not content:
            missing.append(heading.removeprefix("### "))
            content = "_Pendiente de completar sin inferencias._"
        rendered.extend((heading, "", content, ""))

    # Conserva prosa no clasificada después de las cinco secciones para no perder contenido.
    extra_text = "\n".join(line for line in extras if line.strip()).strip()
    if extra_text:
        rendered.extend(("### Notas legacy conservadas", "", extra_text, ""))

    normalized = "\n".join(rendered).rstrip() + "\n"
    task_marker, task_missing = _task_marker(original, task_metadata)
    missing.extend(task_missing)
    if task_marker is not None:
        normalized += "\n" + task_marker + "\n"
    elif "<!-- factory-plan-task " in original:
        # El marker existente no se reescribe ni se duplica.
        marker_start = original.index("<!-- factory-plan-task ")
        marker_end = original.find("-->", marker_start)
        if marker_end >= 0:
            normalized += "\n" + original[marker_start:marker_end + 3].strip() + "\n"

    dedup_key = _dedup_key(original)
    unique_missing = tuple(dict.fromkeys(missing))
    complete = not unique_missing
    comment = None if complete else _repair_comment(unique_missing, dedup_key)
    return NormalizationResult(
        body=normalized,
        complete=complete,
        changed=normalized.strip() != original.strip(),
        missing=unique_missing,
        comment=comment,
        dedup_key=dedup_key,
    )


def plan_issue_normalization(
    body: str,
    *,
    existing_comments: Iterable[str] = (),
    task_metadata: dict[str, object] | None = None,
    state: str = "open",
    has_active_reservation: bool = False,
) -> dict[str, object]:
    """Plan puro: editar+reintentar una vez, comentar+seguir, o no tocar."""
    if state != "open" or has_active_reservation:
        return {
            "action": "skip",
            "reason": "closed_or_reserved",
            "retry_once": False,
            "continue_same_cycle": True,
        }

    result = normalize_issue_body(body, task_metadata=task_metadata)
    if result.complete:
        return {
            "action": "edit_and_retry_once",
            "body": result.body,
            "changed": result.changed,
            "retry_once": True,
            "continue_same_cycle": True,
            "dedup_key": result.dedup_key,
        }

    should_comment = not comment_already_present(existing_comments, result.dedup_key)
    return {
        "action": "comment_and_skip",
        "comment": result.comment if should_comment else None,
        "should_comment": should_comment,
        "missing": result.missing,
        "retry_once": False,
        "continue_same_cycle": True,
        "dedup_key": result.dedup_key,
    }


__all__ = [
    "NormalizationError",
    "NormalizationResult",
    "comment_already_present",
    "normalize_issue_body",
    "plan_issue_normalization",
]
