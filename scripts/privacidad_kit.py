#!/usr/bin/env python3
"""Contrato de privacidad como código: metadatos estructurados, nunca PII real."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from scripts.safe_io import SafeIOError, read_repo_text


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "legal" / "reglas-datos.yml"
TEMPLATE_ROOT = ROOT / "legal" / "plantillas"
MAX_BYTES = 256_000
SLUG = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
PROJECT = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
OWNER_FIELDS = ("name", "identifier", "address", "rights_email")
TREATMENT_FIELDS = (
    "id", "category", "fields", "purpose", "basis", "retention", "consent", "providers"
)
CONSENT_VALUES = {"review_required", "documented", "documented_explicit"}
PLACEHOLDER_TOKEN = "[COMPLETAR POR EL DUEÑO]"


class PrivacyError(ValueError):
    """Fallo estructural seguro: nunca incorpora valores arbitrarios de entrada."""


def _json_document(text: str, label: str) -> object:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise PrivacyError(f"{label}: documento ausente o excesivo")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PrivacyError(f"{label}: JSON/YAML canónico inválido") from exc


def _controlled(value: object, label: str) -> str:
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise PrivacyError(f"{label}: se exige código controlado")
    return value


def _controlled_list(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > 50 or (not allow_empty and not value):
        raise PrivacyError(f"{label}: lista inválida")
    result = [_controlled(item, label) for item in value]
    if len(set(result)) != len(result):
        raise PrivacyError(f"{label}: valores duplicados")
    return result


def validate_rules(document: object) -> dict[str, Any]:
    expected = {
        "version", "owner_placeholder", "categories", "provider_signals",
        "required_treatment_fields", "material_changes", "documents",
    }
    if not isinstance(document, dict) or set(document) != expected:
        raise PrivacyError("reglas: campos raíz incompletos o adicionales")
    if type(document["version"]) is not int or document["version"] != 1:
        raise PrivacyError("reglas: versión no admitida")
    if document["owner_placeholder"] != PLACEHOLDER_TOKEN:
        raise PrivacyError("reglas: placeholder del responsable inválido")

    categories = document["categories"]
    if not isinstance(categories, dict) or not categories or len(categories) > 32:
        raise PrivacyError("reglas: categorías inválidas")
    for name, item in categories.items():
        _controlled(name, "reglas.category")
        if not isinstance(item, dict) or set(item) != {
            "signals", "sensitive", "explicit_consent_required", "maximum_retention"
        }:
            raise PrivacyError("reglas: categoría con esquema inválido")
        _controlled_list(item["signals"], "reglas.signals")
        if type(item["sensitive"]) is not bool or type(item["explicit_consent_required"]) is not bool:
            raise PrivacyError("reglas: flags de categoría inválidos")
        if item["explicit_consent_required"] and not item["sensitive"]:
            raise PrivacyError("reglas: consentimiento explícito solo puede exigirse a categoría sensible")
        if item["maximum_retention"] != "review_required":
            raise PrivacyError("reglas: retención máxima debe quedar en revisión jurídica")

    providers = document["provider_signals"]
    if not isinstance(providers, dict) or len(providers) > 64:
        raise PrivacyError("reglas: proveedores inválidos")
    for name, domains in providers.items():
        _controlled(name, "reglas.provider")
        if not isinstance(domains, list) or not domains or len(domains) > 20:
            raise PrivacyError("reglas: dominios de proveedor inválidos")
        if any(
            not isinstance(domain, str)
            or len(domain) > 120
            or re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) is None
            for domain in domains
        ):
            raise PrivacyError("reglas: dominio de proveedor inválido")

    if document["required_treatment_fields"] != list(TREATMENT_FIELDS):
        raise PrivacyError("reglas: contrato de tratamiento divergente")
    if document["material_changes"] != ["purpose", "sensitive", "new_provider"]:
        raise PrivacyError("reglas: cambios materiales divergentes")
    if document["documents"] != [
        "politica-tratamiento.md", "registro-tratamientos.md", "retencion.md"
    ]:
        raise PrivacyError("reglas: documentos requeridos divergentes")
    return document


def _validate_controller(controller: object, phase: str, placeholder: str) -> dict[str, str]:
    if not isinstance(controller, dict) or set(controller) != set(OWNER_FIELDS):
        raise PrivacyError("datos: responsable incompleto o adicional")
    result: dict[str, str] = {}
    for field in OWNER_FIELDS:
        value = controller[field]
        if not isinstance(value, str) or not 1 <= len(value) <= 160:
            raise PrivacyError("datos: valor de responsable inválido")
        if phase == "construccion" and value != placeholder:
            raise PrivacyError("datos: durante construcción el responsable debe conservar placeholder")
        if phase == "live" and value == placeholder:
            raise PrivacyError("datos: go-live no admite placeholders del responsable")
        result[field] = value
    return result


def _validate_treatment(raw: object, rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != set(TREATMENT_FIELDS):
        raise PrivacyError("datos: tratamiento con campos incompletos o adicionales")
    treatment_id = _controlled(raw["id"], "datos.treatment.id")
    category = _controlled(raw["category"], "datos.treatment.category")
    if category not in rules["categories"]:
        raise PrivacyError("datos: categoría no declarada")
    fields = _controlled_list(raw["fields"], "datos.treatment.fields")
    purpose = _controlled(raw["purpose"], "datos.treatment.purpose")
    basis = _controlled(raw["basis"], "datos.treatment.basis")
    retention = _controlled(raw["retention"], "datos.treatment.retention")
    consent = raw["consent"]
    if consent not in CONSENT_VALUES:
        raise PrivacyError("datos: estado de consentimiento inválido")
    providers = _controlled_list(
        raw["providers"], "datos.treatment.providers", allow_empty=True
    )
    category_rule = rules["categories"][category]
    if category_rule["explicit_consent_required"] and consent != "documented_explicit":
        raise PrivacyError("datos: categoría sensible requiere consentimiento explícito documentado")
    return {
        "id": treatment_id,
        "category": category,
        "fields": fields,
        "purpose": purpose,
        "basis": basis,
        "retention": retention,
        "consent": consent,
        "providers": providers,
    }


def validate_data_map(document: object, rules: dict[str, Any]) -> dict[str, Any]:
    expected = {"version", "project", "phase", "controller", "treatments"}
    if not isinstance(document, dict) or set(document) != expected:
        raise PrivacyError("datos: campos raíz incompletos o adicionales")
    if type(document["version"]) is not int or document["version"] != 1:
        raise PrivacyError("datos: versión no admitida")
    project = document["project"]
    if not isinstance(project, str) or not PROJECT.fullmatch(project):
        raise PrivacyError("datos: project debe usar owner/repo")
    phase = document["phase"]
    if phase not in {"construccion", "live"}:
        raise PrivacyError("datos: phase inválida")
    controller = _validate_controller(
        document["controller"], phase, rules["owner_placeholder"]
    )
    rows = document["treatments"]
    if not isinstance(rows, list) or len(rows) > 500:
        raise PrivacyError("datos: treatments inválido")
    treatments = [_validate_treatment(row, rules) for row in rows]
    ids = [row["id"] for row in treatments]
    if len(set(ids)) != len(ids):
        raise PrivacyError("datos: tratamientos duplicados")
    return {
        "version": 1,
        "project": project,
        "phase": phase,
        "controller": controller,
        "treatments": sorted(treatments, key=lambda row: row["id"]),
    }


def load_rules() -> dict[str, Any]:
    text = read_repo_text(
        RULES_PATH.relative_to(ROOT), root=ROOT, max_bytes=MAX_BYTES
    )
    return validate_rules(_json_document(text, "reglas"))


def load_data_map(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    base = (root or Path.cwd()).resolve()
    try:
        text = read_repo_text(path, root=base, max_bytes=MAX_BYTES)
    except SafeIOError as exc:
        raise PrivacyError("datos: ruta no confiable") from exc
    return validate_data_map(_json_document(text, "datos"), load_rules())


def _template(name: str) -> str:
    path = TEMPLATE_ROOT / name
    try:
        return read_repo_text(
            path.relative_to(ROOT), root=ROOT, max_bytes=MAX_BYTES
        )
    except SafeIOError as exc:
        raise PrivacyError("plantilla canónica ausente o inválida") from exc


def _table_rows(data: dict[str, Any]) -> str:
    lines = [
        "| Tratamiento | Categoría | Campos | Finalidad | Base documentada | Consentimiento | Proveedores | Retención |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in data["treatments"]:
        lines.append(
            "| "
            + " | ".join([
                row["id"],
                row["category"],
                ", ".join(row["fields"]),
                row["purpose"],
                row["basis"],
                row["consent"],
                ", ".join(row["providers"]) or "ninguno_declarado",
                row["retention"],
            ])
            + " |"
        )
    if not data["treatments"]:
        lines.append("| sin_tratamientos | none | — | — | — | — | — | — |")
    return "\n".join(lines)


def _code_list(values: list[str]) -> str:
    return ", ".join("`" + value + "`" for value in values)


def _register_sections(data: dict[str, Any]) -> str:
    if not data["treatments"]:
        return "No hay tratamientos declarados en `datos.yml`."
    sections = []
    for row in data["treatments"]:
        sections.extend([
            f"## {row['id']}",
            "",
            f"- Categoría: `{row['category']}`",
            f"- Campos de software: {_code_list(row['fields'])}",
            f"- Finalidad: `{row['purpose']}`",
            f"- Base documentada: `{row['basis']}` (revisión jurídica requerida)",
            f"- Consentimiento: `{row['consent']}`",
            f"- Proveedores: {_code_list(row['providers']) or 'ninguno_declarado'}",
            f"- Retención: `{row['retention']}`",
            "",
        ])
    return "\n".join(sections).rstrip()


def _retention_rows(data: dict[str, Any], rules: dict[str, Any]) -> str:
    if not data["treatments"]:
        return "| sin_tratamientos | none | — | — |"
    lines = []
    for row in data["treatments"]:
        maximum = rules["categories"][row["category"]]["maximum_retention"]
        lines.append(
            f"| {row['id']} | {row['category']} | {row['retention']} | {maximum} |"
        )
    return "\n".join(lines)


def _render(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    if re.search(r"\{\{[A-Z0-9_]+\}\}", rendered):
        raise PrivacyError("plantilla contiene variables sin resolver")
    return rendered.rstrip() + "\n"


def generate_documents(
    rules_document: object,
    data_document: object,
    *,
    templates: dict[str, str] | None = None,
) -> dict[str, str]:
    rules = validate_rules(rules_document)
    data = validate_data_map(data_document, rules)
    controller = data["controller"]
    selected = templates or {
        "politica-tratamiento.md": _template("politica-tratamiento.md.tpl"),
        "registro-tratamientos.md": _template("registro-tratamientos.md.tpl"),
        "retencion.md": _template("retencion.md.tpl"),
    }
    if set(selected) != set(rules["documents"]):
        raise PrivacyError("plantillas/documentos no coinciden con reglas")
    common = {
        "CONTROLLER_NAME": controller["name"],
        "CONTROLLER_IDENTIFIER": controller["identifier"],
        "CONTROLLER_ADDRESS": controller["address"],
        "RIGHTS_EMAIL": controller["rights_email"],
        "PROJECT": data["project"],
    }
    return {
        "politica-tratamiento.md": _render(
            selected["politica-tratamiento.md"],
            {**common, "TREATMENTS_TABLE": _table_rows(data)},
        ),
        "registro-tratamientos.md": _render(
            selected["registro-tratamientos.md"],
            {**common, "REGISTER_SECTIONS": _register_sections(data)},
        ),
        "retencion.md": _render(
            selected["retencion.md"],
            {**common, "RETENTION_ROWS": _retention_rows(data, rules)},
        ),
    }
