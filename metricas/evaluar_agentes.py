#!/usr/bin/env python3
"""Valida y resume evidencia de agentes/modelos/prompts por tipo de tarea."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterator

REQUIRED = {
    "task_id", "task_type", "agent", "model", "prompt_id", "roles",
    "success", "merged_first_try", "commits", "review_rounds",
    "rework_commits", "incidents_after", "completed_at",
}
OPTIONAL = {"tokens_input", "tokens_output", "ci_minutes", "agent_minutes"}
ALLOWED = REQUIRED | OPTIONAL
IDENTITY_FIELDS = ("task_id", "task_type", "agent", "model", "prompt_id", "completed_at")
SLUG_FIELDS = ("task_type", "agent", "model", "prompt_id")
BOOLEAN_FIELDS = ("success", "merged_first_try")
INTEGER_FIELDS = ("commits", "review_rounds", "rework_commits", "incidents_after")

MAX_INPUT_FILES = 500
MAX_INPUT_FILE_BYTES = 2_000_000
MAX_INPUT_LINE_CHARS = 100_000
MAX_RECORDS = 100_000
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "metricas" / "datos"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts"

SLUG_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
TASK_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?#[1-9]\d*$")
MONTH_RE = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")


class ValidationError(ValueError):
    pass


def _text(record: dict[str, Any], field: str, where: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValidationError(
            f"{where}: campo {field} debe ser texto no vacío (máx. 160)."
        )
    return value.strip()


def _integer(
    record: dict[str, Any],
    field: str,
    where: str,
    optional: bool = False,
) -> int | None:
    value = record.get(field)
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{where}: campo {field} debe ser entero >= 0.")
    return value


def _validate_schema(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError(f"{where}: cada registro debe ser un objeto JSON.")
    missing = REQUIRED - raw.keys()
    unknown = raw.keys() - ALLOWED
    if missing:
        raise ValidationError(
            f"{where}: faltan campos: {', '.join(sorted(missing))}."
        )
    if unknown:
        raise ValidationError(
            f"{where}: campos no permitidos: {', '.join(sorted(unknown))}."
        )
    return raw


def _validate_identities(raw: dict[str, Any], where: str) -> dict[str, str]:
    values = {field: _text(raw, field, where) for field in IDENTITY_FIELDS}
    if not TASK_RE.fullmatch(values["task_id"]):
        raise ValidationError(
            f"{where}: task_id debe usar repo#N u owner/repo#N."
        )
    invalid = [
        field
        for field in SLUG_FIELDS
        if not SLUG_RE.fullmatch(values[field])
    ]
    if invalid:
        raise ValidationError(
            f"{where}: campo {invalid[0]} debe ser un identificador, no texto libre."
        )
    return values


def _validate_roles(raw: dict[str, Any], where: str) -> list[str]:
    roles = raw["roles"]
    if not isinstance(roles, list) or not roles or len(roles) > 8:
        raise ValidationError(
            f"{where}: roles debe contener entre 1 y 8 textos."
        )
    cleaned: set[str] = set()
    for role in roles:
        if not isinstance(role, str) or not role.strip() or len(role) > 80:
            raise ValidationError(
                f"{where}: cada rol debe ser texto no vacío (máx. 80)."
            )
        normalized = role.strip()
        if not SLUG_RE.fullmatch(normalized):
            raise ValidationError(
                f"{where}: cada rol debe ser un identificador, no texto libre."
            )
        cleaned.add(normalized)
    return sorted(cleaned)


def _validate_booleans(
    raw: dict[str, Any],
    record: dict[str, Any],
    where: str,
) -> None:
    for field in BOOLEAN_FIELDS:
        value = raw[field]
        if not isinstance(value, bool):
            raise ValidationError(f"{where}: campo {field} debe ser booleano.")
        record[field] = value


def _validate_integers(
    raw: dict[str, Any],
    record: dict[str, Any],
    where: str,
) -> None:
    for field in INTEGER_FIELDS:
        record[field] = _integer(raw, field, where)
    if record["review_rounds"] > 3:
        raise ValidationError(f"{where}: review_rounds no puede superar 3.")
    for field in OPTIONAL:
        record[field] = _integer(raw, field, where, optional=True)


def _validate_timestamp(value: str, where: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(
            f"{where}: completed_at debe ser ISO-8601."
        ) from exc
    if parsed.tzinfo is None:
        raise ValidationError(
            f"{where}: completed_at debe incluir zona horaria."
        )


def validate_record(raw: Any, where: str) -> dict[str, Any]:
    source = _validate_schema(raw, where)
    record: dict[str, Any] = _validate_identities(source, where)
    record["roles"] = _validate_roles(source, where)
    _validate_booleans(source, record, where)
    _validate_integers(source, record, where)
    _validate_timestamp(record["completed_at"], where)
    return record


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    if not MONTH_RE.fullmatch(month):
        raise ValidationError("month debe usar YYYY-MM.")
    year, month_number = (int(part) for part in month.split("-"))
    try:
        start = datetime(year, month_number, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month_number == 12
            else datetime(year, month_number + 1, 1, tzinfo=timezone.utc)
        )
    except ValueError as exc:
        raise ValidationError(
            "month está fuera del rango de fechas soportado."
        ) from exc
    return start, end


def _expand_input(item: Path, allow_empty: bool) -> list[Path]:
    if item.is_symlink():
        raise ValidationError(
            f"{item.name}: enlaces simbólicos no están permitidos."
        )
    if item.is_dir():
        return sorted(item.rglob("*.jsonl"))
    if item.is_file():
        return [item]
    if allow_empty:
        return []
    raise ValidationError(f"Entrada inexistente: {item.name}.")


def _collect_files(inputs: list[Path], allow_empty: bool) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        files.extend(_expand_input(item, allow_empty))
    unique = sorted(set(files))
    if len(unique) > MAX_INPUT_FILES:
        raise ValidationError(
            f"Demasiados archivos de entrada; máximo {MAX_INPUT_FILES}."
        )
    return unique


def _validate_input_file(path: Path) -> None:
    if path.suffix != ".jsonl":
        raise ValidationError(
            f"{path.name}: extensión no permitida; se requiere .jsonl."
        )
    if path.is_symlink():
        raise ValidationError(
            f"{path.name}: enlaces simbólicos no están permitidos."
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValidationError(
            f"{path.name}: no se pudo inspeccionar el archivo."
        ) from exc
    if size > MAX_INPUT_FILE_BYTES:
        raise ValidationError(
            f"{path.name}: archivo supera el máximo de "
            f"{MAX_INPUT_FILE_BYTES} bytes."
        )


def _parse_line(path: Path, line_no: int, line: str) -> dict[str, Any] | None:
    if len(line) > MAX_INPUT_LINE_CHARS:
        raise ValidationError(
            f"{path.name}:línea {line_no}: supera el máximo permitido."
        )
    if not line.strip():
        return None
    where = f"{path.name}:línea {line_no}"
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{where}: JSON inválido.") from exc
    return validate_record(raw, where)


def _iter_file_records(path: Path) -> Iterator[dict[str, Any]]:
    _validate_input_file(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                record = _parse_line(path, line_no, line)
                if record is not None:
                    yield record
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"{path.name}: el archivo no es UTF-8 válido."
        ) from exc
    except OSError as exc:
        raise ValidationError(
            f"{path.name}: no se pudo abrir el archivo."
        ) from exc


def _within_bounds(
    record: dict[str, Any],
    bounds: tuple[datetime, datetime] | None,
) -> bool:
    if bounds is None:
        return True
    completed = datetime.fromisoformat(
        record["completed_at"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    return bounds[0] <= completed < bounds[1]


def load_records(
    inputs: list[Path],
    allow_empty: bool = False,
    month: str | None = None,
) -> list[dict[str, Any]]:
    bounds = _month_bounds(month) if month else None
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in _collect_files(inputs, allow_empty):
        for record in _iter_file_records(path):
            task_id = record["task_id"]
            if task_id in seen:
                raise ValidationError(
                    f"{path.name}: task_id duplicado; no se contabiliza dos veces."
                )
            seen.add(task_id)
            if not _within_bounds(record, bounds):
                continue
            records.append(record)
            if len(records) > MAX_RECORDS:
                raise ValidationError(
                    f"Se superó el máximo de {MAX_RECORDS} registros por evaluación."
                )

    if not records and not allow_empty:
        raise ValidationError("No se encontraron registros válidos.")
    return records


def _avg(values: list[int | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return round(mean(usable), 2) if usable else None


def _core_quality_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -row["success_rate"],
        row["incidents_per_task"],
        -row["first_merge_rate"],
        row["rework_commits_avg"],
        row["review_rounds_avg"],
    )


def _configuration_key(record: dict[str, Any]) -> tuple[str, ...]:
    return (
        record["agent"],
        record["model"],
        record["prompt_id"],
        ",".join(record["roles"]),
    )


def _token_total(item: dict[str, Any]) -> int | None:
    tokens_input = item["tokens_input"]
    tokens_output = item["tokens_output"]
    if tokens_input is None or tokens_output is None:
        return None
    return tokens_input + tokens_output


def _summarize_configuration(
    key: tuple[str, ...],
    items: list[dict[str, Any]],
    min_samples: int,
) -> dict[str, Any]:
    sample_count = len(items)
    if sample_count < 1:
        raise ValidationError(
            "Grupo de configuración vacío; no se puede calcular el ranking."
        )
    token_totals = [_token_total(item) for item in items]
    token_complete_samples = sum(
        value is not None for value in token_totals
    )
    tokens_avg = (
        _avg(token_totals)
        if token_complete_samples == sample_count
        else None
    )
    eligible = sample_count >= min_samples
    return {
        "configuration": {
            "agent": key[0],
            "model": key[1],
            "prompt_id": key[2],
            "roles": key[3].split(","),
        },
        "samples": sample_count,
        "sample_status": "eligible" if eligible else "insufficient_data",
        "success_rate": round(
            sum(item["success"] for item in items) / sample_count,
            4,
        ),
        "first_merge_rate": round(
            sum(item["merged_first_try"] for item in items) / sample_count,
            4,
        ),
        "incidents_per_task": round(
            sum(item["incidents_after"] for item in items) / sample_count,
            4,
        ),
        "commits_avg": _avg([item["commits"] for item in items]),
        "review_rounds_avg": _avg(
            [item["review_rounds"] for item in items]
        ),
        "rework_commits_avg": _avg(
            [item["rework_commits"] for item in items]
        ),
        "tokens_avg": tokens_avg,
        "tokens_complete_samples": token_complete_samples,
        "ci_minutes_avg": _avg([item["ci_minutes"] for item in items]),
        "agent_minutes_avg": _avg(
            [item["agent_minutes"] for item in items]
        ),
        "eligible": eligible,
        "rank": None,
    }


def _rank_group(
    group: list[dict[str, Any]],
    position: int,
) -> list[dict[str, Any]]:
    all_tokens_complete = all(
        row["tokens_avg"] is not None for row in group
    )
    if not all_tokens_complete:
        group.sort(
            key=lambda row: json.dumps(
                row["configuration"],
                sort_keys=True,
            )
        )
        for row in group:
            row["rank"] = position
        return group

    group.sort(
        key=lambda row: (
            row["tokens_avg"],
            json.dumps(row["configuration"], sort_keys=True),
        )
    )
    previous_tokens: int | float | None = None
    current_rank = position
    for offset, row in enumerate(group):
        tokens = row["tokens_avg"]
        if previous_tokens is None or tokens != previous_tokens:
            current_rank = position + offset
        row["rank"] = current_rank
        previous_tokens = tokens
    return group


def _rank_rows(
    rows: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[list[dict[str, Any]]],
]:
    eligible = [row for row in rows if row["eligible"]]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[_core_quality_key(row)].append(row)

    ordered_eligible: list[dict[str, Any]] = []
    ordered_groups: list[list[dict[str, Any]]] = []
    position = 1
    for core_key in sorted(groups):
        ranked = _rank_group(groups[core_key], position)
        ordered_groups.append(ranked)
        ordered_eligible.extend(ranked)
        position += len(ranked)

    ineligible = [row for row in rows if not row["eligible"]]
    ineligible.sort(
        key=lambda row: json.dumps(row["configuration"], sort_keys=True)
    )
    return ordered_eligible + ineligible, eligible, ordered_groups


def _tokens_are_comparable(
    first: Any,
    second: Any,
) -> bool:
    numeric = (int, float)
    return (
        isinstance(first, numeric)
        and not isinstance(first, bool)
        and isinstance(second, numeric)
        and not isinstance(second, bool)
    )


def _recommend(
    eligible: list[dict[str, Any]],
    ordered_groups: list[list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    if len(eligible) < 2 or not ordered_groups:
        return None, "insufficient-comparison"

    top_group = ordered_groups[0]
    if len(top_group) == 1:
        return top_group[0]["configuration"], "data-backed"

    first_tokens = top_group[0]["tokens_avg"]
    second_tokens = top_group[1]["tokens_avg"]
    if (
        _tokens_are_comparable(first_tokens, second_tokens)
        and first_tokens < second_tokens
    ):
        return top_group[0]["configuration"], "data-backed"
    return None, "tie-or-incomplete-cost"


def _task_type_report(
    configs: dict[tuple[str, ...], list[dict[str, Any]]],
    min_samples: int,
) -> dict[str, Any]:
    rows = [
        _summarize_configuration(key, items, min_samples)
        for key, items in configs.items()
    ]
    ordered_rows, eligible, ordered_groups = _rank_rows(rows)
    recommendation, status = _recommend(eligible, ordered_groups)
    return {
        "configurations": ordered_rows,
        "recommendation": recommendation,
        "recommendation_status": status,
    }


def aggregate(
    records: list[dict[str, Any]],
    min_samples: int = 3,
) -> dict[str, Any]:
    if min_samples < 1:
        raise ValidationError("min_samples debe ser >= 1.")

    grouped: dict[
        str,
        dict[tuple[str, ...], list[dict[str, Any]]],
    ] = defaultdict(lambda: defaultdict(list))
    for record in records:
        grouped[record["task_type"]][_configuration_key(record)].append(record)

    task_types = {
        task_type: _task_type_report(configs, min_samples)
        for task_type, configs in sorted(grouped.items())
    }
    return {
        "schema_version": 1,
        "min_samples": min_samples,
        "records": len(records),
        "period": "all",
        "task_types": task_types,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Evaluación de agentes, modelos y prompts",
        "",
        f"- Registros válidos: **{report['records']}**",
        f"- Muestra mínima por configuración: **{report['min_samples']}**",
        f"- Periodo UTC: **{report.get('period', 'all')}**",
        "",
    ]
    if not report["task_types"]:
        lines += [
            "No hay datos suficientes todavía. No se emite recomendación.",
            "",
        ]
        return "\n".join(lines)

    for task_type, data in report["task_types"].items():
        lines += [
            f"## {task_type}",
            "",
            "| Rank | Configuración | N | Éxito | 1ª integración | "
            "Incidentes/tarea | Retrabajo | Rondas | Tokens |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in data["configurations"]:
            cfg = row["configuration"]
            name = (
                f"{cfg['agent']} / {cfg['model']} / {cfg['prompt_id']} / "
                f"{','.join(cfg['roles'])}"
            )
            rank = row["rank"] if row["rank"] is not None else "—"
            tokens = (
                row["tokens_avg"]
                if row["tokens_avg"] is not None
                else "—"
            )
            lines.append(
                f"| {rank} | {name} | {row['samples']} | "
                f"{row['success_rate']:.1%} | "
                f"{row['first_merge_rate']:.1%} | "
                f"{row['incidents_per_task']:.2f} | "
                f"{row['rework_commits_avg']:.2f} | "
                f"{row['review_rounds_avg']:.2f} | {tokens} |"
            )
        recommendation = data["recommendation"]
        if recommendation:
            lines += [
                "",
                "**Recomendación basada en datos:** "
                f"{recommendation['agent']} / {recommendation['model']} / "
                f"{recommendation['prompt_id']}.",
            ]
        else:
            lines += [
                "",
                "**Sin recomendación:** faltan al menos dos configuraciones "
                "con muestra suficiente.",
            ]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument(
        "--month",
        help="Mes UTC YYYY-MM; omitir para histórico acumulado.",
    )
    args = parser.parse_args()

    try:
        report = aggregate(
            load_records(
                [DEFAULT_DATA_DIR],
                args.allow_empty,
                args.month,
            ),
            args.min_samples,
        )
        report["period"] = args.month or "all"
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (DEFAULT_OUTPUT_DIR / "recomendaciones.json").write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (DEFAULT_OUTPUT_DIR / "dashboard.md").write_text(
            render_markdown(report) + "\n",
            encoding="utf-8",
        )
    except OSError:
        print(
            "ERROR: no se pudo escribir la evidencia de métricas.",
            file=sys.stderr,
        )
        return 2

    print(
        f"Registros válidos: {report['records']}; "
        f"tipos de tarea: {len(report['task_types'])}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
