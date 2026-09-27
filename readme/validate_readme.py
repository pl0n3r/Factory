"""Validación fail-closed de drift para README Contract v1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from intelligence.derived_views import DerivedViewDriftError, check_drift
from readme.generate_readme import generate_readme


def validate_readme(
    readme_text: str,
    contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> None:
    """Compara el README comprometido con la salida canónica del mismo input."""
    expected = generate_readme(readme_text, contract, metadata, sources)
    check_drift(expected, readme_text)


__all__ = ["DerivedViewDriftError", "validate_readme"]
