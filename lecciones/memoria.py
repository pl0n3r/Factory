#!/usr/bin/env python3
"""Valida lecciones, genera contexto acotado y mide tokens de bootstrap."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REQUIRED = {"id", "project", "kind", "occurred_at", "what", "why", "prevention", "source"}
ALLOWED_KINDS = {"incident", "rework", "process"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_INPUT_FILES = 500
MAX_INPUT_FILE_BYTES = 2_000_000
REPO_ROOT = Path(__file__).resolve().parents[1]
LESSONS_DATA_DIR = REPO_ROOT / "lecciones" / "registros"
METRICS_DATA_FILE = REPO_ROOT / "metricas" / "datos" / "tareas.jsonl"

SOURCE_RE = re.compile(
    r"^(?:https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/[1-9][0-9]*"
    r"|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*)$"
)


class LessonValidationError(ValueError):
    pass


def _text(raw: dict[str, Any], field: str, where: str, max_len: int = 280) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_len or "\n" in value:
        raise LessonValidationError(
            f"{where}: {field} debe ser texto de una línea, 1..{max_len} caracteres."
        )
    return value.strip()


def validate_lesson(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LessonValidationError(f"{where}: cada lección debe ser un objeto JSON.")
    if set(raw) != REQUIRED:
        missing = sorted(REQUIRED - set(raw))
        unknown = sorted(set(raw) - REQUIRED)
        detail = "campos faltantes" if missing else "campos no permitidos"
        names = missing or unknown
        raise LessonValidationError(f"{where}: {detail}: {', '.join(names)}.")
    item = {key: _text(raw, key, where) for key in REQUIRED}
    if not ID_RE.fullmatch(item["id"]):
        raise LessonValidationError(f"{where}: id inválido.")
    if not PROJECT_RE.fullmatch(item["project"]):
        raise LessonValidationError(f"{where}: project debe usar owner/repo.")
    if item["kind"] not in ALLOWED_KINDS:
        raise LessonValidationError(f"{where}: kind inválido.")
    if not SOURCE_RE.fullmatch(item["source"]):
        raise LessonValidationError(
            f"{where}: source debe ser Issue/PR de GitHub o owner/repo#N."
        )
    try:
        parsed = datetime.fromisoformat(item["occurred_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise LessonValidationError(f"{where}: occurred_at debe ser ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise LessonValidationError(f"{where}: occurred_at debe incluir zona horaria.")
    item["_sort_at"] = parsed.astimezone(timezone.utc)
    return item


def load_lessons(paths: list[Path]) -> list[dict[str, Any]]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.jsonl")))
        elif path.is_file():
            files.append(path)
        else:
            raise LessonValidationError(f"Entrada inexistente: {path.name}.")

    files = sorted(set(files))
    if len(files) > MAX_INPUT_FILES:
        raise LessonValidationError(
            f"Demasiados archivos de lecciones; máximo {MAX_INPUT_FILES}."
        )

    out: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in files:
        if path.suffix != ".jsonl":
            raise LessonValidationError(
                f"{path.name}: extensión no permitida; se requiere .jsonl."
            )
        if path.is_symlink():
            raise LessonValidationError(
                f"{path.name}: enlaces simbólicos no están permitidos."
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise LessonValidationError(
                f"{path.name}: no se pudo inspeccionar el archivo."
            ) from exc
        if size > MAX_INPUT_FILE_BYTES:
            raise LessonValidationError(
                f"{path.name}: archivo supera {MAX_INPUT_FILE_BYTES} bytes."
            )

        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            raise LessonValidationError(
                f"{path.name}: no se pudo abrir el archivo."
            ) from exc

        try:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                if len(line) > 2048:
                    raise LessonValidationError(
                        f"{path.name}:línea {number}: registro demasiado largo."
                    )
                where = f"{path.name}:línea {number}"
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LessonValidationError(f"{where}: JSON inválido.") from exc
                item = validate_lesson(raw, where)
                if item["id"] in ids:
                    raise LessonValidationError(f"{where}: id duplicado.")
                ids.add(item["id"])
                out.append(item)
        except UnicodeDecodeError as exc:
            raise LessonValidationError(
                f"{path.name}: el archivo no es UTF-8 válido."
            ) from exc
        finally:
            handle.close()
    return out
def summarize(
    lessons: list[dict[str, Any]],
    project: str,
    max_lessons: int = 5,
    max_chars: int = 3000,
) -> str:
    if not PROJECT_RE.fullmatch(project):
        raise LessonValidationError("project debe usar owner/repo.")
    if not 1 <= max_lessons <= 20 or not 400 <= max_chars <= 12000:
        raise LessonValidationError("Límites de contexto fuera de rango seguro.")
    relevant = sorted(
        (item for item in lessons if item["project"] == project),
        key=lambda item: item["_sort_at"],
        reverse=True,
    )
    result = f"# Contexto rápido — {project}\n\n"
    included = 0
    for item in relevant:
        if included >= max_lessons:
            break
        block = (
            f"## {item['id']} · {item['kind']}\n"
            f"- Qué pasó: {item['what']}\n"
            f"- Por qué: {item['why']}\n"
            f"- Cómo evitarlo: {item['prevention']}\n"
            f"- Fuente: {item['source']}\n\n"
        )
        if len(result) + len(block) > max_chars:
            continue
        result += block
        included += 1
    if included == 0:
        message = (
            "Hay lecciones relevantes, pero ninguna cabe en el límite de contexto.\n"
            if relevant
            else "Sin lecciones relevantes registradas.\n"
        )
        if len(result) + len(message) <= max_chars:
            result += message
    return result

def _task_project(task_id: Any, where: str) -> str:
    if not isinstance(task_id, str):
        raise LessonValidationError(f"{where}: task_id es obligatorio para aislar el proyecto.")
    match = re.fullmatch(
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#[1-9][0-9]*",
        task_id,
    )
    if not match:
        raise LessonValidationError(
            f"{where}: task_id debe usar owner/repo#N para métricas de bootstrap."
        )
    return match.group(1)


def token_comparison(
    path: Path,
    change_at: str,
    project: str,
    task_type: str = "agent-bootstrap",
    min_samples: int = 2,
) -> dict[str, Any]:
    if not PROJECT_RE.fullmatch(project):
        raise LessonValidationError("project debe usar owner/repo.")
    if not isinstance(task_type, str) or not ID_RE.fullmatch(task_type):
        raise LessonValidationError("task_type inválido.")
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 1:
        raise LessonValidationError("min_samples debe ser entero >= 1.")
    try:
        change = datetime.fromisoformat(change_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LessonValidationError("change_at debe ser ISO-8601.") from exc
    if change.tzinfo is None:
        raise LessonValidationError("change_at debe incluir zona horaria.")
    change = change.astimezone(timezone.utc)

    before: list[int] = []
    after: list[int] = []
    common = {
        "project": project,
        "task_type": task_type,
        "change_at": change.isoformat(),
        "min_samples": min_samples,
    }
    if not path.exists():
        return {
            **common,
            "status": "insufficient-data",
            "before_samples": 0,
            "after_samples": 0,
            "reduction_pct": None,
        }
    if path.is_symlink():
        raise LessonValidationError(
            "La telemetría de bootstrap no acepta enlaces simbólicos."
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise LessonValidationError(
            "No se pudo inspeccionar la telemetría de bootstrap."
        ) from exc
    if size > MAX_INPUT_FILE_BYTES:
        raise LessonValidationError(
            f"La telemetría supera {MAX_INPUT_FILE_BYTES} bytes."
        )
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise LessonValidationError(
            "No se pudo abrir la telemetría de bootstrap."
        ) from exc

    try:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            if len(line) > 100_000:
                raise LessonValidationError(
                    f"tokens:línea {number}: registro demasiado largo."
                )
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LessonValidationError(
                    f"tokens:línea {number}: JSON inválido."
                ) from exc
            if not isinstance(row, dict) or row.get("task_type") != task_type:
                continue

            row_project = _task_project(
                row.get("task_id"),
                f"tokens:línea {number}",
            )
            if row_project != project:
                continue

            value = row.get("tokens_input")
            stamp = row.get("completed_at")
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or not isinstance(stamp, str)
            ):
                raise LessonValidationError(
                    f"tokens:línea {number}: telemetría inválida."
                )
            try:
                completed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise LessonValidationError(
                    f"tokens:línea {number}: completed_at inválido."
                ) from exc
            if completed.tzinfo is None:
                raise LessonValidationError(
                    f"tokens:línea {number}: completed_at sin zona horaria."
                )
            target = before if completed.astimezone(timezone.utc) < change else after
            target.append(value)
    except UnicodeDecodeError as exc:
        raise LessonValidationError(
            "La telemetría de bootstrap no es UTF-8 válida."
        ) from exc
    finally:
        handle.close()

    if len(before) < min_samples or len(after) < min_samples:
        return {
            **common,
            "status": "insufficient-data",
            "before_samples": len(before),
            "after_samples": len(after),
            "reduction_pct": None,
        }

    before_avg, after_avg = mean(before), mean(after)
    reduction = (
        round(((before_avg - after_avg) / before_avg) * 100, 2)
        if before_avg
        else None
    )
    return {
        **common,
        "status": "measured",
        "before_samples": len(before),
        "after_samples": len(after),
        "before_avg_tokens": round(before_avg, 2),
        "after_avg_tokens": round(after_avg, 2),
        "reduction_pct": reduction,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    summary = sub.add_parser("summary")
    summary.add_argument("--project", required=True)
    summary.add_argument("--max-lessons", type=int, default=5)
    summary.add_argument("--max-chars", type=int, default=3000)

    compare = sub.add_parser("compare-tokens")
    compare.add_argument("--change-at", required=True)
    compare.add_argument("--project", required=True)
    compare.add_argument("--task-type", default="agent-bootstrap")
    args = parser.parse_args()

    try:
        if args.command == "summary":
            output = summarize(
                load_lessons([LESSONS_DATA_DIR]),
                args.project,
                args.max_lessons,
                args.max_chars,
            )
            print(output, end="")
        else:
            output = token_comparison(
                METRICS_DATA_FILE,
                args.change_at,
                args.project,
                args.task_type,
            )
            print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    except LessonValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
