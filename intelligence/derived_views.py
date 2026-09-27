"""Primitivas pequeñas para vistas derivadas deterministas y drift checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


class DerivedViewError(ValueError):
    """Contrato inválido o vista derivada inconsistente."""


class DerivedViewDriftError(DerivedViewError):
    """La vista derivada no coincide con la salida canónica esperada."""


@dataclass(frozen=True)
class DerivedViewSpec:
    """Contrato mínimo de una vista derivada."""

    view_id: str
    source: str
    view: str
    mode: str
    generator: str | None
    drift_check: str

    def validate(self) -> None:
        if not self.view_id or not self.source or not self.view:
            raise DerivedViewError("view_id, source y view son obligatorios.")
        if self.mode not in {"generated", "regression"}:
            raise DerivedViewError("mode debe ser generated o regression.")
        if self.mode == "generated" and not self.generator:
            raise DerivedViewError("Una vista generated requiere generator.")
        if self.mode == "regression" and self.generator is not None:
            raise DerivedViewError("Una vista regression no puede declarar generator.")
        if not self.drift_check:
            raise DerivedViewError("drift_check es obligatorio.")
        if self.source == self.view:
            raise DerivedViewError("Una vista derivada no puede ser su propia fuente.")


def render_markdown_table(
    rows: Iterable[Mapping[str, object]],
    columns: Sequence[str],
    *,
    sort_by: str,
) -> str:
    """Renderiza una tabla Markdown byte-estable a partir de filas normalizadas."""
    if not columns:
        raise DerivedViewError("columns no puede estar vacío.")
    if sort_by not in columns:
        raise DerivedViewError("sort_by debe ser una columna declarada.")

    normalized = [
        {column: markdown_cell(row.get(column, "")) for column in columns}
        for row in rows
    ]
    normalized.sort(key=lambda row: row[sort_by])

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(row[column] for column in columns) + " |"
        for row in normalized
    ]
    return "\n".join([header, separator, *body]) + "\n"


def check_drift(expected: str, actual: str) -> None:
    """Falla cerrado cuando la vista comprometida difiere de la salida esperada."""
    if expected != actual:
        raise DerivedViewDriftError("La vista derivada difiere de la salida esperada.")


def replace_delimited_block(
    document: str,
    *,
    start_marker: str,
    end_marker: str,
    content: str,
) -> str:
    """Reemplaza exactamente un bloque delimitado sin tocar los bytes exteriores."""
    if not start_marker or not end_marker or start_marker == end_marker:
        raise DerivedViewError("Los markers de la vista son inválidos.")
    if document.count(start_marker) != 1 or document.count(end_marker) != 1:
        raise DerivedViewError("La vista debe contener exactamente un par de markers.")
    start = document.index(start_marker)
    end = document.find(end_marker, start + len(start_marker))
    if end < 0:
        raise DerivedViewError("Los markers de la vista están desordenados.")
    before = document[: start + len(start_marker)]
    after = document[end:]
    normalized = content.rstrip("\n")
    if start_marker in normalized or end_marker in normalized:
        raise DerivedViewError("El contenido generado contiene markers.")
    return f"{before}\n{normalized}\n{after}"


def markdown_cell(value: object) -> str:
    """Escapa una celda Markdown conservando el contrato histórico."""
    return str(value).strip().replace("\\", "\\\\").replace("|", "\\|")


def _cell(value: object) -> str:
    return markdown_cell(value)
