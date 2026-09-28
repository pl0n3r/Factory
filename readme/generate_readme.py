"""Motor puro y determinista para bloques derivados del README Contract v1."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from intelligence.derived_views import (
    DerivedViewError,
    markdown_cell,
    replace_delimited_block,
)
from readme.progress_readiness import ProgressReadinessError, canonical_payload


class ReadmeEngineError(DerivedViewError):
    """Input incompatible, sensible o no verificable para README Contract v1."""


SENSITIVE_KEYS = {
    "secret", "secrets", "token", "password", "passwd", "private_key",
    "api_key", "apikey", "authorization", "cookie", "cookies",
}
STATUS_FIELDS = {"ci", "health", "smoke", "quality"}
FIELD_LABELS = {
    "main_sha": "main SHA",
    "version": "versión",
    "ci": "CI",
    "release": "release",
    "health": "health",
    "smoke": "smoke/observer",
    "quality": "quality/security",
    "active_issue": "Issue activo",
    "active_pr": "PR activo",
    "last_release": "último release",
}
ENTRY_KEYS = {"value", "state", "evidence"}


def validate_project_metadata(
    contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> None:
    """Valida metadata estable sin permitir estado operativo ni claves arbitrarias."""
    if not isinstance(metadata, Mapping):
        raise ReadmeEngineError("project metadata debe ser objeto.")
    required = tuple(contract["project_metadata"]["required"])
    if set(metadata) != set(required):
        raise ReadmeEngineError("project metadata no coincide con el contrato requerido.")
    _reject_sensitive(metadata)
    for key in required:
        value = metadata[key]
        if not isinstance(value, str) or not value.strip():
            raise ReadmeEngineError(f"project metadata inválida: {key}.")
    if metadata["phase"] not in contract["project_metadata"]["phase_values"]:
        raise ReadmeEngineError("phase no admitida por el contrato.")


def normalize_operational_sources(
    contract: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    """Normaliza evidencia explícita y falla cerrado ante campos no declarados."""
    if not isinstance(sources, Mapping):
        raise ReadmeEngineError("operational sources debe ser objeto.")
    _reject_sensitive(sources)
    status_contract = contract["derived_blocks"]["status"]
    allowed_fields = tuple(status_contract["fields"])
    unknown = set(sources) - set(allowed_fields)
    if unknown:
        raise ReadmeEngineError("operational sources contiene campos no permitidos.")

    allowed_states = set(status_contract["allowed_states"])
    terminal_evidence = set(status_contract.get("terminal_states_require_evidence", ()))
    normalized: dict[str, dict[str, str]] = {}
    for field in allowed_fields:
        raw = sources.get(field)
        if raw is None:
            normalized[field] = {"value": "UNKNOWN", "state": "UNKNOWN", "evidence": ""}
            continue
        entry = _normalize_entry(raw)
        state = entry["state"]
        if state and state not in allowed_states:
            raise ReadmeEngineError(f"estado no admitido para {field}.")
        if state in terminal_evidence and not entry["evidence"]:
            raise ReadmeEngineError(f"{state} requiere evidencia para {field}.")
        if field in STATUS_FIELDS:
            if entry["value"] and entry["value"] != entry["state"]:
                raise ReadmeEngineError(f"{field} no admite value distinto del estado.")
            effective = state or "UNKNOWN"
        else:
            if state and state not in {"UNKNOWN", "PENDING"}:
                raise ReadmeEngineError(f"{field} usa value, no estados terminales.")
            effective = entry["value"] or state or "UNKNOWN"
        normalized[field] = {
            "value": effective,
            "state": state or ("UNKNOWN" if effective == "UNKNOWN" else ""),
            "evidence": entry["evidence"],
        }
    return normalized


def render_status_block(
    contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> str:
    """Renderiza el cockpit canónico desde inputs locales explícitos."""
    validate_project_metadata(contract, metadata)
    normalized = normalize_operational_sources(contract, sources)
    rows = ["| Señal | Estado |", "| --- | --- |"]
    for field in contract["derived_blocks"]["status"]["fields"]:
        label = FIELD_LABELS.get(field, field)
        rows.append(
            f"| {markdown_cell(label)} | {markdown_cell(normalized[field]['value'])} |"
        )
    return "\n".join(rows)


def normalize_progress_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Valida el snapshot canónico de #294 sin recalcular métricas."""
    if not isinstance(snapshot, Mapping):
        raise ReadmeEngineError("progress snapshot debe ser objeto.")
    _reject_sensitive(snapshot)
    try:
        return json.loads(canonical_payload(snapshot))
    except (ProgressReadinessError, TypeError, ValueError) as exc:
        raise ReadmeEngineError(
            "progress snapshot incompatible con contrato canónico."
        ) from exc


def render_progress_readiness_block(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
) -> str:
    """Renderiza únicamente valores ya calculados por Progress + Readiness."""
    block_contract = contract["derived_blocks"]["progress_readiness"]
    if block_contract.get("consumers_must_not_recalculate") is not True:
        raise ReadmeEngineError(
            "progress_readiness debe prohibir recálculo consumidor."
        )

    if snapshot is None:
        return "\n".join(
            [
                "| Señal | Estado |",
                "| --- | --- |",
                "| Target | UNKNOWN |",
                "| Progress | UNKNOWN |",
                "| Readiness | UNKNOWN |",
                "| Evidence freshness | UNKNOWN |",
                "| Critical blockers | UNKNOWN |",
                "| Trend | UNKNOWN |",
                "",
                "| Dimensión | Progress | Readiness |",
                "| --- | --- | --- |",
                "| UNKNOWN | UNKNOWN | UNKNOWN |",
            ]
        )

    normalized = normalize_progress_snapshot(snapshot)
    target = normalized["target"]
    progress = normalized["progress"]
    readiness = normalized["readiness"]
    freshness = normalized["evidence_freshness"]
    critical = normalized["critical_blockers"]
    trend = normalized["trend"]

    target_text = (
        f"{target['label']} · {target['id']} · "
        f"v{target['version']} · {target['scope']}"
    )
    progress_text = _metric_value(progress)
    readiness_text = f"{_metric_value(readiness)} · {readiness['status']}"
    blocker_text = "0"
    if critical:
        blocker_text = f"{len(critical)} · " + "; ".join(
            f"{item['label']} [{item['state']}]" for item in critical
        )

    rows = [
        "| Señal | Estado |",
        "| --- | --- |",
        f"| Target | {markdown_cell(target_text)} |",
        f"| Progress | {markdown_cell(progress_text)} |",
        f"| Readiness | {markdown_cell(readiness_text)} |",
        f"| Evidence freshness | {markdown_cell(freshness)} |",
        f"| Critical blockers | {markdown_cell(blocker_text)} |",
        f"| Trend | {markdown_cell(_trend_value(trend))} |",
        "",
        "| Dimensión | Progress | Readiness |",
        "| --- | --- | --- |",
    ]
    for dimension in normalized["dimensions"]:
        rows.append(
            "| "
            + " | ".join(
                (
                    markdown_cell(dimension["label"]),
                    markdown_cell(_metric_value(dimension["progress"])),
                    markdown_cell(_metric_value(dimension["readiness"])),
                )
            )
            + " |"
        )
    return "\n".join(rows)


def _metric_value(metric: Mapping[str, Any]) -> str:
    percent = metric.get("percent")
    if percent is None:
        return "N/A" if metric.get("status") == "NOT_APPLICABLE" else "UNKNOWN"
    return f"{percent}%"


def _trend_value(trend: Mapping[str, Any]) -> str:
    kind = trend["kind"]
    if kind != "TREND":
        return kind
    return (
        "TREND · progress "
        + _basis_point_delta(trend["progress_delta_basis_points"])
        + " · readiness "
        + _basis_point_delta(trend["readiness_delta_basis_points"])
    )


def _basis_point_delta(value: Any) -> str:
    if not isinstance(value, int):
        return "UNKNOWN"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value / 100:.2f} pts"


def generate_readme(
    readme_text: str,
    contract: Mapping[str, Any],
    metadata: Mapping[str, Any],
    sources: Mapping[str, Any],
    progress_snapshot: Mapping[str, Any] | None = None,
) -> str:
    """Genera solo bloques derivados declarados y preserva el resto del README."""
    if not isinstance(readme_text, str):
        raise ReadmeEngineError("README debe ser texto.")
    status = contract["derived_blocks"]["status"]
    block = render_status_block(contract, metadata, sources)
    generated = replace_delimited_block(
        readme_text,
        start_marker=status["start_marker"],
        end_marker=status["end_marker"],
        content=block,
    )

    progress_contract = contract["derived_blocks"].get("progress_readiness")
    if progress_contract is None:
        if progress_snapshot is not None:
            raise ReadmeEngineError("contrato progress_readiness ausente.")
        return generated

    start = progress_contract["start_marker"]
    end = progress_contract["end_marker"]
    has_start = start in generated
    has_end = end in generated
    if has_start != has_end:
        raise ReadmeEngineError("markers progress_readiness incompletos.")
    if not has_start and progress_snapshot is None:
        return generated

    progress_block = render_progress_readiness_block(
        contract,
        progress_snapshot,
    )
    return replace_delimited_block(
        generated,
        start_marker=start,
        end_marker=end,
        content=progress_block,
    )


def _normalize_entry(raw: Any) -> dict[str, str]:
    if isinstance(raw, str):
        text = _safe_text(raw)
        return {"value": text, "state": "", "evidence": ""}
    if not isinstance(raw, Mapping) or not set(raw) <= ENTRY_KEYS:
        raise ReadmeEngineError("entrada operacional inválida.")
    _reject_sensitive(raw)
    value = _safe_text(raw.get("value", ""), allow_empty=True)
    state = _safe_text(raw.get("state", ""), allow_empty=True).upper()
    evidence = _safe_text(raw.get("evidence", ""), allow_empty=True)
    return {"value": value, "state": state, "evidence": evidence}


def _safe_text(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ReadmeEngineError("valor operacional debe ser texto.")
    text = " ".join(value.split())
    if not text and not allow_empty:
        raise ReadmeEngineError("valor operacional vacío.")
    if len(text) > 240:
        raise ReadmeEngineError("valor operacional excede 240 caracteres.")
    return text


def _reject_sensitive(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ReadmeEngineError("claves no string.")
            if key.strip().lower() in SENSITIVE_KEYS:
                raise ReadmeEngineError("input contiene campos sensibles.")
            _reject_sensitive(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_sensitive(item)
