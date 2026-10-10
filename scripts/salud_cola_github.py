#!/usr/bin/env python3
"""Proyección pura de una página REST de GitHub; NO realiza HTTP ni I/O.

El transporte autenticado debe capturar URL/status/Link/payload reales.
La función valida coherencia de la evidencia recibida, no su autenticidad.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

REPOSITORIES = (
    "Factory", "Condor", "GrindFlow", "brvtal",
    "ControlBot", "AutoFactory", "FactoryRunner",
)
MAX_PAGE = 100
PAGE_SIZE = 100
MAX_LABELS = 40
# Explicit state vocabulary shared with the snapshot adapter, including the
# recovery label. Unknown workflow prefixes must never be hidden.
STATE_LABELS = frozenset((
    "estado: disponible", "estado: reservado", "estado: bloqueado",
    "estado: planificado", "estado: en revisión",
    "estado: requiere recuperación",
    "status: available", "status: reserved", "status: blocked",
    "status: planned", "status: in review", "status: recovery required",
))
_REL = re.compile(r'<([^<>]+)>;\s*rel="(next|prev|first|last)"')


class GitHubPageError(ValueError):
    """Respuesta no confiable o imposible de proyectar completamente."""


def _int(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _page_from_url(url: object, repo: str) -> int:
    if (type(url) is not str or len(url) > 900
            or any(ord(char) < 32 or ord(char) == 127 for char in url)):
        # urlsplit silently strips CR/LF/TAB (and leading C0) in Python.
        # Check the captured, unmodified URL before parsing components.
        raise GitHubPageError("invalid_request_url")
    try:
        u = urlsplit(url)
        query = parse_qsl(u.query, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise GitHubPageError("invalid_request_url") from exc
    if (u.scheme != "https" or u.netloc != "api.github.com"
            or u.path != f"/repos/pl0n3r/{repo}/issues"
            or u.fragment or len(query) != 3):
        raise GitHubPageError("invalid_request_url")
    # parse_qsl silently decodes percent-encoded query keys/values. The
    # canonical REST contract forbids encoded aliases (page=%31, etc.),
    # even when they would decode to the expected parameters.
    if "%" in u.query or "+" in u.query:
        raise GitHubPageError("invalid_request_url")
    params = dict(query)
    if (len(params) != 3 or set(params) != {"state", "per_page", "page"}
            or params["state"] != "open" or params["per_page"] != "100"):
        raise GitHubPageError("invalid_request_url")
    value = params["page"]
    if not value.isascii() or not value.isdecimal() or value.startswith("0"):
        raise GitHubPageError("invalid_request_url")
    page = int(value)
    if not _int(page, 1, MAX_PAGE):
        raise GitHubPageError("invalid_request_url")
    return page


def _link_has_next(header: object, repo: str, page: int) -> bool:
    if header is None or header == "":
        if page != 1:
            # A non-first page should carry at least its prev relation.
            raise GitHubPageError("incomplete_link")
        return False
    if (type(header) is not str or len(header) > 4000
            or any(ord(char) < 32 or ord(char) == 127 for char in header)):
        raise GitHubPageError("invalid_link")
    links: dict[str, int] = {}
    for part in header.split(","):
        match = _REL.fullmatch(part.strip())
        if not match:
            raise GitHubPageError("invalid_link")
        url, rel = match.groups()
        if rel in links:
            raise GitHubPageError("duplicate_link_relation")
        links[rel] = _page_from_url(url, repo)
    if not links:
        raise GitHubPageError("invalid_link")
    if page == 1 and "prev" in links:
        raise GitHubPageError("inconsistent_link")
    if page > 1 and links.get("prev") != page - 1:
        raise GitHubPageError("incomplete_link")
    if "first" in links and links["first"] != 1:
        raise GitHubPageError("inconsistent_link")
    next_page = links.get("next")
    last_page = links.get("last")
    if next_page is not None:
        if next_page != page + 1 or (last_page is not None and last_page < next_page):
            raise GitHubPageError("non_contiguous_link")
    elif last_page is not None and last_page != page:
        raise GitHubPageError("inconsistent_link")
    return next_page is not None


def parse_github_issue_page(repo: object, requested_page: object,
                            request_url: object, status_code: object,
                            link_header: object, payload: object) -> dict:
    """Retorna página compatible con assemble_inventory de Factory #1100.

    No infiere cause/roadmap, no expone títulos, body, usuarios ni URLs.
    """
    if type(repo) is not str or repo not in REPOSITORIES:
        raise GitHubPageError("invalid_repository")
    if not _int(requested_page, 1, MAX_PAGE):
        raise GitHubPageError("invalid_requested_page")
    actual_page = _page_from_url(request_url, repo)
    if actual_page != requested_page:
        raise GitHubPageError("page_mismatch")
    if type(status_code) is not int or status_code != 200:
        raise GitHubPageError("invalid_http_status")
    has_next = _link_has_next(link_header, repo, actual_page)
    if type(payload) is not list or len(payload) > PAGE_SIZE:
        raise GitHubPageError("invalid_payload")
    # With per_page=100, a nonterminal page MUST be full; otherwise the
    # declared 'next' chain could conceal omitted issue records.
    if has_next and len(payload) != PAGE_SIZE:
        raise GitHubPageError("nonterminal_page_underfilled")
    issues: list[dict] = []
    seen: set[int] = set()
    for raw in payload:
        if type(raw) is not dict:
            raise GitHubPageError("invalid_issue")
        # An open-query request is not proof of a coherent response row.
        # A closed or state-less issue must never become available downstream.
        if type(raw.get("state")) is not str or raw["state"] != "open":
            raise GitHubPageError("invalid_issue_state")
        number, labels = raw.get("number"), raw.get("labels")
        if not _int(number, 1, 100000000) or number in seen:
            raise GitHubPageError("invalid_or_duplicate_issue")
        seen.add(number)
        if type(labels) is not list or len(labels) > MAX_LABELS:
            raise GitHubPageError("invalid_labels")
        names: list[str] = []
        for item in labels:
            if type(item) is not dict:
                raise GitHubPageError("invalid_labels")
            label = item.get("name")
            if type(label) is not str or not 1 <= len(label) <= 100:
                raise GitHubPageError("invalid_labels")
            if label in STATE_LABELS:
                names.append(label)
            elif label.startswith(("estado:", "status:")):
                # Never silently discard an unknown workflow status if
                # another label could otherwise make the Issue actionable.
                raise GitHubPageError("unknown_status_label")
            # Other labels are arbitrary user-editable text: omit entirely.

        is_pr = "pull_request" in raw
        if is_pr and (type(raw["pull_request"]) is not dict
                      or not raw["pull_request"]):
            raise GitHubPageError("invalid_pull_request")
        issues.append({"number": number, "labels": names,
                       "pull_request": is_pr, "blocker": None})
    return {"page_number": actual_page, "has_next": has_next, "issues": issues}


def parse_github_issue_sequence(repo: object, responses: object) -> dict:
    """Verifica continuidad y 'last' estable entre capturas REST completas.

    Los elementos representan respuestas HTTP ya autenticadas por un caller.
    Comparar last/next/prev NO hace que el listado sea atómico: el collector
    futuro debe hacer comprobaciones de estabilidad interlecturas antes de
    usar el inventario como fuente de despachos o incidentes.
    """
    if type(responses) is not list or not 1 <= len(responses) <= MAX_PAGE:
        raise GitHubPageError("invalid_page_sequence")
    pages: list[dict] = []
    seen_numbers: set[int] = set()
    for n, raw in enumerate(responses, start=1):
        if (type(raw) is not dict or set(raw) !=
                {"request_url", "status_code", "link_header", "payload"}):
            raise GitHubPageError("invalid_page_capture")
        result = parse_github_issue_page(
            repo, n, raw["request_url"], raw["status_code"],
            raw["link_header"], raw["payload"],
        )
        if result["has_next"] is not (n < len(responses)):
            raise GitHubPageError("incomplete_page_sequence")
        header = raw["link_header"]
        declared_last = None
        if header:
            # Each relation was syntax-checked by parse_github_issue_page.
            for part in header.split(","):
                match = _REL.fullmatch(part.strip())
                if match and match.group(2) == "last":
                    declared_last = _page_from_url(match.group(1), repo)
        if (n == 1 and len(responses) > 1 and declared_last is None):
            raise GitHubPageError("missing_last_relation")
        if declared_last is not None and declared_last != len(responses):
            raise GitHubPageError("inconsistent_last_relation")
        for issue in result["issues"]:
            if issue["number"] in seen_numbers:
                raise GitHubPageError("cross_page_duplicate_issue")
            seen_numbers.add(issue["number"])
        pages.append(result)
    return {"name": repo, "pages": pages}
