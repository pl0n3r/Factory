"""Validación fail-closed para README Contract v1/v2 durante la migración."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from intelligence.derived_views import DerivedViewDriftError, check_drift
from readme.generate_readme import generate_readme


_SUPPORTED_CONTRACT_VERSIONS = {1, 2}


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

    lowered = readme_text.lower()
    if "github.com/" not in lowered or "/actions" not in lowered:
        raise ValueError("README v2 debe enlazar estado vivo de GitHub Actions.")
    if "/releases" not in lowered:
        raise ValueError("README v2 debe enlazar GitHub Releases.")
    if "control.condorapp.com.co" not in lowered:
        raise ValueError("README v2 debe enlazar el Orquestador como detalle operativo.")


__all__ = ["DerivedViewDriftError", "validate_readme"]
