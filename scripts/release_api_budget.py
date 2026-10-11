"""Estimación pura y fail-closed de llamadas GitHub del gate de release.

NO realiza solicitudes, autoriza reintentos, concede checks ni decide releases.
Un piso de solicitudes no demuestra que los comentarios estén paginados por completo.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


PAGE_SIZE = 100
MAX_SEARCH_ROWS = 200
MAX_RESET_EVIDENCE_SECONDS = 3600
DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class ReleaseBudgetError(ValueError):
    """Se usa solo un código estático: nunca incluir payloads o secretos."""


@dataclass(frozen=True)
class ApiBudget:
    search_rows: int
    release_gates: int
    search_calls: int
    comments_calls_min: int
    metadata_calls: int
    total_calls_min: int
    comments_fully_paginated: bool = False

    def public_report(self) -> dict[str, int | bool]:
        """Vista solo numérica y de completitud; no expone cuerpos ni tokens."""
        return {
            "search_rows": self.search_rows,
            "release_gates": self.release_gates,
            "search_calls": self.search_calls,
            "comments_calls_min": self.comments_calls_min,
            "metadata_calls": self.metadata_calls,
            "total_calls_min": self.total_calls_min,
            "comments_fully_paginated": self.comments_fully_paginated,
        }


@dataclass(frozen=True)
class TransportFailure:
    kind: str
    must_fail_closed: bool
    suggested_retry_seconds: int | None
    execution_authorized: bool = False


def _fail(reason: str) -> None:
    raise ReleaseBudgetError(reason)


def _canonical_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or DATETIME.fullmatch(value) is None:
        return False
    try:
        stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _read_pass(pages: Any) -> tuple[tuple[tuple[Any, ...], ...], int]:
    if not isinstance(pages, list) or not pages:
        _fail("search_paginas_incompletas")
    first = pages[0]
    if not isinstance(first, dict) or type(first.get("total_count")) is not int:
        _fail("search_total_invalido")
    count = first["total_count"]
    if not 0 <= count <= MAX_SEARCH_ROWS:
        _fail("search_total_invalido")
    wanted = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
    if len(pages) != wanted:
        _fail("search_paginas_incompletas")
    seen_numbers: set[int] = set()
    seen_ids: set[int] = set()
    seen_node_ids: set[str] = set()
    rows: list[tuple[Any, ...]] = []
    for index, page in enumerate(pages):
        if (not isinstance(page, dict)
            or page.get("incomplete_results") is not False
            or type(page.get("total_count")) is not int
            or page["total_count"] != count
            or not isinstance(page.get("items"), list)):
            _fail("search_pagina_invalida")
        items = page["items"]
        if len(items) != min(PAGE_SIZE, max(0, count - PAGE_SIZE * index)):
            _fail("search_pagina_truncada")
        for item in items:
            if not isinstance(item, dict):
                _fail("search_issue_invalido")
            number, rest_id, state = item.get("number"), item.get("id"), item.get("state")
            graphql_id = item.get("node_id")
            labels = item.get("labels")
            if (type(number) is not int or number <= 0 or number in seen_numbers
                or type(rest_id) is not int or rest_id <= 0 or rest_id in seen_ids
                or not isinstance(graphql_id, str) or not graphql_id.strip()
                or graphql_id in seen_node_ids
                or not isinstance(labels, list)
                or any(not isinstance(label, dict)
                       or not isinstance(label.get("name"), str)
                       or not label["name"] for label in labels)
                or not _canonical_timestamp(item.get("created_at"))
                or state not in ("open", "closed")
                or item.get("pull_request") is not None
                or not isinstance(item.get("title"), str)
                or not item["title"].strip()
                or not isinstance(item.get("body"), str)
                or not _canonical_timestamp(item.get("updated_at"))):
                _fail("search_issue_invalido")
            try:
                fingerprint = hashlib.sha256(json.dumps(
                    item, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                    allow_nan=False,
                ).encode("ascii")).hexdigest()
            except (TypeError, ValueError, OverflowError):
                _fail("search_metadata_no_serializable")
            seen_numbers.add(number)
            seen_ids.add(rest_id)
            seen_node_ids.add(graphql_id)
            rows.append((rest_id, number, state, item["title"],
                         item["body"], item["updated_at"], fingerprint))
    if len(rows) != count:
        _fail("search_total_no_coincide")
    return tuple(rows), len(pages)


def estimate_api_budget(first_pass: Any, second_pass: Any) -> ApiBudget:
    """Cuenta el piso de GETs del shell real sin usar cuerpos como salida.

    La comprobación compara dos lecturas completas, incluido orden y contenido.
    No infiere ausencia de comentarios en páginas que todavía no se leyeron.
    """
    first, first_calls = _read_pass(first_pass)
    second, second_calls = _read_pass(second_pass)
    if first != second or first_calls != second_calls:
        _fail("search_deriva_entre_lecturas")
    selected = sum("factory-release" in row[4] for row in first)
    search_calls = first_calls + second_calls
    metadata_calls = 2  # PR e Issue del trabajo, sin contar endpoints de CI.
    return ApiBudget(
        search_rows=len(first),
        release_gates=selected,
        search_calls=search_calls,
        comments_calls_min=selected,
        metadata_calls=metadata_calls,
        total_calls_min=search_calls + selected + metadata_calls,
    )


def classify_transport_failure(
    status: Any, *, remaining: Any = None, retry_after_seconds: Any = None,
    reset_after_seconds: Any = None, max_retry_seconds: int = 30,
    attempts_used: int = 1, max_attempts: int = 2,
) -> TransportFailure:
    """Solo consejo diagnóstico: ninguna respuesta convierte una falla en GREEN."""
    if (type(status) is not int or not 400 <= status <= 599
        or type(max_retry_seconds) is not int or not 0 <= max_retry_seconds <= 60
        or type(attempts_used) is not int or type(max_attempts) is not int
        or not 1 <= attempts_used <= max_attempts <= 3):
        _fail("transporte_parametros_invalidos")
    if remaining is not None and (type(remaining) is not int or remaining < 0):
        _fail("transporte_cuota_invalida")
    for delay in (retry_after_seconds, reset_after_seconds):
        if delay is not None and (type(delay) is not int
                                  or not 0 <= delay <= MAX_RESET_EVIDENCE_SECONDS):
            _fail("transporte_reset_invalido")
    # Both server hints are minimum wait bounds; never recommend the shorter.
    # A primary-limit retry requires reset evidence, even with Retry-After.
    if status == 403 and remaining == 0:
        kind = "limite_primario"
        delay = reset_after_seconds
        if delay is not None and retry_after_seconds is not None:
            delay = max(delay, retry_after_seconds)
    elif status == 429 or (status == 403 and retry_after_seconds is not None):
        kind = "limite_secundario"
        delay = retry_after_seconds
        if delay is not None and reset_after_seconds is not None:
            delay = max(delay, reset_after_seconds)
    elif status == 403:
        kind, delay = "http_403_no_acreditado", None
    elif status in (401, 404):
        kind, delay = "permisos_o_recurso", None
    elif status >= 500:
        kind, delay = "fallo_red_o_servidor", None
    else:
        kind, delay = "http_error", None
    suggestion = (delay if kind in ("limite_primario", "limite_secundario")
                  and delay is not None and delay <= max_retry_seconds
                  and attempts_used < max_attempts else None)
    return TransportFailure(kind=kind, must_fail_closed=True,
                            suggested_retry_seconds=suggestion)
