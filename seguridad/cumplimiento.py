"""Verificador de evidencia, NO dictamen jurídico ni compatibilidad de licencias."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re


class ComplianceError(ValueError):
    """Fallo seguro sin incorporar texto arbitrario de los manifiestos."""


PROJECTS = frozenset({"pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal"})
REQUIRED_EVIDENCE = frozenset({
    "privacy_policy", "terms", "processing_register", "rights_channel",
    "retention_schedule", "vendor_review", "legal_review",
})
REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#-]{5,159}\Z")
SLUG = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
PKG = re.compile(r"(?:@?[-a-z0-9_.]+/)?[-a-z0-9_.]+\Z", re.I)
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_:-]{0,79}\Z")
LICENSE = re.compile(r"[A-Za-z0-9.+():-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+():-]+)*\Z")
UNDETERMINED = frozenset({"NOASSERTION", "NONE", "UNKNOWN", "UNLICENSED"})


def _reference(value: object, label: str) -> None:
    if not isinstance(value, str) or not REF.fullmatch(value):
        raise ComplianceError(f"{label}: referencia de evidencia inválida")


def _date(value: object, *, now: datetime) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ComplianceError("fecha de revisión debe usar UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        timestamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ComplianceError("fecha de revisión inválida") from exc
    if timestamp > now or timestamp < now - timedelta(days=365):
        raise ComplianceError("evidencia de revisión futura o desactualizada")


def validate_privacy(record: object, *, now: datetime | None = None) -> str:
    """Exige trazabilidad documental sin almacenar nombres ni datos de titulares."""
    if not isinstance(record, dict) or set(record) != {"version", "project", "scope", "purpose", "data_categories", "consent_or_exception", "evidence", "reviewed_at"}:
        raise ComplianceError("campos de checklist incompletos o adicionales")
    if type(record["version"]) is not int or record["version"] != 1:
        raise ComplianceError("versión de checklist no admitida")
    project = record["project"]
    if not isinstance(project, str) or project not in PROJECTS:
        raise ComplianceError("producto no admitido")
    for field in ("scope", "purpose"):
        if not isinstance(record[field], str) or not SLUG.fullmatch(record[field]):
            raise ComplianceError(f"{field}: se exige código controlado, no texto libre")
    categories = record["data_categories"]
    if not isinstance(categories, list) or not categories or len(categories) > 12 or len(set(map(str, categories))) != len(categories):
        raise ComplianceError("categorías incompletas o repetidas")
    if any(not isinstance(cat, str) or not SLUG.fullmatch(cat) for cat in categories):
        raise ComplianceError("categoría inválida")
    if "none" in categories and len(categories) != 1:
        raise ComplianceError("none no puede mezclarse con datos personales")
    if record["consent_or_exception"] not in ("consent_documented", "exception_for_legal_review", "no_personal_data"):
        raise ComplianceError("fundamento documental no identificado")
    if (categories == ["none"]) != (record["consent_or_exception"] == "no_personal_data"):
        raise ComplianceError("fundamento y categorías inconsistentes")
    evidence = record["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != REQUIRED_EVIDENCE:
        raise ComplianceError("referencias legales incompletas o adicionales")
    for key in sorted(REQUIRED_EVIDENCE):
        _reference(evidence[key], key)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ComplianceError("ahora debe tener zona horaria")
    _date(record["reviewed_at"], now=current.astimezone(timezone.utc))
    return project


def _package(name: object, version: object, licenses: object) -> tuple[str, str, str]:
    if not isinstance(name, str) or not PKG.fullmatch(name):
        raise ComplianceError("dependencia sin nombre controlado")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ComplianceError("dependencia sin versión verificable")
    if not isinstance(licenses, str) or len(licenses) > 160 or not LICENSE.fullmatch(licenses):
        raise ComplianceError("dependencia sin expresión de licencia comprobable")
    if any(word in UNDETERMINED for word in re.findall(r"[A-Za-z0-9.+:-]+", licenses)):
        raise ComplianceError("dependencia con licencia indeterminada")
    return (name.casefold(), version, licenses)


def inspect_composer(document: object) -> list[tuple[str, str, str]]:
    if not isinstance(document, dict):
        raise ComplianceError("composer.lock inválido")
    result = []
    for group in ("packages", "packages-dev"):
        entries = document.get(group)
        if not isinstance(entries, list):
            raise ComplianceError("composer.lock sin grupos de dependencias completos")
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("license"), list) or len(item["license"]) != 1:
                raise ComplianceError("licencia de Composer ausente o requiere revisión de expresión")
            result.append(_package(item.get("name"), item.get("version"), item["license"][0]))
    return result


def inspect_npm(document: object) -> list[tuple[str, str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("packages"), dict):
        raise ComplianceError("package-lock.json incompleto")
    result = []
    for path, item in document["packages"].items():
        if path == "":
            continue
        if not isinstance(path, str) or "node_modules/" not in path or not isinstance(item, dict):
            raise ComplianceError("entrada npm no verificable")
        name = path.rsplit("node_modules/", 1)[-1]
        result.append(_package(name, item.get("version"), item.get("license")))
    return result


def validate_inventory(packages: list[tuple[str, str, str]]) -> dict[str, object]:
    if len(packages) > 10000:
        raise ComplianceError("inventario supera máximo")
    if len(packages) != len(set(packages)):
        raise ComplianceError("entrada de dependencia duplicada")
    return {"packages_observed": len(packages), "license_status": "identifiers_present_review_required"}


def _read(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4_000_000:
        raise ComplianceError("archivo ausente, simbólico o excesivo")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--privacy", required=True, type=Path)
    parser.add_argument("--composer-lock", type=Path)
    parser.add_argument("--npm-lock", type=Path)
    parser.add_argument("--stdlib-only", action="store_true")
    args = parser.parse_args()
    if args.stdlib_only == bool(args.composer_lock or args.npm_lock):
        parser.error("indicar lockfiles o --stdlib-only (exclusivos)")
    try:
        project = validate_privacy(_read(args.privacy))
        packages = []
        if args.composer_lock:
            packages.extend(inspect_composer(_read(args.composer_lock)))
        if args.npm_lock:
            packages.extend(inspect_npm(_read(args.npm_lock)))
        inventory = validate_inventory(packages)
        print(json.dumps({"project": project, "evidence_status": "documented_not_legally_approved",
                          **inventory}, sort_keys=True))
    except (ComplianceError, OSError, UnicodeError, ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ComplianceError) else "entrada de evidencia inválida"
        parser.exit(1, f"error: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
