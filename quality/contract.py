"""Quality Contract v1: evidencia exigible por superficie, sin score mágico."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any

VERSION = 1
CRITICALITY = {"low", "medium", "high", "critical"}
GATES = {
    "unit", "integration", "contract", "database", "tenancy", "e2e",
    "browser", "mobile", "accessibility", "security", "performance",
    "resilience", "migration", "smoke", "observability",
}
ACCESSIBILITY = {"NOT_APPLICABLE", "WCAG_AA", "WCAG_AAA"}
MIGRATION = {"NOT_APPLICABLE", "FORWARD_ROLLBACK", "EXPAND_CONTRACT"}
SONAR_VISIBILITY = {"public", "private"}
SONAR_ANALYSIS_METHOD = {"automatic", "ci"}
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)\b\s*[:=]"
    r"|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)
MAX_SURFACES = 50
MAX_ITEMS = 64
MAX_FRESHNESS_SECONDS = 31_536_000
MAX_SONAR_DEBT_ITEMS = 1_000_000
MAX_SONAR_DEBT_AGE_DAYS = 36_500


class QualityContractError(ValueError):
    """Quality Contract inválido."""


def validate_quality_contract(payload: Any) -> dict[str, Any]:
    """Valida y normaliza Quality Contract v1 de forma determinista."""
    _reject_sensitive(payload)
    required = {
        "version", "project", "surfaces", "invariants", "compatibility",
        "accessibility", "migration", "smoke", "evidence_freshness_seconds",
        "dimensions",
    }
    data = _closed_optional(payload, required, {"sonar"}, "contract")
    if data["version"] != VERSION:
        raise QualityContractError("version debe ser 1.")

    compatibility = _exact(
        data["compatibility"], {"runtimes", "browsers", "devices"}, "compatibility"
    )
    dimensions = _exact(data["dimensions"], {"performance", "recovery"}, "dimensions")

    normalized = {
        "version": VERSION,
        "project": _identifier(data["project"], "project"),
        "surfaces": _surfaces(data["surfaces"]),
        "invariants": _catalog(data["invariants"], None, "invariants", require_nonempty=True),
        "compatibility": {
            key: _catalog(compatibility[key], None, f"compatibility.{key}")
            for key in ("runtimes", "browsers", "devices")
        },
        "accessibility": _enum_object(
            data["accessibility"], "target", ACCESSIBILITY, "accessibility"
        ),
        "migration": _enum_object(data["migration"], "strategy", MIGRATION, "migration"),
        "smoke": _external_ref(data["smoke"], "smoke"),
        "evidence_freshness_seconds": _bounded_int(
            data["evidence_freshness_seconds"], "evidence_freshness_seconds"
        ),
        "dimensions": {
            key: _external_ref(dimensions[key], f"dimensions.{key}")
            for key in ("performance", "recovery")
        },
    }
    if "sonar" in data:
        normalized["sonar"] = _sonar(data["sonar"])
    return normalized


def canonical_quality_contract(payload: Any) -> str:
    return json.dumps(
        validate_quality_contract(payload), ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    )


def quality_contract_fingerprint(payload: Any) -> str:
    return hashlib.sha256(canonical_quality_contract(payload).encode()).hexdigest()


def _sonar(value: Any) -> dict[str, Any]:
    row = _exact(
        value,
        {
            "expected_visibility",
            "analysis_method",
            "max_analysis_age_seconds",
            "max_organization_line_usage_percent",
            "max_open_vulnerabilities",
            "max_open_bugs",
            "max_open_hotspots",
            "max_debt_age_days",
        },
        "sonar",
    )
    visibility = row["expected_visibility"]
    if not isinstance(visibility, str) or visibility not in SONAR_VISIBILITY:
        raise QualityContractError("sonar.expected_visibility fuera del catálogo.")
    method = row["analysis_method"]
    if not isinstance(method, str) or method not in SONAR_ANALYSIS_METHOD:
        raise QualityContractError("sonar.analysis_method fuera del catálogo.")

    return {
        "expected_visibility": visibility,
        "analysis_method": method,
        "max_analysis_age_seconds": _bounded_int(
            row["max_analysis_age_seconds"], "sonar.max_analysis_age_seconds"
        ),
        "max_organization_line_usage_percent": _bounded_int_range(
            row["max_organization_line_usage_percent"],
            "sonar.max_organization_line_usage_percent",
            minimum=1,
            maximum=100,
        ),
        "max_open_vulnerabilities": _bounded_nonnegative_int(
            row["max_open_vulnerabilities"], "sonar.max_open_vulnerabilities"
        ),
        "max_open_bugs": _bounded_nonnegative_int(
            row["max_open_bugs"], "sonar.max_open_bugs"
        ),
        "max_open_hotspots": _bounded_nonnegative_int(
            row["max_open_hotspots"], "sonar.max_open_hotspots"
        ),
        "max_debt_age_days": _bounded_int_range(
            row["max_debt_age_days"],
            "sonar.max_debt_age_days",
            minimum=0,
            maximum=MAX_SONAR_DEBT_AGE_DAYS,
        ),
    }


def _surfaces(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > MAX_SURFACES:
        raise QualityContractError("surfaces debe ser lista no vacía y acotada.")
    seen, result = set(), []
    for raw in value:
        row = _exact(raw, {"id", "criticality", "required_gates"}, "surface")
        surface_id = _identifier(row["id"], "surface.id")
        if surface_id in seen:
            raise QualityContractError("surface.id duplicado.")
        seen.add(surface_id)
        criticality = row["criticality"]
        if criticality not in CRITICALITY:
            raise QualityContractError("surface.criticality fuera del catálogo.")
        result.append({
            "id": surface_id,
            "criticality": criticality,
            "required_gates": _catalog(
                row["required_gates"], GATES, "surface.required_gates", require_nonempty=True
            ),
        })
    return sorted(result, key=lambda row: row["id"])


def _external_ref(value: Any, label: str) -> dict[str, Any]:
    row = _exact(value, {"required", "source_ref"}, label)
    if type(row["required"]) is not bool:
        raise QualityContractError(f"{label}.required debe ser booleano.")
    ref = row["source_ref"]
    if row["required"]:
        if not isinstance(ref, str) or _REF.fullmatch(ref) is None:
            raise QualityContractError(f"{label}.source_ref inválida.")
    elif ref is not None:
        raise QualityContractError(f"{label}.source_ref debe ser null cuando no aplica.")
    return {"required": row["required"], "source_ref": ref}


def _enum_object(value: Any, field: str, allowed: set[str], label: str) -> dict[str, str]:
    row = _exact(value, {field}, label)
    if row[field] not in allowed:
        raise QualityContractError(f"{label}.{field} fuera del catálogo.")
    return {field: row[field]}


def _catalog(value: Any, allowed: set[str] | None, label: str, *, require_nonempty: bool = False) -> list[str]:
    if (
        not isinstance(value, list) or len(value) > MAX_ITEMS
        or (require_nonempty and not value)
        or not all(isinstance(item, str) for item in value)
        or len(value) != len(set(value))
    ):
        raise QualityContractError(f"{label} debe ser lista única y acotada.")
    normalized = [_identifier(item, f"{label}[]") for item in value]
    if allowed is not None and any(item not in allowed for item in normalized):
        raise QualityContractError(f"{label} contiene valor fuera del catálogo.")
    return sorted(normalized)


def _bounded_int(value: Any, label: str) -> int:
    return _bounded_int_range(
        value,
        label,
        minimum=1,
        maximum=MAX_FRESHNESS_SECONDS,
    )


def _bounded_nonnegative_int(value: Any, label: str) -> int:
    return _bounded_int_range(
        value,
        label,
        minimum=0,
        maximum=MAX_SONAR_DEBT_ITEMS,
    )


def _bounded_int_range(
    value: Any,
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise QualityContractError(f"{label} fuera de límites.")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise QualityContractError(f"{label} inválido.")
    return value


def _closed_optional(
    value: Any,
    required: set[str],
    optional: set[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QualityContractError(f"{label} contiene campos faltantes o no permitidos.")
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise QualityContractError(f"{label} contiene campos faltantes o no permitidos.")
    return value


def _exact(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise QualityContractError(f"{label} contiene campos faltantes o no permitidos.")
    return value


def _reject_sensitive(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise QualityContractError("contract debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000:
        raise QualityContractError("contract excede tamaño máximo.")
    if _SENSITIVE.search(encoded):
        raise QualityContractError("contract contiene forma sensible no permitida.")
