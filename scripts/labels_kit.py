#!/usr/bin/env python3
"""Valida catálogos y selecciones de etiquetas del kit Factory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.safe_io import SafeIOError, read_repo_text
else:
    from safe_io import SafeIOError, read_repo_text

HEX = re.compile(r"^[0-9A-Fa-f]{6}$")
KEY = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
DIMENSIONS = ("type_", "priority_", "state_")
KIT_ROOT = Path(__file__).resolve().parents[1]
CATALOGS = {
    "es": Path("labels/es.json"),
    "en": Path("labels/en.json"),
}
LEGACY_ALIASES = {
    "es": {
        "prioridad: normal": "prioridad: media",
        "calidad": "tipo: calidad",
        "seguridad": "tipo: seguridad",
        "deuda técnica": "tipo: deuda técnica",
        "accesibilidad": "tipo: accesibilidad",
    },
    "en": {
        "priority: normal": "priority: medium",
        "quality": "type: quality",
        "security": "type: security",
        "technical debt": "type: technical debt",
        "accessibility": "type: accessibility",
    },
}
MAX_CATALOG_BYTES = 512 * 1024

class LabelError(ValueError):
    pass

def catalog_for_language(language: str) -> list[dict[str, str]]:
    try:
        path = CATALOGS[language]
    except KeyError as exc:
        raise LabelError("Idioma de catálogo inválido.") from exc
    return load_catalog(path, root=KIT_ROOT)

def aliases_for_language(language: str) -> dict[str, str]:
    try:
        return dict(LEGACY_ALIASES[language])
    except KeyError as exc:
        raise LabelError("Idioma de aliases inválido.") from exc

def load_catalog(path: Path, *, root: Path | None = None) -> list[dict[str, str]]:
    try:
        raw = json.loads(read_repo_text(path, root=root, max_bytes=MAX_CATALOG_BYTES))
    except (SafeIOError, json.JSONDecodeError) as exc:
        raise LabelError("Catálogo ilegible o JSON inválido.") from exc
    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise LabelError("El catálogo debe contener entre 1 y 200 etiquetas.")
    keys: set[str] = set()
    names: set[str] = set()
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"key", "name", "color", "description"}:
            raise LabelError("Cada etiqueta debe contener exactamente key, name, color y description.")
        key = item["key"]
        name = item["name"]
        color = item["color"]
        description = item["description"]
        if (
            not isinstance(key, str) or not KEY.fullmatch(key)
            or not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or "\n" in name or "\r" in name
            or not isinstance(color, str) or not HEX.fullmatch(color)
            or not isinstance(description, str) or not 1 <= len(description.strip()) <= 240
            or "\n" in description or "\r" in description
        ):
            raise LabelError("Etiqueta contiene datos fuera del contrato.")
        name = name.strip()
        description = description.strip()
        color = color.upper()
        if key in keys or name in names:
            raise LabelError("key y name deben ser únicos.")
        keys.add(key)
        names.add(name)
        out.append({"key": key, "name": name, "color": color, "description": description})
    for prefix in DIMENSIONS:
        if not any(item["key"].startswith(prefix) for item in out):
            raise LabelError(f"Falta dimensión obligatoria {prefix}")
    return out

def selected_names(raw: Any) -> set[str]:
    if not isinstance(raw, list) or len(raw) > 200:
        raise LabelError("La selección de labels debe ser una lista acotada.")
    names: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            name = item["name"]
        else:
            raise LabelError("Label seleccionada con formato inválido.")
        if not 1 <= len(name) <= 80 or "\n" in name or "\r" in name:
            raise LabelError("Nombre de label fuera del contrato.")
        names.add(name)
    return names

def validate_selection(catalog: list[dict[str, str]], names: set[str]) -> None:
    by_dimension = {
        prefix: {item["name"] for item in catalog if item["key"].startswith(prefix)}
        for prefix in DIMENSIONS
    }
    labels = {"type_": "tipo/type", "priority_": "prioridad/priority", "state_": "estado/status"}
    for prefix, allowed in by_dimension.items():
        matches = names & allowed
        if len(matches) != 1:
            raise LabelError(
                f"Debe existir exactamente una etiqueta de {labels[prefix]}; encontradas: {sorted(matches)}"
            )

def upsert_plan(
    catalog: list[dict[str, str]],
    existing: Any,
    *,
    aliases: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(existing, list) or len(existing) > 1000:
        raise LabelError("La respuesta de labels existentes debe ser una lista acotada.")
    current: dict[str, dict[str, Any]] = {}
    for item in existing:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            current[item["name"]] = item

    wanted_by_name = {item["name"]: item for item in catalog}
    plan: list[dict[str, str]] = []
    renamed_targets: set[str] = set()
    for old_name, new_name in (aliases or {}).items():
        if old_name == new_name or new_name not in wanted_by_name:
            raise LabelError("Alias de migración inválido.")
        if old_name not in current:
            continue
        if new_name in current or new_name in renamed_targets:
            raise LabelError(
                f"No se puede renombrar {old_name!r} a {new_name!r}: "
                "la etiqueta destino ya existe."
            )
        plan.append(
            {
                "action": "rename",
                "old_name": old_name,
                **wanted_by_name[new_name],
            }
        )
        renamed_targets.add(new_name)

    for wanted in catalog:
        if wanted["name"] in renamed_targets:
            continue
        have = current.get(wanted["name"])
        if have is None:
            plan.append({"action": "create", **wanted})
            continue
        if (
            str(have.get("color", "")).upper() != wanted["color"]
            or str(have.get("description") or "") != wanted["description"]
        ):
            plan.append({"action": "update", **wanted})
    return plan

def sweep(catalog: list[dict[str, str]], lines: list[str]) -> list[int]:
    if len(lines) > 10_000:
        raise LabelError("Sweep excede el máximo de Issues permitido.")
    invalid: list[int] = []
    for line in lines:
        if not line.strip():
            continue
        if len(line) > 100_000:
            raise LabelError("Sweep recibió una línea demasiado larga.")
        try:
            issue = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LabelError("Sweep recibió NDJSON inválido.") from exc
        if (
            not isinstance(issue, dict)
            or isinstance(issue.get("number"), bool)
            or not isinstance(issue.get("number"), int)
            or issue["number"] < 1
        ):
            raise LabelError("Sweep recibió Issue inválido.")
        try:
            validate_selection(catalog, selected_names(issue.get("labels", [])))
        except LabelError:
            invalid.append(issue["number"])
    return invalid

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate-catalog", "validate-selection", "upsert-plan", "sweep"))
    parser.add_argument("--language", choices=sorted(CATALOGS), required=True)
    args = parser.parse_args()
    try:
        catalog = catalog_for_language(args.language)
        if args.command == "validate-catalog":
            print(json.dumps({"labels": len(catalog)}, sort_keys=True))
            return 0
        if args.command == "validate-selection":
            validate_selection(catalog, selected_names(json.load(sys.stdin)))
            print('{"valid":true}')
            return 0
        if args.command == "upsert-plan":
            print(
                json.dumps(
                    upsert_plan(
                        catalog,
                        json.load(sys.stdin),
                        aliases=aliases_for_language(args.language),
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        invalid = sweep(catalog, sys.stdin.readlines())
        print(json.dumps({"invalid": invalid}, sort_keys=True))
        return 1 if invalid else 0
    except (LabelError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
