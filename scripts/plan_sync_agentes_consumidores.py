#!/usr/bin/env python3
"""Offline, read-only proposal for syncing Factory agent principles to consumers.

Build-ahead only: no writes, no network, no authority to apply updates.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

REPOSITORIES = (
    "pl0n3r/AutoFactory", "pl0n3r/Condor", "pl0n3r/ControlBot",
    "pl0n3r/FactoryRunner", "pl0n3r/GrindFlow", "pl0n3r/brvtal",
)
BEGIN = "<!-- factory-principios-sync:start -->"
END = "<!-- factory-principios-sync:end -->"
HEADING = "## Principios de construcción de la fábrica"
MAX_DOCUMENT_BYTES = 200_000


class SyncPlanError(ValueError):
    """Invalid or incomplete evidence: fail closed without reflecting text."""


def _validate_text(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\r" in raw:
        raise SyncPlanError("invalid_document")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError:
        # Even malformed Unicode must fail closed with a stable, private code.
        raise SyncPlanError("invalid_document") from None
    if size > MAX_DOCUMENT_BYTES:
        raise SyncPlanError("invalid_document")
    return raw


def _principles(template: object) -> str:
    source = _validate_text(template)
    if source.count(HEADING) != 1 or "factory-principios-sync" in source:
        raise SyncPlanError("invalid_principles_source")
    pattern = re.compile(r"^## Principios de construcción de la fábrica\s*$", re.M)
    match = pattern.search(source)
    if match is None:
        raise SyncPlanError("invalid_principles_source")
    start = match.start()
    next_section = re.search(r"^## [^#\n]", source[match.end():], re.M)
    end = match.end() + next_section.start() if next_section else len(source)
    content = source[start:end].strip("\n")
    # Contract v1 only permits the exact approved footer texts. Without an
    # explicit end marker, arbitrary unheaded lines after the footer would
    # otherwise be projected into every consumer.
    footer = content.split("### Límite explícito del template", 1)[-1].strip()
    if footer not in (
        "Este texto no sincroniza ni modifica consumidores.",
        "Este texto no sincroniza ni modifica consumidores, no constituye aprobación humana o revisión independiente y no activa el orquestador. Ningún cambio queda listo para merge, release, `Factory@v1`, despliegue o live sin CI, revisión independiente, protección de rama y autoridad comprobadas. Se prohíben acceso a datos reales, gasto, compra, credenciales, permisos nuevos y borrados irreversibles sin su puerta legítima.",
    ):
        raise SyncPlanError("invalid_principles_source")
    headings = re.findall(r"^### (Regla 0|Principio [1-8]) — ", content, re.M)
    all_subsections = re.findall(r"^### [^\n]+", content, re.M)
    if (len(all_subsections) != 10
            or all_subsections[-1] != "### Límite explícito del template"
            or headings != ["Regla 0"] + [f"Principio {x}" for x in range(1, 9)]
            or content.count("### Límite explícito del template") != 1
            or "no otorga permisos de ejecución" not in source
            or "no sincroniza ni modifica consumidores" not in content):
        raise SyncPlanError("invalid_principles_source")
    return content


def _render_consumer(existing: str, principles: str) -> tuple[str, str]:
    # Reserved sync identifiers must be complete, standalone marker lines.
    # A truncated delimiter cannot be treated as an empty, unsynced file.
    if any("factory-principios-sync" in line and line not in (BEGIN, END)
           for line in existing.splitlines()):
        raise SyncPlanError("invalid_sync_markers")
    # A Markdown example is local documentation, not a managed block. Never
    # replace literal sync markers occurring inside fenced code examples.
    fence_char = None
    fence_width = 0
    for line in existing.splitlines():
        if fence_char is None:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if opening is not None:
                fence_char = opening.group(1)[0]
                fence_width = len(opening.group(1))
        else:
            if "factory-principios-sync" in line:
                raise SyncPlanError("invalid_sync_markers")
            closing = re.fullmatch(r" {0,3}(`{3,}|~{3,})[ \\t]*", line)
            if (closing is not None and closing.group(1)[0] == fence_char
                    and len(closing.group(1)) >= fence_width):
                fence_char = None
    if existing.count(BEGIN) != existing.count(END) or existing.count(BEGIN) > 1:
        raise SyncPlanError("invalid_sync_markers")
    if BEGIN not in existing:
        if HEADING in existing:
            raise SyncPlanError("ambiguous_unmanaged_principles")
        gap = "\n" if existing.endswith("\n") else "\n\n"
        return existing + gap + BEGIN + "\n" + principles + "\n" + END + "\n", "insert"
    lines = existing.splitlines(keepends=True)
    begin_positions = [i for i, line in enumerate(lines) if line.rstrip("\n") == BEGIN]
    end_positions = [i for i, line in enumerate(lines) if line.rstrip("\n") == END]
    if (len(begin_positions) != 1 or len(end_positions) != 1
            or begin_positions[0] >= end_positions[0]
            or not lines[begin_positions[0]].endswith("\n")
            or (len(lines) > end_positions[0] + 1 and not lines[end_positions[0]].endswith("\n"))):
        raise SyncPlanError("invalid_sync_markers")
    outside_block = ("".join(lines[:begin_positions[0]])
                     + "".join(lines[end_positions[0] + 1:]))
    if HEADING in outside_block:
        raise SyncPlanError("ambiguous_unmanaged_principles")
    proposed = ("".join(lines[:begin_positions[0] + 1])
                + principles + "\n"
                + "".join(lines[end_positions[0]:]))
    return proposed, "noop" if proposed == existing else "replace"


def plan_sync(template_text: str, consumer_text_by_repo: Mapping[str, str]) -> dict:
    """Plan six exact consumers. Return hashes/status only, never content/apply rights."""
    principles = _principles(template_text)
    if (not isinstance(consumer_text_by_repo, Mapping)
            or set(consumer_text_by_repo) != set(REPOSITORIES)
            or len(consumer_text_by_repo) != len(REPOSITORIES)):
        raise SyncPlanError("incomplete_consumer_inventory")
    entries = []
    for repository_ref in REPOSITORIES:
        existing = _validate_text(consumer_text_by_repo[repository_ref])
        projected, action = _render_consumer(existing, principles)
        # The projected document must respect the same safety budget as the
        # input. Appending a valid principles block may overflow a near-limit
        # consumer file; never suggest an unrepresentable change.
        _validate_text(projected)
        entries.append({
            "repository_ref": repository_ref,
            "action": action,
            "original_sha256": hashlib.sha256(existing.encode("utf-8")).hexdigest(),
            "proposed_sha256": hashlib.sha256(projected.encode("utf-8")).hexdigest(),
        })
    return {"status": "planned", "can_apply": False, "consumers": entries}


__all__ = ["SyncPlanError", "plan_sync"]
