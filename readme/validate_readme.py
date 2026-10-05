"""Validación fail-closed para README Contract v1/v2 durante la migración."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from intelligence.derived_views import DerivedViewDriftError, check_drift
from readme.generate_readme import generate_readme


_SUPPORTED_CONTRACT_VERSIONS = {1, 2}
_OPERATIONAL_COCKPIT_RE = re.compile(r"(?m)^## Operational Cockpit\s*$")
_MARKDOWN_HTTP_DESTINATION_RE = re.compile(
    r"\]\((https?://[^)\s]+)\)",
    re.IGNORECASE,
)
_GITHUB_ACTIONS_PATH_RE = re.compile(r"^/[^/]+/[^/]+/actions(?:/.*)?$")
_GITHUB_RELEASES_PATH_RE = re.compile(r"^/[^/]+/[^/]+/releases(?:/.*)?$")


def validate_readme(
    readme_text: str,
    contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: Mapping[str, Any],
    progress_snapshot: Mapping[str, Any] | None = None,
) -> None:
    """Valida README v1 legado o v2 vivo sin convertir ausencia de señal en estado."""
    version = contract.get("version")
    if version not in _SUPPORTED_CONTRACT_VERSIONS:
        raise ValueError("README Contract version no soportada.")

    if version == 1 or _uses_legacy_v1_blocks(readme_text, contract):
        expected = generate_readme(
            readme_text,
            contract,
            metadata,
            sources,
            progress_snapshot,
        )
        check_drift(expected, readme_text)
        return

    _validate_v2(readme_text, contract, progress_snapshot)


def _uses_legacy_v1_blocks(
    readme_text: str,
    contract: Mapping[str, Any],
) -> bool:
    blocks = contract.get("derived_blocks")
    if not isinstance(blocks, Mapping):
        return False
    markers: list[str] = []
    for name in ("status", "progress_readiness"):
        block = blocks.get(name)
        if not isinstance(block, Mapping):
            continue
        for key in ("start_marker", "end_marker"):
            marker = block.get(key)
            if isinstance(marker, str) and marker:
                markers.append(marker)
    return any(marker in readme_text for marker in markers)


def _validate_v2(
    readme_text: str,
    contract: Mapping[str, Any],
    progress_snapshot: Mapping[str, Any] | None,
) -> None:
    if not isinstance(readme_text, str) or not readme_text.strip():
        raise ValueError("README v2 debe ser texto no vacío.")
    if progress_snapshot is not None:
        raise ValueError("README v2 no renderiza Progress + Readiness.")

    live_status = contract.get("live_status")
    compatibility = contract.get("compatibility")
    policy = contract.get("content_policy")
    if not isinstance(live_status, Mapping):
        raise ValueError("README Contract v2 sin live_status.")
    if not isinstance(compatibility, Mapping) or not isinstance(policy, Mapping):
        raise ValueError("README Contract v2 incompleto.")

    if live_status.get("commits_for_refresh") is not False:
        raise ValueError("README v2 no permite commits de refresco.")
    if live_status.get("unknown_placeholder_tables") is not False:
        raise ValueError("README v2 no permite tablas UNKNOWN.")
    if live_status.get("renders_progress_readiness") is not False:
        raise ValueError("README v2 no renderiza Progress + Readiness.")
    if compatibility.get("accepted_versions_during_migration") != [1, 2]:
        raise ValueError("README v2 debe mantener transición v1/v2.")
    if policy.get("v2_has_generated_status_blocks") is not False:
        raise ValueError("README v2 no admite status generado por commits.")

    forbidden = (
        "<!-- factory:status:start -->",
        "<!-- factory:status:end -->",
        "<!-- factory:progress-readiness:start -->",
        "<!-- factory:progress-readiness:end -->",
        "### Progress + Readiness",
        "| main SHA | UNKNOWN |",
        "| Progress | UNKNOWN |",
        "| Readiness | UNKNOWN |",
    )
    for token in forbidden:
        if token in readme_text:
            raise ValueError(f"README v2 conserva contenido legado: {token}")

    _validate_live_destinations(readme_text, live_status)


def _validate_live_destinations(
    readme_text: str,
    live_status: Mapping[str, Any],
) -> None:
    raw_allowed_hosts = live_status.get("allowed_hosts")
    if (
        not isinstance(raw_allowed_hosts, list)
        or not raw_allowed_hosts
        or any(not isinstance(host, str) or not host.strip() for host in raw_allowed_hosts)
    ):
        raise ValueError("README Contract v2 requiere allowed_hosts explícitos.")
    allowed_hosts = {host.strip().lower() for host in raw_allowed_hosts}

    match = _OPERATIONAL_COCKPIT_RE.search(readme_text)
    if match is None:
        raise ValueError("README v2 debe declarar Operational Cockpit.")
    section_tail = readme_text[match.end():]
    next_section = re.search(r"(?m)^##\s+", section_tail)
    cockpit = (
        section_tail[: next_section.start()]
        if next_section is not None
        else section_tail
    )

    destinations = _MARKDOWN_HTTP_DESTINATION_RE.findall(cockpit)
    if not destinations:
        raise ValueError("README v2 debe enlazar destinos vivos Markdown reales.")

    parsed_destinations = []
    for destination in destinations:
        parsed = urlparse(destination)
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https" or not host:
            raise ValueError("README v2 exige destinos vivos HTTPS válidos.")
        if host not in allowed_hosts:
            raise ValueError(
                f"README v2 enlaza un host vivo no permitido: {host}."
            )
        parsed_destinations.append((host, parsed.path))

    if not any(
        host == "github.com" and _GITHUB_ACTIONS_PATH_RE.fullmatch(path)
        for host, path in parsed_destinations
    ):
        raise ValueError("README v2 debe enlazar GitHub Actions real.")
    if not any(
        host == "github.com" and _GITHUB_RELEASES_PATH_RE.fullmatch(path)
        for host, path in parsed_destinations
    ):
        raise ValueError("README v2 debe enlazar GitHub Releases real.")
    if not any(
        host == "control.condorapp.com.co" and path == "/"
        for host, path in parsed_destinations
    ):
        raise ValueError("README v2 debe enlazar el Orquestador real.")


__all__ = ["DerivedViewDriftError", "validate_readme"]
