#!/usr/bin/env python3
"""Agrega feedback de producto sin PII y propone prioridades semanales."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
EPIC_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#[1-9]\d*$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
MARKER_NAME = "factory-product-metric"
MARKER_RE = re.compile(
    r"<!--\s*factory-product-metric\s+(\{[^}]*\})\s*-->",
    re.DOTALL,
)
RECORD_FIELDS = {
    "project", "epic", "metric", "surface", "phase",
    "period_start", "period_end", "value", "sample_size",
}
MARKER_FIELDS = {"metric", "surface", "target_improvement_pct"}
FAMILIES = {"usage", "error", "conversion", "cwv", "seo"}
PHASES = {"baseline", "post-deploy"}
DIRECTIONS = {"increase", "decrease"}
UNITS = {"ratio", "count", "ms", "score"}
MAX_INPUT_FILES = 500
MAX_INPUT_FILE_BYTES = 2_000_000
MAX_INPUT_LINE_CHARS = 100_000
MAX_RECORDS = 100_000
MAX_SAMPLE_SIZE = 1_000_000_000
MAX_MARKER_FILE_BYTES = 2_000_000
REGRESSION_THRESHOLD_PCT = 5.0

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "producto" / "metricas.json"
DATA_DIR = REPO_ROOT / "producto" / "datos"
EPIC_MARKERS_PATH = DATA_DIR / "epic-markers.json"
OUTPUT_DIR = REPO_ROOT / "artifacts"


class FeedbackValidationError(ValueError):
    pass


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise FeedbackValidationError(
            f"{field} debe ser ISO-8601 con zona horaria."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FeedbackValidationError(
            f"{field} debe ser ISO-8601 con zona horaria."
        ) from exc
    if parsed.tzinfo is None:
        raise FeedbackValidationError(f"{field} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


def _read_catalog(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedbackValidationError(
            "Catálogo de métricas ilegible o inválido."
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise FeedbackValidationError("Catálogo debe usar schema_version=1.")
    metrics = raw.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise FeedbackValidationError("Catálogo no contiene métricas.")
    return metrics


def _catalog_spec(metric: Any, spec: Any) -> dict[str, str]:
    if not isinstance(metric, str) or not SLUG_RE.fullmatch(metric):
        raise FeedbackValidationError("Identificador de métrica inválido.")
    if (
        not isinstance(spec, dict)
        or set(spec) != {"family", "unit", "direction"}
    ):
        raise FeedbackValidationError(
            f"Métrica {metric} debe declarar family, unit y direction."
        )
    family = spec["family"]
    unit = spec["unit"]
    direction = spec["direction"]
    if (
        family not in FAMILIES
        or unit not in UNITS
        or direction not in DIRECTIONS
    ):
        raise FeedbackValidationError(
            f"Contrato inválido para métrica {metric}."
        )
    return {
        "family": family,
        "unit": unit,
        "direction": direction,
    }


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, dict[str, str]]:
    metrics = _read_catalog(path)
    catalog = {
        metric: _catalog_spec(metric, spec)
        for metric, spec in metrics.items()
    }
    families = {spec["family"] for spec in catalog.values()}
    missing = FAMILIES - families
    if missing:
        raise FeedbackValidationError(
            "Catálogo no cubre familias: " + ", ".join(sorted(missing)) + "."
        )
    return catalog


def _record_schema(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != RECORD_FIELDS:
        raise FeedbackValidationError(
            f"{where}: registro debe contener exactamente los campos permitidos."
        )
    return raw


def _record_identity(
    raw: dict[str, Any],
    catalog: dict[str, dict[str, str]],
    where: str,
) -> tuple[str, str, str, str, str]:
    project = raw["project"]
    epic = raw["epic"]
    metric = raw["metric"]
    surface = raw["surface"]
    phase = raw["phase"]
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
        raise FeedbackValidationError(f"{where}: project debe usar owner/repo.")
    if not isinstance(epic, str):
        raise FeedbackValidationError(f"{where}: epic debe usar owner/repo#N.")
    epic_match = EPIC_RE.fullmatch(epic)
    if not epic_match or epic_match.group(1) != project:
        raise FeedbackValidationError(
            f"{where}: epic debe pertenecer al mismo project y usar owner/repo#N."
        )
    if not isinstance(metric, str) or metric not in catalog:
        raise FeedbackValidationError(
            f"{where}: metric no pertenece al catálogo."
        )
    if not isinstance(surface, str) or not SLUG_RE.fullmatch(surface):
        raise FeedbackValidationError(
            f"{where}: surface debe ser un slug de producto, no texto libre."
        )
    if phase not in PHASES:
        raise FeedbackValidationError(
            f"{where}: phase debe ser baseline o post-deploy."
        )
    return project, epic, metric, surface, phase


def _record_period(
    raw: dict[str, Any],
    where: str,
) -> tuple[datetime, datetime]:
    start = _timestamp(raw["period_start"], f"{where}: period_start")
    end = _timestamp(raw["period_end"], f"{where}: period_end")
    if end <= start:
        raise FeedbackValidationError(
            f"{where}: period_end debe ser posterior a period_start."
        )
    if end - start > timedelta(days=93):
        raise FeedbackValidationError(f"{where}: periodo supera 93 días.")
    return start, end


def _record_sample_size(value: Any, where: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_SAMPLE_SIZE
    ):
        raise FeedbackValidationError(
            f"{where}: sample_size debe estar entre 1 y {MAX_SAMPLE_SIZE}."
        )
    return value


def _record_value(
    value: Any,
    unit: str,
    where: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeedbackValidationError(
            f"{where}: value debe ser numérico finito."
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise FeedbackValidationError(
            f"{where}: value debe ser numérico finito."
        )
    if value < 0:
        raise FeedbackValidationError(f"{where}: value no puede ser negativo.")
    if unit == "ratio" and value > 1:
        raise FeedbackValidationError(
            f"{where}: ratio debe estar entre 0 y 1."
        )
    if unit == "count" and not isinstance(value, int):
        raise FeedbackValidationError(f"{where}: count debe ser entero.")
    return float(value)


def validate_record(
    raw: Any,
    catalog: dict[str, dict[str, str]],
    where: str,
) -> dict[str, Any]:
    source = _record_schema(raw, where)
    project, epic, metric, surface, phase = _record_identity(
        source,
        catalog,
        where,
    )
    start, end = _record_period(source, where)
    sample_size = _record_sample_size(source["sample_size"], where)
    value = _record_value(source["value"], catalog[metric]["unit"], where)
    return {
        "project": project,
        "epic": epic,
        "metric": metric,
        "surface": surface,
        "phase": phase,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "value": value,
        "sample_size": sample_size,
    }


def _telemetry_files(directory: Path, allow_empty: bool) -> list[Path]:
    if not directory.exists():
        if allow_empty:
            return []
        raise FeedbackValidationError(
            "Directorio de telemetría inexistente."
        )
    if not directory.is_dir() or directory.is_symlink():
        raise FeedbackValidationError(
            "La telemetría debe provenir del directorio canónico."
        )
    files = sorted(directory.glob("*.jsonl"))
    if len(files) > MAX_INPUT_FILES:
        raise FeedbackValidationError(
            f"Demasiados archivos de telemetría; máximo {MAX_INPUT_FILES}."
        )
    return files


def _validate_telemetry_file(path: Path) -> None:
    if path.is_symlink():
        raise FeedbackValidationError(f"{path.name}: symlink no permitido.")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FeedbackValidationError(
            f"{path.name}: no se pudo inspeccionar."
        ) from exc
    if size > MAX_INPUT_FILE_BYTES:
        raise FeedbackValidationError(
            f"{path.name}: supera {MAX_INPUT_FILE_BYTES} bytes."
        )


def _parse_record_line(
    path: Path,
    line_no: int,
    line: str,
    catalog: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    if not line.strip():
        return None
    if len(line) > MAX_INPUT_LINE_CHARS:
        raise FeedbackValidationError(
            f"{path.name}:línea {line_no}: demasiado larga."
        )
    where = f"{path.name}:línea {line_no}"
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise FeedbackValidationError(f"{where}: JSON inválido.") from exc
    return validate_record(raw, catalog, where)


def _iter_records(
    path: Path,
    catalog: dict[str, dict[str, str]],
) -> Iterator[dict[str, Any]]:
    _validate_telemetry_file(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                record = _parse_record_line(
                    path,
                    line_no,
                    line,
                    catalog,
                )
                if record is not None:
                    yield record
    except UnicodeDecodeError as exc:
        raise FeedbackValidationError(
            f"{path.name}: no es UTF-8 válido."
        ) from exc
    except OSError as exc:
        raise FeedbackValidationError(
            f"{path.name}: no se pudo abrir."
        ) from exc


def _record_identity_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["project"],
        record["epic"],
        record["metric"],
        record["surface"],
        record["phase"],
        record["period_start"],
        record["period_end"],
    )


def load_records(
    directory: Path,
    catalog: dict[str, dict[str, str]],
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in _telemetry_files(directory, allow_empty):
        for record in _iter_records(path, catalog):
            identity = _record_identity_key(record)
            if identity in seen:
                raise FeedbackValidationError(
                    f"{path.name}: agregado duplicado; "
                    "no se contabiliza dos veces."
                )
            seen.add(identity)
            records.append(record)
            if len(records) > MAX_RECORDS:
                raise FeedbackValidationError(
                    f"Se superó el máximo de {MAX_RECORDS} registros."
                )
    if not records and not allow_empty:
        raise FeedbackValidationError(
            "No se encontraron registros de telemetría."
        )
    return records


def _extract_marker_payload(body: str) -> str | None:
    intent = MARKER_NAME in body
    matches = MARKER_RE.findall(body)
    if not matches:
        if intent:
            raise FeedbackValidationError(
                "Marker factory-product-metric malformado."
            )
        return None
    if len(matches) != 1:
        raise FeedbackValidationError(
            "Debe existir un único marker factory-product-metric."
        )
    return matches[0]


def _marker_target(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeedbackValidationError(
            "target_improvement_pct debe ser numérico finito."
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise FeedbackValidationError(
            "target_improvement_pct debe ser numérico finito."
        )
    if value <= 0 or value > 1000:
        raise FeedbackValidationError(
            "target_improvement_pct debe estar en (0, 1000]."
        )
    return float(value)


def parse_epic_marker(
    body: str,
    catalog: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    if not isinstance(body, str):
        raise FeedbackValidationError(
            "El cuerpo del épico debe ser texto."
        )
    payload = _extract_marker_payload(body)
    if payload is None:
        return None
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FeedbackValidationError(
            "Marker factory-product-metric contiene JSON inválido."
        ) from exc
    if not isinstance(raw, dict) or set(raw) != MARKER_FIELDS:
        raise FeedbackValidationError(
            "Marker debe contener metric, surface y target_improvement_pct."
        )
    metric = raw["metric"]
    surface = raw["surface"]
    if not isinstance(metric, str) or metric not in catalog:
        raise FeedbackValidationError(
            "Marker usa una métrica fuera del catálogo."
        )
    if not isinstance(surface, str) or not SLUG_RE.fullmatch(surface):
        raise FeedbackValidationError("Marker usa surface inválida.")
    return {
        "metric": metric,
        "surface": surface,
        "target_improvement_pct": _marker_target(
            raw["target_improvement_pct"]
        ),
        "direction": catalog[metric]["direction"],
    }


def required_epics(records: list[dict[str, Any]]) -> list[str]:
    return sorted({record["epic"] for record in records})


def load_epic_markers(
    path: Path,
    catalog: dict[str, dict[str, str]],
    epics: list[str],
) -> dict[str, dict[str, Any]]:
    required = set(epics)
    if not required:
        return {}
    if path.is_symlink() or not path.is_file():
        raise FeedbackValidationError(
            "Falta el mapa canónico de markers de los épicos observados."
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FeedbackValidationError(
            "No se pudo inspeccionar el mapa de markers."
        ) from exc
    if size > MAX_MARKER_FILE_BYTES:
        raise FeedbackValidationError(
            "Mapa de markers demasiado grande."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedbackValidationError(
            "Mapa de markers ilegible o inválido."
        ) from exc
    if not isinstance(raw, dict) or set(raw) != required:
        raise FeedbackValidationError(
            "El mapa de markers debe contener exactamente los épicos observados."
        )

    result: dict[str, dict[str, Any]] = {}
    for epic in sorted(required):
        body = raw.get(epic)
        if not isinstance(body, str) or len(body) > 200_000:
            raise FeedbackValidationError(
                f"{epic}: body del épico inválido."
            )
        marker = parse_epic_marker(body, catalog)
        if marker is None:
            raise FeedbackValidationError(
                f"{epic}: falta marker factory-product-metric."
            )
        result[epic] = marker
    return result


def _period(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _validate_rows_in_phase(
    phase_name: str,
    rows: list[dict[str, Any]],
    family: str,
) -> None:
    ordered = sorted(rows, key=lambda row: row["period_start"])
    previous_end: datetime | None = None
    for row in ordered:
        start = _period(row["period_start"])
        end = _period(row["period_end"])
        if previous_end is not None and start < previous_end:
            raise FeedbackValidationError(
                f"Ventanas {phase_name} solapadas; "
                "la muestra se contaría dos veces."
            )
        previous_end = end
    if family == "cwv" and len(rows) > 1:
        raise FeedbackValidationError(
            "CWV p75 requiere un único agregado por fase; "
            "no se promedian percentiles."
        )


def _validate_phase_windows(
    baseline_rows: list[dict[str, Any]],
    post_rows: list[dict[str, Any]],
    family: str,
) -> None:
    _validate_rows_in_phase("baseline", baseline_rows, family)
    _validate_rows_in_phase("post-deploy", post_rows, family)
    if not baseline_rows or not post_rows:
        return
    baseline_end = max(
        _period(row["period_end"]) for row in baseline_rows
    )
    post_start = min(
        _period(row["period_start"]) for row in post_rows
    )
    if baseline_end > post_start:
        raise FeedbackValidationError(
            "Baseline debe terminar antes de comenzar post-deploy."
        )


def _weighted_average(
    rows: list[dict[str, Any]],
    unit: str,
) -> tuple[float, int]:
    total_samples = sum(row["sample_size"] for row in rows)
    if total_samples <= 0:
        raise FeedbackValidationError(
            "Grupo sin muestra; no se puede promediar."
        )
    if unit == "count":
        total_days = sum(
            (
                _period(row["period_end"])
                - _period(row["period_start"])
            ).total_seconds() / 86_400
            for row in rows
        )
        if total_days <= 0:
            raise FeedbackValidationError(
                "Métrica count requiere duración positiva "
                "para calcular tasa diaria."
            )
        value = sum(row["value"] for row in rows) / total_days
    else:
        value = (
            sum(
                row["value"] * row["sample_size"]
                for row in rows
            )
            / total_samples
        )
    return round(value, 6), total_samples


def _group_records(
    records: list[dict[str, Any]],
) -> dict[
    tuple[str, str, str, str],
    dict[str, list[dict[str, Any]]],
]:
    groups: dict[
        tuple[str, str, str, str],
        dict[str, list[dict[str, Any]]],
    ] = defaultdict(lambda: {"baseline": [], "post-deploy": []})
    for record in records:
        key = (
            record["project"],
            record["epic"],
            record["metric"],
            record["surface"],
        )
        groups[key][record["phase"]].append(record)
    return groups


def _validated_marker(
    epic: str,
    metric: str,
    surface: str,
    markers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    marker = markers.get(epic)
    if marker is None:
        raise FeedbackValidationError(
            f"{epic}: falta marker de producto."
        )
    if marker["metric"] != metric or marker["surface"] != surface:
        raise FeedbackValidationError(
            f"{epic}: marker metric/surface no coincide con la telemetría."
        )
    return marker


def _base_result(
    project: str,
    epic: str,
    metric: str,
    surface: str,
    spec: dict[str, str],
    marker: dict[str, Any],
    baseline_rows: list[dict[str, Any]],
    post_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "project": project,
        "epic": epic,
        "metric": metric,
        "family": spec["family"],
        "surface": surface,
        "unit": spec["unit"],
        "direction": spec["direction"],
        "target_improvement_pct": marker["target_improvement_pct"],
        "status": "insufficient-data",
        "baseline": None,
        "post_deploy": None,
        "delta_pct": None,
        "improvement_pct": None,
        "baseline_samples": sum(
            item["sample_size"] for item in baseline_rows
        ),
        "post_deploy_samples": sum(
            item["sample_size"] for item in post_rows
        ),
    }


def _populate_phase_values(
    row: dict[str, Any],
    baseline_rows: list[dict[str, Any]],
    post_rows: list[dict[str, Any]],
    unit: str,
) -> None:
    if baseline_rows:
        row["baseline"], row["baseline_samples"] = _weighted_average(
            baseline_rows,
            unit,
        )
    if post_rows:
        row["post_deploy"], row["post_deploy_samples"] = _weighted_average(
            post_rows,
            unit,
        )


def _comparison_status(
    row: dict[str, Any],
    direction: str,
    min_sample_size: int,
) -> float | None:
    enough = (
        row["baseline_samples"] >= min_sample_size
        and row["post_deploy_samples"] >= min_sample_size
    )
    if not enough:
        return None
    if row["baseline"] == 0:
        row["status"] = "non-comparable-zero-baseline"
        return None

    delta_pct = round(
        ((row["post_deploy"] - row["baseline"]) / row["baseline"]) * 100,
        2,
    )
    improvement_pct = (
        delta_pct if direction == "increase" else -delta_pct
    )
    row["delta_pct"] = delta_pct
    row["improvement_pct"] = round(improvement_pct, 2)
    if improvement_pct <= -REGRESSION_THRESHOLD_PCT:
        row["status"] = "regressed"
    elif improvement_pct >= REGRESSION_THRESHOLD_PCT:
        row["status"] = "improved"
    else:
        row["status"] = "stable"
    return improvement_pct


def _proposal(
    row: dict[str, Any],
    improvement_pct: float | None,
) -> dict[str, Any] | None:
    if row["status"] != "regressed" or improvement_pct is None:
        return None
    regression_pct = round(-improvement_pct, 2)
    evidence_factor = min(
        4.0,
        round(math.log10(row["post_deploy_samples"] + 1), 4),
    )
    return {
        "project": row["project"],
        "epic": row["epic"],
        "metric": row["metric"],
        "family": row["family"],
        "surface": row["surface"],
        "baseline": row["baseline"],
        "post_deploy": row["post_deploy"],
        "regression_pct": regression_pct,
        "post_deploy_samples": row["post_deploy_samples"],
        "target_improvement_pct": row["target_improvement_pct"],
        "impact_score": round(regression_pct * evidence_factor, 2),
        "suggested_title": (
            f"[AUTO] revisar {row['metric']} en {row['surface']}"
        ),
    }


def _aggregate_group(
    key: tuple[str, str, str, str],
    phases: dict[str, list[dict[str, Any]]],
    catalog: dict[str, dict[str, str]],
    markers: dict[str, dict[str, Any]],
    min_sample_size: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    project, epic, metric, surface = key
    baseline_rows = phases["baseline"]
    post_rows = phases["post-deploy"]
    spec = catalog[metric]
    marker = _validated_marker(epic, metric, surface, markers)
    _validate_phase_windows(
        baseline_rows,
        post_rows,
        spec["family"],
    )
    row = _base_result(
        project,
        epic,
        metric,
        surface,
        spec,
        marker,
        baseline_rows,
        post_rows,
    )
    _populate_phase_values(
        row,
        baseline_rows,
        post_rows,
        spec["unit"],
    )
    improvement_pct = _comparison_status(
        row,
        spec["direction"],
        min_sample_size,
    )
    return row, _proposal(row, improvement_pct)


def aggregate(
    records: list[dict[str, Any]],
    catalog: dict[str, dict[str, str]],
    min_sample_size: int = 100,
    epic_markers: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if (
        isinstance(min_sample_size, bool)
        or not isinstance(min_sample_size, int)
        or min_sample_size < 1
    ):
        raise FeedbackValidationError(
            "min_sample_size debe ser entero >= 1."
        )
    markers = epic_markers or {}
    if records and not markers:
        raise FeedbackValidationError(
            "La telemetría requiere markers de épico para validar el objetivo."
        )

    results: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    for key, phases in sorted(_group_records(records).items()):
        row, proposal = _aggregate_group(
            key,
            phases,
            catalog,
            markers,
            min_sample_size,
        )
        results.append(row)
        if proposal is not None:
            proposals.append(proposal)

    proposals.sort(
        key=lambda item: (
            -item["impact_score"],
            -item["post_deploy_samples"],
            item["project"],
            item["epic"],
            item["metric"],
            item["surface"],
        )
    )
    return {
        "schema_version": 1,
        "records": len(records),
        "min_sample_size": min_sample_size,
        "regression_threshold_pct": REGRESSION_THRESHOLD_PCT,
        "results": results,
        "proposals": proposals,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Feedback semanal de producto",
        "",
        f"- Registros agregados: **{report['records']}**",
        f"- Muestra mínima por fase: **{report['min_sample_size']}**",
        f"- Umbral de regresión: **{report['regression_threshold_pct']:.1f}%**",
        "",
    ]
    if not report["results"]:
        lines += [
            "No hay telemetría suficiente todavía. No se proponen Issues.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        "## Resultados por épico",
        "",
        "| Épico | Familia | Métrica | Surface | Objetivo | Estado | "
        "Baseline | Post | Δ |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in report["results"]:
        delta = (
            "—"
            if row["delta_pct"] is None
            else f"{row['delta_pct']:.2f}%"
        )
        baseline = "—" if row["baseline"] is None else row["baseline"]
        post = (
            "—"
            if row["post_deploy"] is None
            else row["post_deploy"]
        )
        lines.append(
            f"| {row['epic']} | {row['family']} | {row['metric']} | "
            f"{row['surface']} | {row['target_improvement_pct']:.2f}% | "
            f"{row['status']} | {baseline} | {post} | {delta} |"
        )

    lines += ["", "## Propuestas priorizadas", ""]
    if not report["proposals"]:
        lines += [
            "Sin regresiones medibles que justifiquen "
            "una propuesta automática.",
            "",
        ]
    else:
        for index, item in enumerate(report["proposals"], 1):
            lines += [
                f"{index}. **{item['suggested_title']}**",
                f"   - Épico: {item['epic']}",
                "   - Objetivo declarado: "
                f"{item['target_improvement_pct']:.2f}%",
                "   - Regresión: "
                f"{item['regression_pct']:.2f}% · "
                f"muestra post: {item['post_deploy_samples']}",
                "   - Impact score auditable: "
                f"{item['impact_score']:.2f}",
            ]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--min-sample-size", type=int, default=100)
    parser.add_argument("--list-epics", action="store_true")
    args = parser.parse_args()

    try:
        catalog = load_catalog()
        records = load_records(DATA_DIR, catalog, args.allow_empty)
        epics = required_epics(records)
        if args.list_epics:
            print(json.dumps(epics, ensure_ascii=False))
            return 0
        markers = load_epic_markers(
            EPIC_MARKERS_PATH,
            catalog,
            epics,
        )
        report = aggregate(
            records,
            catalog,
            args.min_sample_size,
            markers,
        )
    except FeedbackValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "reporte-producto.json").write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (OUTPUT_DIR / "reporte-producto.md").write_text(
            render_markdown(report) + "\n",
            encoding="utf-8",
        )
    except OSError:
        print(
            "ERROR: no se pudo escribir la evidencia semanal.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
