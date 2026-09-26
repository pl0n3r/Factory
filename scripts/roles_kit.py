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
    "## Experiencia simulada y especialidades",
    "## Investigación inicial",
    "## Heurísticas y trade-offs",
    "## Señales de excelencia",
    "## Red flags y colaboración",
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

EXTENSION_SIGNALS = {
    "mobile-engineering": r"\bandroid\b|\bios\b|\bmobile\b|\bswift\b|\bkotlin\b|\.kt\b",
    "ml-engineering": r"\bmachine learning\b|\bmlops\b|\bpytorch\b|\btensorflow\b",
}


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
    if not isinstance(raw, list) or len(raw) < len(REQUIRED_ROLES):
        raise RoleError("El catálogo debe contener al menos los 16 roles base.")

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

    if not REQUIRED_ROLES <= set(result):
        raise RoleError("El catálogo debe conservar todos los roles base requeridos.")
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


def _path_tokens(path: str) -> set[str]:
    tokens: set[str] = set()
    for segment in path.lower().split("/"):
        if not segment:
            continue
        tokens.add(segment)
        stem = segment.rsplit(".", 1)[0]
        if stem:
            tokens.add(stem)
    return tokens


def _classify_file(path: str) -> tuple[set[str], set[str]]:
    roles: set[str] = set()
    risks: set[str] = set()
    lower = path.lower()
    tokens = _path_tokens(lower)

    if tokens & {"migration", "migrations", "schema", "database", "db"} or lower.endswith(".sql"):
        roles.update({"dba", "qa"})
        risks.add("schema")
    if lower.startswith(".github/workflows/") or tokens & {
        "deploy", "ops", "infra", "terraform", "docker"
    }:
        roles.update({"infraestructura", "sre", "seguridad"})
        risks.add("deploy")
    if tokens & {
        "security", "auth", "oauth", "permission", "permissions",
        "secret", "secrets",
    }:
        roles.update({"seguridad", "qa"})
        risks.add("security")
    if (
        tokens & {"template", "templates", "view", "views", "frontend", "public"}
        or lower.endswith((".css", ".scss", ".tsx", ".jsx", ".vue", ".svelte"))
    ):
        roles.update({"frontend", "ux", "qa"})
        risks.add("public-ux")
    if tokens & {"seo", "sitemap", "robots"}:
        roles.update({"seo", "contenido"})
    if tokens & {"metricas", "analytics", "data", "report", "reports"}:
        roles.update({"datos-analitica", "qa"})
    if tokens & {"marketing", "campaign", "campaigns", "copy"}:
        roles.update({"marketing", "contenido"})
    if tokens & {"legal", "privacy", "privacidad"}:
        roles.add("legal-privacidad")
    if tokens & {"adr", "architecture", "arquitectura"}:
        roles.add("arquitectura")
    if lower.endswith((".py", ".php", ".js", ".ts", ".java", ".go", ".rb")):
        roles.update({"ingenieria-software", "qa"})
    return roles, risks


def _roles_from_type_labels(labels: set[str]) -> set[str]:
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
    roles: set[str] = set()
    for label, mapped in type_rules.items():
        if label in labels:
            roles.update(mapped)
    return roles


def _positive_role_text(text: str) -> str:
    """Evita que negaciones explícitas activen capacidades no aplicables."""
    patterns = (
        r"\bsin\s+(?:nuevas?\s+)?migraciones?(?:\s+de\s+schema)?\b",
        r"\bno\s+(?:hay|incluye|requiere|usa)\s+(?:nuevas?\s+)?migraciones?(?:\s+de\s+schema)?\b",
        r"\bsin\s+(?:cambios?\s+de\s+)?schema\b",
        r"\bno\s+(?:hay|incluye|requiere|usa)\s+(?:cambios?\s+de\s+)?schema\b",
        r"\bsin\s+machine learning\b",
        r"\bno\s+(?:hay|incluye|requiere|usa)\s+machine learning\b",
        r"\bsin\s+(?:android|ios|mobile|kotlin|swift)\b",
        r"\bno\s+(?:hay|incluye|requiere|usa)\s+(?:android|ios|mobile|kotlin|swift)\b",
    )
    value = text
    for pattern in patterns:
        value = re.sub(pattern, "", value)
    return value


def _roles_from_text(text: str) -> set[str]:
    text = _positive_role_text(text)
    keyword_rules = (
        (r"\bseo\b|sitemap|robots\.txt|canonical", {"seo", "contenido"}),
        (r"marketing|campaña|campaign|conversi[oó]n|cta", {"marketing", "contenido"}),
        (r"privacidad|privacy|datos personales|retenci[oó]n", {"legal-privacidad"}),
        (r"arquitectura|architecture|adr\b", {"arquitectura"}),
        (r"migraci[oó]n|schema|índice|index\b|locking", {"dba"}),
        (r"accesibilidad|wcag|usabilidad|ux\b", {"ux"}),
    )
    roles: set[str] = set()
    for pattern, mapped in keyword_rules:
        if re.search(pattern, text):
            roles.update(mapped)
    return roles


def _roles_from_catalog_extensions(
    context: dict[str, Any],
    catalog: dict[str, dict[str, str]],
) -> set[str]:
    """Selecciona extensiones de catálogo por señales de capability verificables."""
    text = _positive_role_text(
        " ".join([context["title"], context["body"], *context["files"]]).lower()
    )
    roles: set[str] = set()
    for slug in sorted(set(catalog) - REQUIRED_ROLES):
        pattern = EXTENSION_SIGNALS.get(slug)
        if pattern and re.search(pattern, text):
            roles.add(slug)
            continue
        meaningful = [
            token for token in slug.split("-")
            if token not in {"engineering", "engineer", "role"}
        ]
        if meaningful and all(
            re.search(rf"\b{re.escape(token)}\b", text)
            for token in meaningful
        ):
            roles.add(slug)
    return roles


def classify(
    context: dict[str, Any],
    catalog: dict[str, dict[str, str]] | None = None,
) -> tuple[list[str], set[str]]:
    labels = {value.lower() for value in context["labels"]}
    roles = _roles_from_type_labels(labels)
    risks: set[str] = set()

    for filename in context["files"]:
        file_roles, file_risks = _classify_file(filename)
        roles.update(file_roles)
        risks.update(file_risks)

    text = f"{context['title']}\n{context['body']}".lower()
    roles.update(_roles_from_text(text))
    if catalog is not None:
        roles.update(_roles_from_catalog_extensions(context, catalog))

    if not roles:
        roles.update({"ingenieria-software", "qa"})
    return sorted(roles), risks



def _stack_signals(context: dict[str, Any]) -> list[str]:
    haystack = " ".join([context["title"], context["body"], *context["files"]]).lower()
    rules = (
        ("php", r"\bphp\b"), ("symfony", r"\bsymfony\b"),
        ("laravel", r"\blaravel\b"), ("typescript", r"\btypescript\b|\.tsx?\b"),
        ("node", r"\bnode(?:\.js)?\b|package\.json"), ("mariadb", r"\bmariadb\b"),
        ("mysql", r"\bmysql\b"), ("github-actions", r"\.github/workflows|github actions"),
        ("hostinger", r"\bhostinger\b"),
    )
    return [name for name, pattern in rules if re.search(pattern, haystack)]


def compile_team(context: dict[str, Any], catalog: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Compone un equipo contextual y deja trazabilidad de las señales usadas."""
    roles, risks = classify(context, catalog)
    known = [role for role in roles if role in catalog]
    preference = ("producto", "arquitectura", "ingenieria-software", "infraestructura", "sre", "seguridad", "dba", "frontend", "qa")
    primary = next((role for role in preference if role in known), known[0])
    support = [role for role in known if role != primary]
    allowed_review = cross_review_allowed(risks)
    review = next((role for role in support if role in allowed_review), None)
    if risks and review is None:
        reviewer_preference = (
            "arquitectura", "seguridad", "sre", "qa", "diseno-visual"
        )
        review = next(
            (
                role for role in reviewer_preference
                if role in allowed_review and role in catalog and role != primary
            ),
            None,
        )
        if review is not None and review not in known:
            known.append(review)
            support.append(review)
    stacks = _stack_signals(context)
    contextual_profiles: list[str] = []
    if "ingenieria-software" in known and stacks:
        contextual_profiles.append(f"Staff {'/'.join(stacks[:2])} Engineer")
    if "dba" in known and any(x in stacks for x in ("mariadb", "mysql")):
        contextual_profiles.append("MariaDB/MySQL Performance DBA")
    if "sre" in known and "hostinger" in stacks:
        contextual_profiles.append("Hostinger SRE")
    if "seguridad" in known:
        contextual_profiles.append("Application Security Reviewer")
    return {"primary": primary, "support": support, "review": review, "roles": known, "risks": sorted(risks), "stacks": stacks, "contextual_profiles": contextual_profiles, "trace": {"files": list(context["files"]), "labels": list(context["labels"]), "signals": stacks}}


CANDIDATE_REQUIRED_FIELDS = {"slug", "title", "seniority", "domains", "stacks", "heuristics", "checklist", "evidence", "trigger"}


def validate_role_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_REQUIRED_FIELDS:
        raise RoleError("Candidato de rol con esquema inválido.")
    slug = candidate["slug"]
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]{2,40}", slug):
        raise RoleError("Slug de candidato inválido.")
    for field in ("title", "seniority", "trigger"):
        if not isinstance(candidate[field], str) or not candidate[field].strip():
            raise RoleError(f"Campo {field} de candidato vacío.")
    for field in ("domains", "stacks", "heuristics", "checklist", "evidence"):
        value = candidate[field]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise RoleError(f"Campo {field} de candidato inválido.")
    return candidate


def propose_role_candidate(context: dict[str, Any], catalog: dict[str, dict[str, str]]) -> dict[str, Any] | None:
    """Propone una capacidad faltante solo ante señales técnicas positivas."""
    text = _positive_role_text(
        " ".join([context["title"], context["body"], *context["files"]]).lower()
    )
    metadata = {
        "mobile-engineering": ("Staff Mobile Engineer", ["mobile applications"], ["Kotlin/Android", "Swift/iOS"]),
        "ml-engineering": ("Staff ML Engineer", ["machine learning systems"], ["Python", "MLOps"]),
    }
    for slug, pattern in EXTENSION_SIGNALS.items():
        title, domains, stacks = metadata[slug]
        if slug not in catalog and re.search(pattern, text):
            return validate_role_candidate({
                "slug": slug, "title": title, "seniority": "Staff-level simulated expertise",
                "domains": domains, "stacks": stacks,
                "heuristics": ["Preferir contratos observables y reversibles.", "Separar constraints de plataforma de lógica de producto."],
                "checklist": ["Riesgos específicos de plataforma cubiertos.", "Pruebas en target representativo.", "Rollback y compatibilidad definidos."],
                "evidence": ["Pruebas reproducibles del target.", "Trade-offs y límites documentados."],
                "trigger": f"Señal objetiva: {pattern}",
            })
    return None


def register_role_candidate(
    registry: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Registra un candidato validado separado del catálogo de roles utilizables."""
    value = validate_role_candidate(candidate)
    slug = value["slug"]
    if slug in registry:
        raise RoleError("El candidato ya existe en el registro.")
    result = dict(registry)
    result[slug] = dict(value)
    return result


def _declaration_value(body: str, keys: set[str]) -> str | None:
    normalized_keys = {key.casefold() for key in keys}
    for line in body.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip().casefold() in normalized_keys:
            stripped = value.strip()
            return stripped or None
    return None


def declared_roles(body: str) -> list[str]:
    value = _declaration_value(body, {"Rol(es)", "Roles"})
    if value is None:
        return []
    return [
        item.strip().strip(chr(96))
        for item in re.split(r"[,;+]", value)
        if item.strip()
    ]


def single_role(body: str, key: str) -> str | None:
    value = _declaration_value(body, {key})
    if value is None or not re.fullmatch(r"[a-z0-9-]+", value):
        return None
    return value

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
    suggested, risks = classify(context, catalog)
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
            roles, risks = classify(context, catalog)
            field = "label_es" if args.language == "es" else "label_en"
            print(
                json.dumps(
                    {
                        "roles": roles,
                        "labels": [catalog[role][field] for role in roles],
                        "risks": sorted(risks),
                        "team": compile_team(context, catalog),
                        "role_candidate": propose_role_candidate(context, catalog),
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
