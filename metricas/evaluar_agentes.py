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
from typing import Any

REQUIRED = {
    "task_id", "task_type", "agent", "model", "prompt_id", "roles",
    "success", "merged_first_try", "commits", "review_rounds",
    "rework_commits", "incidents_after", "completed_at",
}
OPTIONAL = {"tokens_input", "tokens_output", "ci_minutes", "agent_minutes"}
ALLOWED = REQUIRED | OPTIONAL

MAX_INPUT_FILES = 500
MAX_INPUT_FILE_BYTES = 2_000_000
MAX_INPUT_LINE_CHARS = 100_000
MAX_RECORDS = 100_000
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "metricas" / "datos"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts"


class ValidationError(ValueError):
    pass


SLUG_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
TASK_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?#[1-9][0-9]*$")


def _text(record: dict[str, Any], field: str, where: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValidationError(f"{where}: campo {field} debe ser texto no vacío (máx. 160).")
    return value.strip()


def _integer(record: dict[str, Any], field: str, where: str, optional: bool = False) -> int | None:
    value = record.get(field)
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{where}: campo {field} debe ser entero >= 0.")
    return value


def validate_record(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError(f"{where}: cada registro debe ser un objeto JSON.")
    missing = REQUIRED - raw.keys()
    unknown = raw.keys() - ALLOWED
    if missing:
        raise ValidationError(f"{where}: faltan campos: {', '.join(sorted(missing))}.")
    if unknown:
        raise ValidationError(f"{where}: campos no permitidos: {', '.join(sorted(unknown))}.")

    record = {field: _text(raw, field, where) for field in
              ("task_id", "task_type", "agent", "model", "prompt_id", "completed_at")}
    if not TASK_RE.fullmatch(record["task_id"]):
        raise ValidationError(f"{where}: task_id debe usar repo#N u owner/repo#N.")
    for field in ("task_type", "agent", "model", "prompt_id"):
        if not SLUG_RE.fullmatch(record[field]):
            raise ValidationError(f"{where}: campo {field} debe ser un identificador, no texto libre.")
    roles = raw["roles"]
    if not isinstance(roles, list) or not roles or len(roles) > 8:
        raise ValidationError(f"{where}: roles debe contener entre 1 y 8 textos.")
    if any(not isinstance(role, str) or not role.strip() or len(role) > 80 for role in roles):
        raise ValidationError(f"{where}: cada rol debe ser texto no vacío (máx. 80).")
    record["roles"] = sorted(set(role.strip() for role in roles))
    if any(not SLUG_RE.fullmatch(role) for role in record["roles"]):
        raise ValidationError(f"{where}: cada rol debe ser un identificador, no texto libre.")

    for field in ("success", "merged_first_try"):
        if not isinstance(raw[field], bool):
            raise ValidationError(f"{where}: campo {field} debe ser booleano.")
        record[field] = raw[field]
    for field in ("commits", "review_rounds", "rework_commits", "incidents_after"):
        record[field] = _integer(raw, field, where)
    if record["review_rounds"] > 3:
        raise ValidationError(f"{where}: review_rounds no puede superar 3.")

    for field in OPTIONAL:
        record[field] = _integer(raw, field, where, optional=True)

    try:
        parsed = datetime.fromisoformat(record["completed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{where}: completed_at debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{where}: completed_at debe incluir zona horaria.")

    return record


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month):
        raise ValidationError("month debe usar YYYY-MM.")
    year, month_number = (int(part) for part in month.split("-"))
    try:
        start = datetime(year, month_number, 1, tzinfo=timezone.utc)
        if month_number == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month_number + 1, 1, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValidationError("month está fuera del rango de fechas soportado.") from exc
    return start, end


def load_records(
    inputs: list[Path],
    allow_empty: bool = False,
    month: str | None = None,
) -> list[dict[str, Any]]:
    files: list[Path] = []
    bounds = _month_bounds(month) if month else None
    for item in inputs:
        if item.is_dir():
            files.extend(sorted(item.rglob("*.jsonl")))
        elif item.is_file():
            files.append(item)
        elif not allow_empty:
            raise ValidationError(f"Entrada inexistente: {item.name}.")

    files = sorted(set(files))
    if len(files) > MAX_INPUT_FILES:
        raise ValidationError(f"Demasiados archivos de entrada; máximo {MAX_INPUT_FILES}.")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        if path.suffix != ".jsonl":
            raise ValidationError(f"{path.name}: extensión no permitida; se requiere .jsonl.")
        if path.is_symlink():
            raise ValidationError(f"{path.name}: enlaces simbólicos no están permitidos.")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ValidationError(f"{path.name}: no se pudo inspeccionar el archivo.") from exc
        if size > MAX_INPUT_FILE_BYTES:
            raise ValidationError(
                f"{path.name}: archivo supera el máximo de {MAX_INPUT_FILE_BYTES} bytes."
            )

        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            raise ValidationError(f"{path.name}: no se pudo abrir el archivo.") from exc

        try:
            for line_no, line in enumerate(handle, 1):
                if len(line) > MAX_INPUT_LINE_CHARS:
                    raise ValidationError(
                        f"{path.name}:línea {line_no}: supera el máximo permitido."
                    )
                if not line.strip():
                    continue
                where = f"{path.name}:línea {line_no}"
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"{where}: JSON inválido.") from exc
                record = validate_record(raw, where)
                if record["task_id"] in seen:
                    raise ValidationError(f"{where}: task_id duplicado; no se contabiliza dos veces.")
                seen.add(record["task_id"])
                if bounds:
                    completed = datetime.fromisoformat(
                        record["completed_at"].replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    if not (bounds[0] <= completed < bounds[1]):
                        continue
                records.append(record)
                if len(records) > MAX_RECORDS:
                    raise ValidationError(
                        f"Se superó el máximo de {MAX_RECORDS} registros por evaluación."
                    )
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{path.name}: el archivo no es UTF-8 válido.") from exc
        finally:
            handle.close()

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


def aggregate(records: list[dict[str, Any]], min_samples: int = 3) -> dict[str, Any]:
    if min_samples < 1:
        raise ValidationError("min_samples debe ser >= 1.")
    grouped: dict[str, dict[tuple[str, ...], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        key = (record["agent"], record["model"], record["prompt_id"], ",".join(record["roles"]))
        grouped[record["task_type"]][key].append(record)

    task_types: dict[str, Any] = {}
    for task_type, configs in sorted(grouped.items()):
        rows = []
        for key, items in configs.items():
            n = len(items)
            if n == 0:
                raise ValidationError("Grupo de configuración vacío; no se puede calcular el ranking.")
            token_totals = [
                item["tokens_input"] + item["tokens_output"]
                if item["tokens_input"] is not None and item["tokens_output"] is not None
                else None
                for item in items
            ]
            token_complete_samples = sum(value is not None for value in token_totals)
            tokens_avg = _avg(token_totals) if token_complete_samples == n else None
            eligible = n >= min_samples
            row = {
                "configuration": {"agent": key[0], "model": key[1], "prompt_id": key[2],
                                  "roles": key[3].split(",")},
                "samples": n,
                "sample_status": "eligible" if eligible else "insufficient_data",
                "success_rate": round(sum(item["success"] for item in items) / n, 4),
                "first_merge_rate": round(sum(item["merged_first_try"] for item in items) / n, 4),
                "incidents_per_task": round(sum(item["incidents_after"] for item in items) / n, 4),
                "commits_avg": _avg([item["commits"] for item in items]),
                "review_rounds_avg": _avg([item["review_rounds"] for item in items]),
                "rework_commits_avg": _avg([item["rework_commits"] for item in items]),
                "tokens_avg": tokens_avg,
                "tokens_complete_samples": token_complete_samples,
                "ci_minutes_avg": _avg([item["ci_minutes"] for item in items]),
                "agent_minutes_avg": _avg([item["agent_minutes"] for item in items]),
                "eligible": eligible,
                "rank": None,
            }
            rows.append(row)

        eligible = [row for row in rows if row["eligible"]]
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            groups[_core_quality_key(row)].append(row)

        position = 1
        ordered_eligible: list[dict[str, Any]] = []
        ordered_groups: list[list[dict[str, Any]]] = []
        for core_key in sorted(groups):
            group = groups[core_key]
            all_tokens_complete = all(row["tokens_avg"] is not None for row in group)
            if all_tokens_complete:
                group.sort(key=lambda row: (
                    row["tokens_avg"],
                    json.dumps(row["configuration"], sort_keys=True),
                ))
                previous_tokens = None
                current_rank = position
                for offset, row in enumerate(group):
                    if previous_tokens is None or row["tokens_avg"] != previous_tokens:
                        current_rank = position + offset
                    row["rank"] = current_rank
                    previous_tokens = row["tokens_avg"]
            else:
                group.sort(key=lambda row: json.dumps(row["configuration"], sort_keys=True))
                for row in group:
                    row["rank"] = position
            ordered_groups.append(group)
            ordered_eligible.extend(group)
            position += len(group)

        eligible_ids = {id(row) for row in eligible}
        ineligible = [row for row in rows if id(row) not in eligible_ids]
        ineligible.sort(key=lambda row: json.dumps(row["configuration"], sort_keys=True))
        rows = ordered_eligible + ineligible

        recommendation = None
        recommendation_status = "insufficient-comparison"
        if len(eligible) >= 2 and ordered_groups:
            top_group = ordered_groups[0]
            if len(top_group) == 1:
                recommendation = top_group[0]["configuration"]
                recommendation_status = "data-backed"
            else:
                first_tokens = top_group[0]["tokens_avg"]
                second_tokens = top_group[1]["tokens_avg"]
                complete_tokens = (
                    isinstance(first_tokens, (int, float))
                    and not isinstance(first_tokens, bool)
                    and isinstance(second_tokens, (int, float))
                    and not isinstance(second_tokens, bool)
                )
                if complete_tokens and first_tokens < second_tokens:
                    recommendation = top_group[0]["configuration"]
                    recommendation_status = "data-backed"
                else:
                    recommendation_status = "tie-or-incomplete-cost"

        task_types[task_type] = {
            "configurations": rows,
            "recommendation": recommendation,
            "recommendation_status": recommendation_status,
        }

    return {
        "schema_version": 1,
        "min_samples": min_samples,
        "records": len(records),
        "period": "all",
        "task_types": task_types,
    }

def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Evaluación de agentes, modelos y prompts", "",
             f"- Registros válidos: **{report['records']}**",
             f"- Muestra mínima por configuración: **{report['min_samples']}**",
             f"- Periodo UTC: **{report.get('period', 'all')}**", ""]
    if not report["task_types"]:
        lines += ["No hay datos suficientes todavía. No se emite recomendación.", ""]
        return "\n".join(lines)

    for task_type, data in report["task_types"].items():
        lines += [f"## {task_type}", "",
                  "| Rank | Configuración | N | Éxito | 1ª integración | Incidentes/tarea | Retrabajo | Rondas | Tokens |",
                  "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in data["configurations"]:
            cfg = row["configuration"]
            name = f"{cfg['agent']} / {cfg['model']} / {cfg['prompt_id']} / {','.join(cfg['roles'])}"
            rank = row["rank"] if row["rank"] is not None else "—"
            tokens = row["tokens_avg"] if row["tokens_avg"] is not None else "—"
            lines.append(
                f"| {rank} | {name} | {row['samples']} | {row['success_rate']:.1%} | "
                f"{row['first_merge_rate']:.1%} | {row['incidents_per_task']:.2f} | "
                f"{row['rework_commits_avg']:.2f} | {row['review_rounds_avg']:.2f} | {tokens} |"
            )
        if data["recommendation"]:
            cfg = data["recommendation"]
            lines += ["", f"**Recomendación basada en datos:** {cfg['agent']} / {cfg['model']} / {cfg['prompt_id']}."]
        else:
            lines += ["", "**Sin recomendación:** faltan al menos dos configuraciones con muestra suficiente."]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--month", help="Mes UTC YYYY-MM; omitir para histórico acumulado.")
    args = parser.parse_args()

    try:
        report = aggregate(
            load_records([DEFAULT_DATA_DIR], args.allow_empty, args.month),
            args.min_samples,
        )
        report["period"] = args.month or "all"
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (DEFAULT_OUTPUT_DIR / "recomendaciones.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (DEFAULT_OUTPUT_DIR / "dashboard.md").write_text(
            render_markdown(report) + "\n",
            encoding="utf-8",
        )
    except OSError:
        print("ERROR: no se pudo escribir la evidencia de métricas.", file=sys.stderr)
        return 2

    print(f"Registros válidos: {report['records']}; tipos de tarea: {len(report['task_types'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
