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
WARNING_MARKER = "<!-- factory-label-validation -->"
AUTO_MARKER = "<!-- factory-auto-unlabeled -->"
CLOSING_REFERENCE = re.compile(r"\b(?:closes|fixes|resolves)\s+#([1-9][0-9]*)\b", re.IGNORECASE)

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
        if new_name in current:
            # Si alias y destino canónico ya coexisten, conservar el canónico.
            # El bucle normal de catálogo actualizará su metadata si hay drift.
            continue
        if new_name in renamed_targets:
            raise LabelError(
                f"No se puede renombrar {old_name!r} a {new_name!r}: "
                "otro alias del plan ya reclama la etiqueta destino."
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

def _catalog_name(catalog: list[dict[str, str]], key: str) -> str:
    matches = [item["name"] for item in catalog if item["key"] == key]
    if len(matches) != 1:
        raise LabelError(f"Catálogo no contiene exactamente una etiqueta {key}.")
    return matches[0]

def _dimension_matches(catalog: list[dict[str, str]], names: set[str], prefix: str) -> set[str]:
    allowed = {item["name"] for item in catalog if item["key"].startswith(prefix)}
    return names & allowed

def closing_issue_reference(body: str) -> int | None:
    if not isinstance(body, str) or len(body) > 100_000:
        raise LabelError("Body fuera del contrato para referencia de cierre.")
    references = {int(value) for value in CLOSING_REFERENCE.findall(body)}
    return next(iter(references)) if len(references) == 1 else None

def linked_issue_names(raw: Any) -> set[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise LabelError("Issue enlazado inválido.")
    if raw.get("pull_request") is not None:
        return None
    if raw.get("state") not in {"open", "closed"}:
        return None
    return selected_names(raw.get("labels", []))

def validation_plan(
    catalog: list[dict[str, str]],
    names: set[str],
    *,
    is_pull_request: bool,
    body: str = "",
    linked_names: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(is_pull_request, bool):
        raise LabelError("is_pull_request debe ser booleano.")
    additions: list[str] = []
    planned = set(names)

    if not _dimension_matches(catalog, planned, "state_"):
        default_key = "state_review" if is_pull_request else "state_available"
        default_name = _catalog_name(catalog, default_key)
        additions.append(default_name)
        planned.add(default_name)

    closing = closing_issue_reference(body) if is_pull_request else None
    if closing is not None and linked_names is not None:
        for prefix in ("type_", "priority_"):
            if _dimension_matches(catalog, planned, prefix):
                continue
            inherited = _dimension_matches(catalog, linked_names, prefix)
            if len(inherited) == 1:
                value = next(iter(inherited))
                additions.append(value)
                planned.add(value)

    dimension_codes = {"type_": "type", "priority_": "priority", "state_": "state"}
    missing: list[str] = []
    multiple: list[str] = []
    for prefix in DIMENSIONS:
        matches = _dimension_matches(catalog, planned, prefix)
        if not matches:
            missing.append(dimension_codes[prefix])
        elif len(matches) > 1:
            multiple.append(dimension_codes[prefix])

    return {
        "add": sorted(set(additions)),
        "closing_issue": closing,
        "missing": missing,
        "multiple": multiple,
        "valid": not missing and not multiple,
    }

def warning_plan(plan: dict[str, Any], language: str) -> dict[str, str]:
    if language not in CATALOGS:
        raise LabelError("Idioma de warning inválido.")
    valid = plan.get("valid") is True
    if valid:
        message = "✅ Clasificación completa." if language == "es" else "✅ Classification complete."
        return {"action": "clear", "body": WARNING_MARKER + "\n" + message}
    missing = plan.get("missing", [])
    multiple = plan.get("multiple", [])
    if not isinstance(missing, list) or not isinstance(multiple, list):
        raise LabelError("Plan de warning inválido.")
    controlled = {"type", "priority", "state"}
    if any(item not in controlled for item in [*missing, *multiple]):
        raise LabelError("Dimensión de warning inválida.")
    if language == "es":
        details = []
        if missing:
            details.append("faltan: " + ", ".join(missing))
        if multiple:
            details.append("duplicadas: " + ", ".join(multiple))
        message = "⚠️ Clasificación incompleta (" + "; ".join(details) + ")."
    else:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if multiple:
            details.append("multiple: " + ", ".join(multiple))
        message = "⚠️ Incomplete classification (" + "; ".join(details) + ")."
    return {"action": "warn", "body": WARNING_MARKER + "\n" + message}

def sweep_issue_plan(
    catalog: list[dict[str, str]], invalid: list[int], language: str
) -> dict[str, Any]:
    if language not in CATALOGS:
        raise LabelError("Idioma de sweep inválido.")
    if len(invalid) > 10_000 or any(
        isinstance(number, bool) or not isinstance(number, int) or number < 1
        for number in invalid
    ):
        raise LabelError("Lista de Issues inválidos fuera del contrato.")
    numbers = sorted(set(invalid))
    labels = [
        _catalog_name(catalog, "type_infrastructure"),
        _catalog_name(catalog, "priority_medium"),
        _catalog_name(catalog, "state_available"),
    ]
    if numbers:
        heading = (
            "Ítems abiertos sin clasificación completa:"
            if language == "es"
            else "Open items without complete classification:"
        )
        body = AUTO_MARKER + "\n" + heading + "\n\n" + "\n".join(f"- #{number}" for number in numbers)
        action = "upsert"
    else:
        message = (
            "✅ No quedan ítems abiertos sin clasificar."
            if language == "es"
            else "✅ No open items remain unclassified."
        )
        body = AUTO_MARKER + "\n" + message
        action = "close"
    return {
        "action": action,
        "body": body,
        "labels": labels,
        "title": "[AUTO] Unlabeled items",
    }

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

def validation_document_plan(
    catalog: list[dict[str, str]],
    document: Any,
    language: str,
) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {
        "labels",
        "is_pull_request",
        "body",
        "linked_issue",
    }:
        raise LabelError("Documento de validación inválido.")
    if not isinstance(document["is_pull_request"], bool) or not isinstance(document["body"], str):
        raise LabelError("Documento de validación fuera del contrato.")
    plan = validation_plan(
        catalog,
        selected_names(document["labels"]),
        is_pull_request=document["is_pull_request"],
        body=document["body"],
        linked_names=linked_issue_names(document["linked_issue"]),
    )
    plan["warning"] = warning_plan(plan, language)
    return plan

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "validate-catalog",
            "validate-selection",
            "upsert-plan",
            "closing-reference",
            "plan-validation",
            "sweep",
            "sweep-plan",
        ),
    )
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
        if args.command == "closing-reference":
            print(json.dumps({"number": closing_issue_reference(sys.stdin.read())}, sort_keys=True))
            return 0
        if args.command == "plan-validation":
            plan = validation_document_plan(catalog, json.load(sys.stdin), args.language)
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 0
        lines = sys.stdin.readlines()
        invalid = sweep(catalog, lines)
        if args.command == "sweep-plan":
            print(json.dumps(sweep_issue_plan(catalog, invalid, args.language), ensure_ascii=False, sort_keys=True))
            return 0
        print(json.dumps({"invalid": invalid}, sort_keys=True))
        return 1 if invalid else 0
    except (LabelError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
