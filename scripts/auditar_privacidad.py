#!/usr/bin/env python3
"""Auditoría periódica de privacidad sin exponer valores personales."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

from scripts.privacidad_gate import material_change_reasons, scan_added_code
from scripts.privacidad_kit import PrivacyError, load_data_map, load_rules, validate_data_map
from seguridad.puertas_humanas import GateValidationError, validate_gate


SOURCE_SUFFIXES = (
    ".php", ".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".twig", ".html"
)
IGNORED_DIRS = {
    ".git", ".factory", "vendor", "node_modules", "tests", "docs", "legal",
    "var", "storage", "cache", "dist", "build",
}
MAX_FILES = 5_000
MAX_FILE_BYTES = 512_000
MAX_TOTAL_BYTES = 20_000_000
SHA = re.compile(r"[0-9a-f]{40}\Z")
SAFE_PATH = re.compile(r"[A-Za-z0-9._/-]{1,240}\Z")
AUDIT_MARKER = "<!-- factory-privacy-audit -->"
MATERIAL_MARKER = "<!-- factory-privacy-material -->"


class PrivacyAuditError(ValueError):
    """Fallo seguro; solo puede incluir rutas y códigos controlados."""


def _source_path(path: str) -> bool:
    return path.endswith(SOURCE_SUFFIXES) or path.endswith(".blade.php")


def collect_sources(root: Path) -> dict[str, str]:
    """Lee solo fuentes UTF-8 acotadas dentro del checkout sin seguir symlinks."""
    try:
        base = root.resolve(strict=True)
    except OSError as exc:
        raise PrivacyAuditError("checkout no verificable") from exc
    if not base.is_dir():
        raise PrivacyAuditError("checkout no es un directorio")

    result: dict[str, str] = {}
    total = 0

    def walk_error(exc: OSError) -> None:
        raise PrivacyAuditError("no fue posible recorrer las fuentes") from exc

    for directory, dirnames, filenames in os.walk(
        base,
        topdown=True,
        onerror=walk_error,
        followlinks=False,
    ):
        current = Path(directory)
        safe_dirs: list[str] = []
        for name in sorted(dirnames):
            if name in IGNORED_DIRS:
                continue
            candidate = current / name
            if candidate.is_symlink():
                raise PrivacyAuditError("directorio simbólico no auditable")
            safe_dirs.append(name)
        dirnames[:] = safe_dirs

        for name in sorted(filenames):
            path = current / name
            try:
                relative_path = path.relative_to(base)
            except ValueError as exc:
                raise PrivacyAuditError("ruta fuera del checkout") from exc
            relative = relative_path.as_posix()
            if (
                not 1 <= len(relative) <= 240
                or any(part in {"", ".", ".."} for part in relative_path.parts)
                or any(char not in ALLOWED_PATH_CHARS for char in relative)
            ):
                raise PrivacyAuditError("ruta de fuente no canónica")
            if not _source_path(relative):
                continue
            if path.is_symlink():
                raise PrivacyAuditError("fuente simbólica no auditable")
            try:
                file_stat = path.stat(follow_symlinks=False)
            except OSError as exc:
                raise PrivacyAuditError("fuente no inspeccionable") from exc
            if not stat.S_ISREG(file_stat.st_mode):
                continue
            if file_stat.st_size > MAX_FILE_BYTES:
                raise PrivacyAuditError("fuente excede máximo")
            total += file_stat.st_size
            if total > MAX_TOTAL_BYTES:
                raise PrivacyAuditError("fuentes exceden tamaño total máximo")
            if len(result) >= MAX_FILES:
                raise PrivacyAuditError("repositorio excede cantidad máxima de fuentes")
            try:
                result[relative] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise PrivacyAuditError("fuente no UTF-8") from exc
    return result

def _declared(current: dict[str, Any]) -> tuple[set[str], set[str]]:
    fields: set[str] = set()
    providers: set[str] = set()
    for treatment in current["treatments"]:
        fields.update(treatment["fields"])
        providers.update(treatment["providers"])
    return fields, providers


def _observed_sources(
    sources: dict[str, str],
    rules: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    fields: dict[str, set[str]] = defaultdict(set)
    providers: dict[str, set[str]] = defaultdict(set)
    for path in sorted(sources):
        text = sources[path]
        pseudo_diff = "+++ b/" + path + "\n" + "\n".join(
            "+" + line for line in text.splitlines()
        )
        observed = scan_added_code(pseudo_diff, rules)
        for signal in observed["personal_signals"]:
            fields[signal].add(path)
        for provider in observed["provider_signals"]:
            providers[provider].add(path)
    return fields, providers


def _findings(
    observed: dict[str, set[str]],
    declared: set[str],
) -> list[dict[str, Any]]:
    return [
        {"signal": signal, "paths": sorted(paths)}
        for signal, paths in sorted(observed.items())
        if signal not in declared
    ]


def build_legal_gate_body(project: str, reasons: list[str]) -> str:
    """Construye una puerta legal válida sin incluir contenido libre del código."""
    if not reasons:
        raise PrivacyAuditError("no hay cambio material para puerta legal")
    context = (
        f"{project}: la auditoría detectó {len(reasons)} cambio(s) material(es) "
        "de privacidad que requieren decisión jurídica humana."
    )
    gate = {
        "category": "legal",
        "context": context,
        "options": [
            {
                "id": "A",
                "label": "Solicitar revisión jurídica antes de aprobar la documentación",
            },
            {
                "id": "B",
                "label": "Continuar en construcción manteniendo documented_not_legally_approved",
            },
        ],
        "recommendation": "A",
        "safe_default": "B",
    }
    try:
        validated = validate_gate(gate)
    except GateValidationError as exc:
        raise PrivacyAuditError("puerta legal interna inválida") from exc
    encoded = json.dumps(validated, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    reason_lines = "\n".join(f"- `{reason}`" for reason in reasons)
    return (
        f"{MATERIAL_MARKER}\n"
        "## Cambio material de privacidad\n\n"
        f"Producto: `{project}`\n\n"
        "Motivos estructurados:\n"
        f"{reason_lines}\n\n"
        "La documentación permanece en estado "
        "`documented_not_legally_approved` hasta una decisión humana.\n\n"
        f"<!-- factory-human-gate {encoded} -->\n"
    )


def render_audit_issue_body(report: dict[str, Any]) -> str:
    """Renderiza hallazgos sanitizados para un Issue técnico idempotente."""
    lines = [
        AUDIT_MARKER,
        "## Auditoría automática de privacidad",
        "",
        f"Producto: `{report['project']}`",
        f"Estado: `{report['status']}`",
        "",
    ]
    for label, key in (
        ("Señales personales no documentadas", "undocumented_fields"),
        ("Proveedores no documentados", "undocumented_providers"),
    ):
        lines.extend([f"### {label}", ""])
        rows = report[key]
        if not rows:
            lines.append("- ninguno")
        else:
            for row in rows:
                paths = ", ".join(f"`{path}`" for path in row["paths"])
                lines.append(f"- `{row['signal']}`: {paths}")
        lines.append("")
    lines.append(
        "El reporte contiene únicamente identificadores controlados y rutas; "
        "nunca valores observados en los archivos."
    )
    return "\n".join(lines).rstrip() + "\n"


def audit_sources(
    *,
    sources: dict[str, str],
    current_document: object,
    previous_document: object | None = None,
    rules_document: object | None = None,
) -> dict[str, Any]:
    """Compara código y mapa de datos con salida determinista y sanitizada."""
    rules = load_rules() if rules_document is None else rules_document
    current = validate_data_map(current_document, rules)
    declared_fields, declared_providers = _declared(current)
    observed_fields, observed_providers = _observed_sources(sources, rules)
    field_findings = _findings(observed_fields, declared_fields)
    provider_findings = _findings(observed_providers, declared_providers)
    reasons = material_change_reasons(previous_document, current, rules)

    report: dict[str, Any] = {
        "project": current["project"],
        "status": "review_required" if field_findings or provider_findings else "clean",
        "undocumented_fields": field_findings,
        "undocumented_providers": provider_findings,
        "legal_gate_required": bool(reasons),
        "material_reasons": reasons,
    }
    report["audit_issue_body"] = render_audit_issue_body(report)
    report["legal_gate_body"] = (
        build_legal_gate_body(current["project"], reasons) if reasons else ""
    )
    return report


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrivacyAuditError("no fue posible consultar git") from exc


def _git_show(root: Path, sha: str) -> object | None:
    if not sha:
        return None
    if not SHA.fullmatch(sha):
        raise PrivacyAuditError("previous SHA inválido")

    listing = _run_git(root, ["ls-tree", "--name-only", sha, "--", "datos.yml"])
    if listing.returncode != 0:
        raise PrivacyAuditError("referencia histórica no verificable")
    if listing.stdout.strip() == "":
        return None
    if listing.stdout.strip() != "datos.yml":
        raise PrivacyAuditError("referencia histórica ambigua")

    completed = _run_git(root, ["show", f"{sha}:datos.yml"])
    if completed.returncode != 0:
        raise PrivacyAuditError("no fue posible leer datos.yml histórico")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PrivacyAuditError("datos.yml histórico inválido") from exc

def evaluate_repository(root: Path, previous_sha: str = "") -> dict[str, Any]:
    current = load_data_map(Path("datos.yml"), root=root)
    previous = _git_show(root, previous_sha)
    return audit_sources(
        sources=collect_sources(root),
        current_document=current,
        previous_document=previous,
        rules_document=load_rules(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-sha", default="")
    args = parser.parse_args()
    try:
        report = evaluate_repository(Path.cwd().resolve(), args.previous_sha)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    except PrivacyAuditError as exc:
        parser.exit(1, f"error: {exc}\n")
    except PrivacyError:
        parser.exit(1, "error: auditoría de privacidad inválida\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
