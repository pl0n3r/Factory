#!/usr/bin/env python3
"""Clasifica y valida roles profesionales del kit Factory."""
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

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "agentes" / "roles" / "catalogo.json"
ROLES_DIR = ROOT / "agentes" / "roles"
REQUIRED_ROLES = {
    "ingenieria-software", "arquitectura", "dba", "infraestructura", "sre",
    "seguridad", "qa", "ux", "diseno-visual", "frontend", "producto",
    "marketing", "seo", "contenido", "datos-analitica", "legal-privacidad",
}
REQUIRED_HEADINGS = (
    "## Mentalidad y responsabilidades",
    "## Nunca haría",
    "## Checklist",
    "## Evidencia exigida",
    "## Referencias",
)
MAX_BODY = 120_000
MAX_CONTEXT = 500_000
MAX_FILES = 1_000
MAX_LABELS = 100
MAX_CATALOG_BYTES = 128_000
MAX_ROLE_BYTES = 64_000


class RoleError(ValueError):
    pass


def _repo_relative(path: Path) -> Path:
    if path.is_absolute():
        try:
            return path.relative_to(ROOT)
        except ValueError as exc:
            raise RoleError("Ruta fuera del checkout Factory.") from exc
    return path


def load_catalog(
    path: Path = CATALOG_PATH,
    roles_dir: Path = ROLES_DIR,
) -> dict[str, dict[str, str]]:
    try:
        raw = json.loads(
            read_repo_text(
                _repo_relative(path),
                root=ROOT,
                max_bytes=MAX_CATALOG_BYTES,
            )
        )
    except (SafeIOError, json.JSONDecodeError) as exc:
        raise RoleError("Catálogo de roles ilegible o inválido.") from exc
    if not isinstance(raw, list) or len(raw) != len(REQUIRED_ROLES):
        raise RoleError("El catálogo debe contener exactamente 16 roles.")

    roles_rel = _repo_relative(roles_dir)
    result: dict[str, dict[str, str]] = {}
    labels_es: set[str] = set()
    labels_en: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {
            "slug", "label_es", "label_en", "file"
        }:
            raise RoleError("Entrada de catálogo con esquema inválido.")
        if not all(isinstance(item[key], str) and item[key].strip() for key in item):
            raise RoleError("Entrada de catálogo vacía.")

        slug = item["slug"]
        if not re.fullmatch(r"[a-z0-9-]{2,40}", slug):
            raise RoleError("Slug de rol inválido.")
        expected_file = roles_rel / f"{slug}.md"
        if Path(item["file"]) != expected_file:
            raise RoleError("El archivo de rol no coincide con su slug canónico.")
        if (
            slug in result
            or item["label_es"] in labels_es
            or item["label_en"] in labels_en
        ):
            raise RoleError("Slug o etiqueta de rol duplicada.")
        if item["label_es"] != f"rol: {slug}":
            raise RoleError("Etiqueta ES no coincide con el slug.")

        try:
            content = read_repo_text(
                expected_file,
                root=ROOT,
                max_bytes=MAX_ROLE_BYTES,
            )
        except SafeIOError as exc:
            raise RoleError("Falta archivo de rol o no es seguro.") from exc
        for heading in REQUIRED_HEADINGS:
            if heading not in content:
                raise RoleError("Archivo de rol incompleto.")
        if len(parse_checklist(content)) < 3:
            raise RoleError("Cada rol requiere al menos tres items de checklist.")

        result[slug] = dict(item)
        labels_es.add(item["label_es"])
        labels_en.add(item["label_en"])

    if set(result) != REQUIRED_ROLES:
        raise RoleError("El catálogo debe contener exactamente los 16 roles requeridos.")
    return result


def parse_checklist(content: str) -> list[str]:
    try:
        section = content.split("## Checklist", 1)[1].split(
            "## Evidencia exigida", 1
        )[0]
    except IndexError as exc:
        raise RoleError("Checklist de rol ausente.") from exc
    items: list[str] = []
    for line in section.splitlines():
        match = re.fullmatch(r"- \[ \] (.+)", line.strip())
        if match:
            items.append(match.group(1).strip())
    return items


def parse_context(payload: str) -> dict[str, Any]:
    if not isinstance(payload, str) or len(payload) > MAX_CONTEXT:
        raise RoleError("Contexto JSON vacío o demasiado grande.")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RoleError("Contexto JSON inválido.") from exc
    if not isinstance(raw, dict):
        raise RoleError("Contexto debe ser objeto JSON.")

    body = raw.get("body") or ""
    title = raw.get("title") or ""
    labels = raw.get("labels") or []
    files = raw.get("files") or []
    if (
        not isinstance(body, str)
        or not isinstance(title, str)
        or len(body) > MAX_BODY
        or len(title) > 500
    ):
        raise RoleError("Título/body inválido o demasiado grande.")
    if (
        not isinstance(labels, list)
        or len(labels) > MAX_LABELS
        or not all(isinstance(value, str) and len(value) <= 100 for value in labels)
    ):
        raise RoleError("Labels inválidas.")
    if (
        not isinstance(files, list)
        or len(files) > MAX_FILES
        or not all(isinstance(value, str) and len(value) <= 500 for value in files)
    ):
        raise RoleError("Files inválidos.")
    return {"body": body, "title": title, "labels": labels, "files": files}


def classify(context: dict[str, Any]) -> tuple[list[str], set[str]]:
    roles: set[str] = set()
    risks: set[str] = set()
    labels = {value.lower() for value in context["labels"]}
    text = f"{context['title']}\n{context['body']}".lower()

    type_rules = {
        "tipo: producto": {"producto"},
        "type: product": {"producto"},
        "tipo: incidente": {"sre", "qa"},
        "type: incident": {"sre", "qa"},
        "tipo: error": {"ingenieria-software", "qa"},
        "type: bug": {"ingenieria-software", "qa"},
        "tipo: pruebas": {"qa"},
        "type: tests": {"qa"},
        "tipo: documentación": {"contenido"},
        "type: documentation": {"contenido"},
        "tipo: infraestructura": {"infraestructura", "sre"},
        "type: infrastructure": {"infraestructura", "sre"},
    }
    for label, mapped in type_rules.items():
        if label in labels:
            roles.update(mapped)

    for filename in context["files"]:
        path = filename.lower()
        if re.search(r"(^|/)(migrations?|schema|database|db)(/|\.|$)|\.sql$", path):
            roles.update({"dba", "qa"})
            risks.add("schema")
        if path.startswith(".github/workflows/") or re.search(
            r"(^|/)(deploy|ops|infra|terraform|docker)(/|\.|$)", path
        ):
            roles.update({"infraestructura", "sre", "seguridad"})
            risks.add("deploy")
        if re.search(
            r"(^|/)(security|auth|oauth|permissions?|secrets?)(/|\.|$)", path
        ):
            roles.update({"seguridad", "qa"})
            risks.add("security")
        if re.search(
            r"(^|/)(templates?|views?|frontend|public)(/|$)|\.(css|scss|tsx|jsx|vue|svelte)$",
            path,
        ):
            roles.update({"frontend", "ux", "qa"})
            risks.add("public-ux")
        if re.search(r"(^|/)(seo|sitemap|robots)(/|\.|$)", path):
            roles.update({"seo", "contenido"})
        if re.search(r"(^|/)(metricas|analytics|data|reports?)(/|\.|$)", path):
            roles.update({"datos-analitica", "qa"})
        if re.search(r"(^|/)(marketing|campaigns?|copy)(/|\.|$)", path):
            roles.update({"marketing", "contenido"})
        if re.search(r"(^|/)(legal|privacy|privacidad)(/|\.|$)", path):
            roles.add("legal-privacidad")
        if re.search(r"(^|/)(adr|architecture|arquitectura)(/|\.|$)", path):
            roles.add("arquitectura")
        if path.endswith((".py", ".php", ".js", ".ts", ".java", ".go", ".rb")):
            roles.update({"ingenieria-software", "qa"})

    keyword_rules = (
        (r"\bseo\b|sitemap|robots\.txt|canonical", {"seo", "contenido"}),
        (r"marketing|campaña|campaign|conversi[oó]n|cta", {"marketing", "contenido"}),
        (r"privacidad|privacy|datos personales|retenci[oó]n", {"legal-privacidad"}),
        (r"arquitectura|architecture|adr\b", {"arquitectura"}),
        (r"migraci[oó]n|schema|índice|index\b|locking", {"dba"}),
        (r"accesibilidad|wcag|usabilidad|ux\b", {"ux"}),
    )
    for pattern, mapped in keyword_rules:
        if re.search(pattern, text):
            roles.update(mapped)

    if not roles:
        roles.update({"ingenieria-software", "qa"})
    return sorted(roles), risks


def declared_roles(body: str) -> list[str]:
    match = re.search(r"(?im)^Rol\(es\):\s*(.+)$", body)
    if not match:
        match = re.search(r"(?im)^Roles:\s*(.+)$", body)
    if not match:
        return []
    return [
        value.strip().strip(chr(96))
        for value in re.split(r"[,;+]", match.group(1))
        if value.strip()
    ]


def single_role(body: str, key: str) -> str | None:
    match = re.search(
        rf"(?im)^{re.escape(key)}:\s*([a-z0-9-]+)\s*$",
        body,
    )
    return match.group(1) if match else None


def checked_items(body: str) -> set[str]:
    return {
        match.group(1).strip()
        for line in body.splitlines()
        if (match := re.fullmatch(r"\s*- \[[xX]\] (.+)", line))
    }


def cross_review_allowed(risks: set[str]) -> set[str]:
    mapping = {
        "schema": {"sre", "seguridad", "arquitectura"},
        "deploy": {"seguridad", "qa", "arquitectura"},
        "security": {"qa", "arquitectura", "sre"},
        "public-ux": {"qa", "seguridad", "diseno-visual"},
    }
    allowed: set[str] = set()
    for risk in risks:
        allowed.update(mapping.get(risk, set()))
    return allowed


def validate_pr(
    context: dict[str, Any],
    catalog: dict[str, dict[str, str]],
    roles_dir: Path,
    language: str,
) -> dict[str, Any]:
    body = context["body"]
    suggested, risks = classify(context)
    declared = declared_roles(body)
    if not declared:
        raise RoleError("El PR debe declarar Rol(es): ...")
    unknown = set(declared) - set(catalog)
    if unknown:
        raise RoleError("El PR declara roles desconocidos.")
    missing = set(suggested) - set(declared)
    if missing:
        raise RoleError(
            "Faltan roles requeridos por el cambio: " + ", ".join(sorted(missing))
        )

    label_field = "label_es" if language == "es" else "label_en"
    labels = set(context["labels"])
    missing_labels = {catalog[role][label_field] for role in declared} - labels
    if missing_labels:
        raise RoleError(
            "Faltan etiquetas de rol en el PR: " + ", ".join(sorted(missing_labels))
        )

    checked = checked_items(body)
    for role in declared:
        content = read_repo_text(
            _repo_relative(roles_dir) / f"{role}.md",
            root=ROOT,
            max_bytes=MAX_ROLE_BYTES,
        )
        missing_checks = set(parse_checklist(content)) - checked
        if missing_checks:
            raise RoleError(f"Checklist incompleto para {role}.")

    primary = single_role(body, "Rol primario")
    if primary is None or primary not in declared:
        raise RoleError("Rol primario debe existir y estar incluido en Rol(es).")
    if risks:
        reviewer = single_role(body, "Revisión cruzada")
        allowed = cross_review_allowed(risks)
        if (
            reviewer is None
            or reviewer == primary
            or reviewer not in declared
            or reviewer not in allowed
        ):
            raise RoleError(
                "Cambio de riesgo requiere Revisión cruzada con rol permitido distinto al primario."
            )
    return {"declared": declared, "required": suggested, "risks": sorted(risks)}


def labels_for(
    catalog: dict[str, dict[str, str]],
    language: str,
) -> list[str]:
    field = "label_es" if language == "es" else "label_en"
    return [catalog[slug][field] for slug in sorted(catalog)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("validate-catalog", "suggest", "validate-pr", "labels"),
    )
    parser.add_argument("--language", choices=("es", "en"), default="es")
    args = parser.parse_args()

    try:
        catalog = load_catalog()
        if args.command == "validate-catalog":
            print(json.dumps({"roles": len(catalog)}, sort_keys=True))
            return 0
        if args.command == "labels":
            print(
                json.dumps(
                    labels_for(catalog, args.language),
                    ensure_ascii=False,
                )
            )
            return 0

        payload = sys.stdin.read(MAX_CONTEXT + 1)
        if len(payload) > MAX_CONTEXT:
            raise RoleError("Contexto JSON demasiado grande.")
        context = parse_context(payload)

        if args.command == "suggest":
            roles, risks = classify(context)
            field = "label_es" if args.language == "es" else "label_en"
            print(
                json.dumps(
                    {
                        "roles": roles,
                        "labels": [catalog[role][field] for role in roles],
                        "risks": sorted(risks),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0

        print(
            json.dumps(
                validate_pr(context, catalog, ROLES_DIR, args.language),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (RoleError, SafeIOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
