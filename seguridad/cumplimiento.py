"""Verificador de evidencia, NO dictamen jurídico ni compatibilidad de licencias."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


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
LICENSE = re.compile(
    r"[A-Za-z0-9.+():-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+():-]+)*\Z"
)
UTC_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
UNDETERMINED = frozenset({"NOASSERTION", "NONE", "UNKNOWN", "UNLICENSED"})
COMPOSER_LOCK = Path("composer.lock")
NPM_LOCK = Path("package-lock.json")
FACTORY_ROOT = Path(__file__).resolve().parents[1]
NPM_SNAPSHOT_ROOT = FACTORY_ROOT / "seguridad" / "evidencia" / "brvtal-npm"
NPM_SNAPSHOT_MANIFEST = NPM_SNAPSHOT_ROOT / "snapshot.json"
NPM_SNAPSHOT_PACKAGE = NPM_SNAPSHOT_ROOT / "package.json"
NPM_SNAPSHOT_LOCK = NPM_SNAPSHOT_ROOT / "package-lock.json"
NPM_SNAPSHOT_PROJECT = "pl0n3r/brvtal"
NPM_SNAPSHOT_SOURCE_SHA = "138b1babac0ff6797ad9e0f3ccb0fbda0f793452"
NPM_SNAPSHOT_SOURCE_BLOB = "a23d3ab36b5988c2edd9a38ff15a19d8fd572b1b"
NPM_SNAPSHOT_RUN = 36001724208
NPM_SNAPSHOT_NPM_VERSION = "10.9.8"
NPM_SNAPSHOT_COMMAND = (
    "npm install --package-lock-only --ignore-scripts --no-audit --no-fund"
)
NPM_SNAPSHOT_SHA256 = {
    "package.json": "5a89041609e59a10328e4a7238898fa2b2986d33320704c2b9d52d3c3256c5a1",
    "package-lock.json": "0707872e3d96768b17c2a76cc5ac55e675508d94f2382897d15b3103ba7e030c",
}
MAX_LOCK_BYTES = 4_000_000
MAX_PRIVACY_BYTES = 128_000


def _reference(value: object, label: str) -> None:
    if not isinstance(value, str) or not REF.fullmatch(value):
        raise ComplianceError(f"{label}: referencia de evidencia inválida")


def _date(value: object, *, now: datetime) -> None:
    if not isinstance(value, str) or not UTC_STAMP.fullmatch(value):
        raise ComplianceError(
            "fecha de revisión debe usar UTC YYYY-MM-DDTHH:MM:SSZ"
        )
    try:
        timestamp = datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ComplianceError("fecha de revisión inválida") from exc
    if timestamp > now or timestamp < now - timedelta(days=365):
        raise ComplianceError("evidencia de revisión futura o desactualizada")


def _privacy_root(record: object) -> dict[str, Any]:
    expected = {
        "version",
        "project",
        "scope",
        "purpose",
        "data_categories",
        "consent_or_exception",
        "evidence",
        "reviewed_at",
    }
    if not isinstance(record, dict) or set(record) != expected:
        raise ComplianceError("campos de checklist incompletos o adicionales")
    if type(record["version"]) is not int or record["version"] != 1:
        raise ComplianceError("versión de checklist no admitida")
    project = record["project"]
    if not isinstance(project, str) or project not in PROJECTS:
        raise ComplianceError("producto no admitido")
    return record


def _controlled_fields(record: dict[str, Any]) -> None:
    for field in ("scope", "purpose"):
        value = record[field]
        if not isinstance(value, str) or not SLUG.fullmatch(value):
            raise ComplianceError(
                f"{field}: se exige código controlado, no texto libre"
            )


def _categories(record: dict[str, Any]) -> list[str]:
    categories = record["data_categories"]
    if (
        not isinstance(categories, list)
        or not categories
        or len(categories) > 12
    ):
        raise ComplianceError("categorías incompletas o repetidas")
    if any(not isinstance(cat, str) or not SLUG.fullmatch(cat) for cat in categories):
        raise ComplianceError("categoría inválida")
    if len(set(categories)) != len(categories):
        raise ComplianceError("categorías incompletas o repetidas")
    if "none" in categories and len(categories) != 1:
        raise ComplianceError("none no puede mezclarse con datos personales")
    return categories


def _basis(record: dict[str, Any], categories: list[str]) -> None:
    basis = record["consent_or_exception"]
    allowed = {
        "consent_documented",
        "exception_for_legal_review",
        "no_personal_data",
    }
    if basis not in allowed:
        raise ComplianceError("fundamento documental no identificado")
    no_personal_data = categories == ["none"]
    if no_personal_data != (basis == "no_personal_data"):
        raise ComplianceError("fundamento y categorías inconsistentes")


def _evidence(record: dict[str, Any]) -> None:
    evidence = record["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != REQUIRED_EVIDENCE:
        raise ComplianceError("referencias legales incompletas o adicionales")
    for key in sorted(REQUIRED_EVIDENCE):
        _reference(evidence[key], key)


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ComplianceError("ahora debe tener zona horaria")
    return current.astimezone(timezone.utc)


def validate_privacy(record: object, *, now: datetime | None = None) -> str:
    """Exige trazabilidad documental sin almacenar nombres ni datos de titulares."""
    validated = _privacy_root(record)
    _controlled_fields(validated)
    categories = _categories(validated)
    _basis(validated, categories)
    _evidence(validated)
    _date(validated["reviewed_at"], now=_current_time(now))
    return str(validated["project"])


def _package(
    name: object,
    version: object,
    licenses: object,
) -> tuple[str, str, str]:
    if not isinstance(name, str) or not PKG.fullmatch(name):
        raise ComplianceError("dependencia sin nombre controlado")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ComplianceError("dependencia sin versión verificable")
    if (
        not isinstance(licenses, str)
        or len(licenses) > 160
        or not LICENSE.fullmatch(licenses)
    ):
        raise ComplianceError("dependencia sin expresión de licencia comprobable")
    words = re.findall(r"[A-Za-z0-9.+:-]+", licenses)
    if any(word in UNDETERMINED for word in words):
        raise ComplianceError("dependencia con licencia indeterminada")
    return (name.casefold(), version, licenses)


def inspect_composer(document: object) -> list[tuple[str, str, str]]:
    if not isinstance(document, dict):
        raise ComplianceError("composer.lock inválido")
    result = []
    for group in ("packages", "packages-dev"):
        entries = document.get(group)
        if not isinstance(entries, list):
            raise ComplianceError(
                "composer.lock sin grupos de dependencias completos"
            )
        for item in entries:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("license"), list)
                or len(item["license"]) != 1
            ):
                raise ComplianceError(
                    "licencia de Composer ausente o requiere revisión de expresión"
                )
            result.append(
                _package(
                    item.get("name"),
                    item.get("version"),
                    item["license"][0],
                )
            )
    return result


def inspect_npm(document: object) -> list[tuple[str, str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("packages"), dict):
        raise ComplianceError("package-lock.json incompleto")
    result = []
    for path, item in document["packages"].items():
        if path == "":
            continue
        if (
            not isinstance(path, str)
            or "node_modules/" not in path
            or not isinstance(item, dict)
        ):
            raise ComplianceError("entrada npm no verificable")
        name = path.rsplit("node_modules/", 1)[-1]
        result.append(
            _package(name, item.get("version"), item.get("license"))
        )
    return result



def _snapshot_file(path: Path) -> Path:
    """Resuelve únicamente archivos de evidencia versionados bajo Factory."""
    if path.is_symlink():
        raise ComplianceError("snapshot npm simbólico prohibido")
    try:
        root = NPM_SNAPSHOT_ROOT.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ComplianceError("snapshot npm canónico ausente o inválido") from exc
    if not resolved.is_file() or resolved.stat().st_size > MAX_LOCK_BYTES:
        raise ComplianceError("snapshot npm canónico ausente o excesivo")
    return resolved


def _snapshot_bytes(path: Path) -> bytes:
    try:
        return _snapshot_file(path).read_bytes()
    except OSError as exc:
        raise ComplianceError("snapshot npm no verificable") from exc


def _snapshot_json_bytes(data: bytes) -> object:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ComplianceError("snapshot npm JSON inválido") from exc


def _snapshot_json(path: Path) -> object:
    return _snapshot_json_bytes(_snapshot_bytes(path))


def inspect_npm_snapshot(
    slug: str,
    *,
    expected_project: str | None = None,
) -> list[tuple[str, str, str]]:
    """Valida evidencia npm cerrada del run fijado y reutiliza inspect_npm."""
    if slug != "brvtal":
        raise ComplianceError("snapshot npm no admitido")

    manifest = _snapshot_json(NPM_SNAPSHOT_MANIFEST)
    expected_keys = {
        "version",
        "project",
        "source_sha",
        "source_package_blob",
        "generation_run",
        "npm_version",
        "generation_command",
        "sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_keys:
        raise ComplianceError("metadata de snapshot npm inválida")
    if type(manifest["version"]) is not int or manifest["version"] != 1:
        raise ComplianceError("versión de snapshot npm no admitida")
    if (
        manifest["project"] != NPM_SNAPSHOT_PROJECT
        or manifest["source_sha"] != NPM_SNAPSHOT_SOURCE_SHA
        or manifest["source_package_blob"] != NPM_SNAPSHOT_SOURCE_BLOB
        or manifest["generation_run"] != NPM_SNAPSHOT_RUN
        or manifest["npm_version"] != NPM_SNAPSHOT_NPM_VERSION
        or manifest["generation_command"] != NPM_SNAPSHOT_COMMAND
        or manifest["sha256"] != NPM_SNAPSHOT_SHA256
    ):
        raise ComplianceError("procedencia de snapshot npm no coincide")
    if expected_project is not None and expected_project != manifest["project"]:
        raise ComplianceError("snapshot npm no corresponde al producto")

    package_bytes = _snapshot_bytes(NPM_SNAPSHOT_PACKAGE)
    lock_bytes = _snapshot_bytes(NPM_SNAPSHOT_LOCK)
    observed = {
        "package.json": hashlib.sha256(package_bytes).hexdigest(),
        "package-lock.json": hashlib.sha256(lock_bytes).hexdigest(),
    }
    if observed != NPM_SNAPSHOT_SHA256:
        raise ComplianceError("snapshot npm alterado")

    package = _snapshot_json_bytes(package_bytes)
    lock = _snapshot_json_bytes(lock_bytes)
    if (
        not isinstance(package, dict)
        or package.get("name") != "brvtal"
        or package.get("version") != "0.1.51"
        or package.get("devDependencies") != {"@playwright/test": "^1.55.0"}
    ):
        raise ComplianceError("package.json fuente de snapshot inválido")
    if (
        not isinstance(lock, dict)
        or lock.get("name") != package["name"]
        or lock.get("version") != package["version"]
        or lock.get("lockfileVersion") != 3
        or lock.get("requires") is not True
        or not isinstance(lock.get("packages"), dict)
        or lock["packages"].get("", {}).get("devDependencies")
        != package["devDependencies"]
    ):
        raise ComplianceError("package-lock.json no corresponde a la fuente")

    return inspect_npm(lock)


def validate_inventory(
    packages: list[tuple[str, str, str]],
) -> dict[str, object]:
    if len(packages) > 10000:
        raise ComplianceError("inventario supera máximo")
    if len(packages) != len(set(packages)):
        raise ComplianceError("entrada de dependencia duplicada")
    return {
        "packages_observed": len(packages),
        "license_status": "identifiers_present_review_required",
    }


def _read_repo_json(relative: Path) -> object:
    root = Path.cwd().resolve()
    raw = root / relative
    if raw.is_symlink():
        raise ComplianceError("lockfile simbólico prohibido")
    try:
        resolved = raw.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ComplianceError("lockfile canónico ausente o inválido") from exc
    if not resolved.is_file() or resolved.stat().st_size > MAX_LOCK_BYTES:
        raise ComplianceError("lockfile canónico ausente o excesivo")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComplianceError("lockfile JSON inválido") from exc


def _privacy_from_stdin() -> object:
    raw = sys.stdin.read(MAX_PRIVACY_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_PRIVACY_BYTES:
        raise ComplianceError("evidencia de privacidad supera máximo")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ComplianceError("evidencia de privacidad JSON inválida") from exc


def _inventory_from_args(
    *,
    composer: bool,
    npm: bool,
    stdlib_only: bool,
    npm_snapshot: str | None,
    expected_project: str,
) -> list[tuple[str, str, str]]:
    use_lockfiles = composer or npm
    modes = int(use_lockfiles) + int(stdlib_only) + int(npm_snapshot is not None)
    if modes != 1:
        raise ComplianceError(
            "indicar --composer/--npm, --npm-snapshot o --stdlib-only (exclusivos)"
        )
    packages: list[tuple[str, str, str]] = []
    if composer:
        packages.extend(inspect_composer(_read_repo_json(COMPOSER_LOCK)))
    if npm:
        packages.extend(inspect_npm(_read_repo_json(NPM_LOCK)))
    if npm_snapshot is not None:
        packages.extend(
            inspect_npm_snapshot(
                npm_snapshot,
                expected_project=expected_project,
            )
        )
    return packages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--composer",
        action="store_true",
        help="inspecciona ./composer.lock del checkout",
    )
    parser.add_argument(
        "--npm",
        action="store_true",
        help="inspecciona ./package-lock.json del checkout",
    )
    parser.add_argument(
        "--npm-snapshot",
        choices=("brvtal",),
        help="inspecciona evidencia npm canónica versionada en Factory",
    )
    parser.add_argument("--stdlib-only", action="store_true")
    args = parser.parse_args()
    try:
        project = validate_privacy(_privacy_from_stdin())
        packages = _inventory_from_args(
            composer=args.composer,
            npm=args.npm,
            stdlib_only=args.stdlib_only,
            npm_snapshot=args.npm_snapshot,
            expected_project=project,
        )
        inventory = validate_inventory(packages)
        print(json.dumps({
            "project": project,
            "evidence_status": "documented_not_legally_approved",
            **inventory,
        }, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        message = (
            str(exc)
            if isinstance(exc, ComplianceError)
            else "entrada de evidencia inválida"
        )
        parser.exit(1, f"error: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
