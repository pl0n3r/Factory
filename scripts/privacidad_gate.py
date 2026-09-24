#!/usr/bin/env python3
"""Gate de privacidad: detecta drift sin emitir valores personales del código."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from scripts.privacidad_kit import (
    PrivacyError,
    generate_documents,
    load_rules,
    validate_data_map,
)
from scripts.safe_io import SafeIOError, read_repo_text


DATA_MAP = Path("datos.yml")
DOCS_ROOT = Path("docs/privacidad")
SOURCE_SUFFIXES = (
    ".php", ".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".twig", ".html"
)
IGNORED_PREFIXES = (
    "tests/", "docs/", ".github/", "vendor/", "node_modules/", "legal/"
)
AMBIGUOUS_SIGNALS = {"name", "location", "document", "health"}
SHA = re.compile(r"[0-9a-f]{40}\Z")


class PrivacyGateError(ValueError):
    """Fallo seguro del gate; nunca incorpora líneas crudas del diff."""


def _code_path(path: str) -> bool:
    if not path or path.startswith(IGNORED_PREFIXES):
        return False
    return path.endswith(SOURCE_SUFFIXES) or path.endswith(".blade.php")


def _signal_present(signal: str, line: str) -> bool:
    """Detecta señales sensibles conservando contexto para nombres ambiguos."""
    if signal in AMBIGUOUS_SIGNALS:
        quoted = (
            f'"{signal}"' in line
            or f"'{signal}'" in line
            or re.search(rf"\bname\s*=\s*['\"]{re.escape(signal)}['\"]", line)
        )
        if quoted:
            return True
        if signal == "health":
            object_field = re.search(
                rf"(?:{{|,)\s*{re.escape(signal)}\s*:",
                line,
            )
            property_access = re.search(
                rf"(?:\.|\?->|->)\s*{re.escape(signal)}(?![a-z0-9_])",
                line,
            )
            return bool(object_field or property_access)
        return False
    return re.search(
        rf"(?<![a-z0-9_]){re.escape(signal)}(?![a-z0-9_])",
        line,
    ) is not None


def scan_added_code(diff_text: str, rules: dict[str, Any]) -> dict[str, list[str]]:
    """Devuelve solo identificadores de señales; descarta el contenido observado."""
    if not isinstance(diff_text, str) or len(diff_text.encode("utf-8")) > 8_000_000:
        raise PrivacyGateError("diff ausente o excesivo")
    current_path = ""
    personal: set[str] = set()
    providers: set[str] = set()
    categories = rules["categories"]
    provider_signals = rules["provider_signals"]

    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            current_path = raw[6:] if raw.startswith("+++ b/") else ""
            continue
        if not current_path or not _code_path(current_path):
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue
        line = raw[1:].lower()
        for category in categories.values():
            for signal in category["signals"]:
                if _signal_present(signal, line):
                    personal.add(signal)
        for provider, domains in provider_signals.items():
            if any(domain in line for domain in domains):
                providers.add(provider)

    return {
        "personal_signals": sorted(personal),
        "provider_signals": sorted(providers),
    }


def _declared(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    fields: set[str] = set()
    providers: set[str] = set()
    for treatment in data["treatments"]:
        fields.update(treatment["fields"])
        providers.update(treatment["providers"])
    return fields, providers


def material_change_reasons(
    previous_document: object | None,
    current_document: object,
    rules: dict[str, Any],
) -> list[str]:
    """Clasifica cambios materiales usando solo IDs/códigos controlados."""
    current = validate_data_map(current_document, rules)
    if previous_document is None:
        previous_rows: dict[str, dict[str, Any]] = {}
    else:
        previous = validate_data_map(previous_document, rules)
        previous_rows = {row["id"]: row for row in previous["treatments"]}

    reasons: set[str] = set()
    for row in current["treatments"]:
        old = previous_rows.get(row["id"])
        current_sensitive = bool(rules["categories"][row["category"]]["sensitive"])
        if old is None:
            reasons.add(f"{row['id']}:purpose")
            if current_sensitive:
                reasons.add(f"{row['id']}:sensitive")
            if row["providers"]:
                reasons.add(f"{row['id']}:new_provider")
            continue
        if old["purpose"] != row["purpose"]:
            reasons.add(f"{row['id']}:purpose")
        old_sensitive = bool(rules["categories"][old["category"]]["sensitive"])
        if current_sensitive and not old_sensitive:
            reasons.add(f"{row['id']}:sensitive")
        if set(row["providers"]) - set(old["providers"]):
            reasons.add(f"{row['id']}:new_provider")
    return sorted(reasons)


def evaluate_change(
    *,
    diff_text: str,
    changed_files: list[str],
    current_document: object,
    documents: dict[str, str],
    previous_document: object | None = None,
    rules_document: object | None = None,
) -> dict[str, Any]:
    """Valida documentación y devuelve metadatos sanitizados del resultado."""
    rules = load_rules() if rules_document is None else rules_document
    current = validate_data_map(current_document, rules)
    observed = scan_added_code(diff_text, rules)
    declared_fields, declared_providers = _declared(current)

    missing_fields = sorted(set(observed["personal_signals"]) - declared_fields)
    if missing_fields:
        raise PrivacyGateError(
            "señales personales no documentadas en datos.yml: "
            + ", ".join(missing_fields)
        )

    missing_providers = sorted(set(observed["provider_signals"]) - declared_providers)
    if missing_providers:
        raise PrivacyGateError(
            "proveedores no documentados en datos.yml: "
            + ", ".join(missing_providers)
        )

    expected = generate_documents(rules, current)
    document_names = tuple(expected)
    if set(documents) != set(document_names):
        raise PrivacyGateError("documentos de privacidad incompletos o adicionales")
    drift = sorted(
        name for name in document_names if documents[name] != expected[name]
    )
    if drift:
        raise PrivacyGateError(
            "documentos generados desactualizados: " + ", ".join(drift)
        )

    reasons = (
        material_change_reasons(previous_document, current, rules)
        if DATA_MAP.as_posix() in set(changed_files)
        else []
    )
    return {
        "status": "documented_not_legally_approved",
        "personal_signals": observed["personal_signals"],
        "provider_signals": observed["provider_signals"],
        "legal_gate_required": bool(reasons),
        "material_reasons": reasons,
    }


def _git(root: Path, args: list[str], *, allow_failure: bool = False) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrivacyGateError("no fue posible consultar git") from exc
    if completed.returncode != 0:
        if allow_failure:
            return None
        raise PrivacyGateError("git no pudo construir la evidencia requerida")
    return completed.stdout


def _json_text(text: str, label: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PrivacyGateError(f"{label}: JSON/YAML canónico inválido") from exc


def _repo_text(root: Path, path: Path) -> str:
    try:
        return read_repo_text(path, root=root, max_bytes=512_000)
    except SafeIOError as exc:
        raise PrivacyGateError("archivo canónico de privacidad ausente o inválido") from exc


def evaluate_repository(root: Path, base_sha: str) -> dict[str, Any]:
    if not SHA.fullmatch(base_sha):
        raise PrivacyGateError("base SHA inválido")
    rules = load_rules()
    current_text = _repo_text(root, DATA_MAP)
    current = _json_text(current_text, "datos")
    changed = _git(root, ["diff", "--name-only", base_sha, "HEAD", "--"])
    diff = _git(root, ["diff", "--unified=0", base_sha, "HEAD", "--"])
    assert changed is not None and diff is not None

    previous_text = _git(
        root, ["show", f"{base_sha}:{DATA_MAP.as_posix()}"], allow_failure=True
    )
    previous = None if previous_text is None else _json_text(previous_text, "datos base")
    documents = {
        name: _repo_text(root, DOCS_ROOT / name)
        for name in rules["documents"]
    }
    return evaluate_change(
        diff_text=diff,
        changed_files=[line for line in changed.splitlines() if line],
        current_document=current,
        previous_document=previous,
        documents=documents,
        rules_document=rules,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    try:
        report = evaluate_repository(Path.cwd().resolve(), args.base_sha)
        print(json.dumps(report, sort_keys=True))
    except (PrivacyError, PrivacyGateError, OSError, TypeError) as exc:
        message = str(exc) if isinstance(exc, PrivacyGateError) else "evidencia de privacidad inválida"
        parser.exit(1, f"error: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
