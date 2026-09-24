"""Auditoría conservadora de workflows y evidencias de recuperación de Factory."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re


class ValidationError(ValueError):
    """Entrada no verificable; el mensaje nunca contiene su contenido."""


_SHA_REF = re.compile(r"^[^\s@]+@[0-9a-f]{40}$")
_EVIDENCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{5,159}$")
_REQUIRED_CHECKS = frozenset({"repo_backup", "secrets_escrow", "token_rotation", "restore_drill"})
_REQUIRED_ROLES = frozenset({"ci", "deploy", "observer"})


def audit_workflow(content: str) -> None:
    """Rechaza disparadores privilegiados y permisos/acciones inseguros."""
    if len(content.encode("utf-8")) > 256_000:
        raise ValidationError("workflow supera el tamaño máximo")
    lines = content.splitlines()
    for index, raw in enumerate(lines):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indentation = len(line) - len(line.lstrip())
        if (re.match(r"^\s*[\"\']?pull_request_target[\"\']?\s*:", line)
                or re.match(r"^\s*-\s+[\"\']?pull_request_target[\"\']?\s*$", line)
                or re.match(r"^\s*[\"\']?on[\"\']?\s*:\s*(?:[\[{][^\n]*\bpull_request_target\b|[\"\']?pull_request_target[\"\']?\s*$)", line)):
            raise ValidationError(f"línea {index + 1}: pull_request_target prohibido")
        if re.match(r"^\s*permissions\s*:\s*[\"\']?write-all[\"\']?\s*$", line):
            raise ValidationError(f"línea {index + 1}: write-all prohibido")
        if indentation == 0 and (re.match(r"^permissions\s*:\s*\{.*\bwrite\b.*\}", line)
                                 or re.match(r"^permissions\s*:\s*[&*]", line)):
            # Un alias/anchor aquí puede ocultar permisos elevados del escaneo textual.
            raise ValidationError("permisos globales de escritura prohibidos")
        permission = re.match(r"^\s*permissions\s*:\s*$", line)
        if permission and indentation == 0:
            for following in lines[index + 1:]:
                clean = following.split("#", 1)[0].rstrip()
                if not clean.strip():
                    continue
                level = len(clean) - len(clean.lstrip())
                if level <= indentation:
                    break
                if re.match(r"^\s*[\w-]+\s*:\s*write\s*$", clean):
                    raise ValidationError("permisos de escritura deben declararse por job")
        uses = re.match(r"^\s*(?:-\s*)?uses\s*:\s*(\S*)", line)
        if uses:
            ref = uses.group(1).strip("'\"")
            if not (ref.startswith("./") or _SHA_REF.fullmatch(ref)):
                raise ValidationError(f"línea {index + 1}: acción sin SHA inmutable")


def validate_manifest(document: object, *, now: datetime | None = None) -> None:
    """Exige evidencia reciente sin transportar tokens ni otros secretos."""
    if not isinstance(document, dict) or set(document) != {"version", "project", "identities", "checks"}:
        raise ValidationError("campos raíz del manifiesto incompletos o adicionales")
    if document["version"] != 1 or type(document["version"]) is not int:
        raise ValidationError("versión del manifiesto no admitida")
    if not isinstance(document["project"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", document["project"]):
        raise ValidationError("project debe usar owner/repo")
    identities = document["identities"]
    if not isinstance(identities, dict) or set(identities) != _REQUIRED_ROLES:
        raise ValidationError("identidades ci/deploy/observer obligatorias")
    if any(not isinstance(value, str) or not re.fullmatch(r"github-app:[a-z0-9-]{3,64}", value) for value in identities.values()):
        raise ValidationError("identidad debe ser referencia de GitHub App, nunca token")
    if len(set(identities.values())) != len(_REQUIRED_ROLES):
        raise ValidationError("las identidades de agentes deben ser distintas")
    checks = document["checks"]
    if not isinstance(checks, dict) or set(checks) != _REQUIRED_CHECKS:
        raise ValidationError("evidencias de recuperación incompletas o adicionales")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValidationError("fecha de referencia sin zona horaria")
    current = current.astimezone(timezone.utc)
    for name in sorted(_REQUIRED_CHECKS):
        item = checks[name]
        if not isinstance(item, dict) or set(item) != {"verified_at", "evidence_ref"}:
            raise ValidationError(f"{name}: se exige fecha y referencia, sin secretos")
        stamp, reference = item["verified_at"], item["evidence_ref"]
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
            raise ValidationError(f"{name}: verified_at debe usar UTC RFC3339")
        try:
            verified = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValidationError(f"{name}: fecha inválida") from exc
        if not current - timedelta(days=90) <= verified <= current:
            raise ValidationError(f"{name}: evidencia vencida o futura")
        if not isinstance(reference, str) or not _EVIDENCE_REF.fullmatch(reference):
            raise ValidationError(f"{name}: referencia de evidencia inválida")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows", type=Path, help="directorio de workflows a auditar")
    parser.add_argument("--manifest", type=Path, help="manifiesto de evidencia (fuera del repo)")
    args = parser.parse_args()
    if not args.workflows and not args.manifest:
        parser.error("indicar --workflows o --manifest")
    try:
        if args.workflows:
            root = args.workflows
            if root.is_symlink() or not root.is_dir():
                raise ValidationError("directorio de workflows inválido")
            files = sorted((*root.glob("*.yml"), *root.glob("*.yaml")))
            if not files or len(files) > 100:
                raise ValidationError("cantidad de workflows inválida")
            for file in files:
                if file.is_symlink() or file.stat().st_size > 256_000:
                    raise ValidationError("workflow inválido o excesivo")
                audit_workflow(file.read_text(encoding="utf-8"))
            print(f"workflows validados: {len(files)}")
        if args.manifest:
            file = args.manifest
            if file.is_symlink() or file.stat().st_size > 32_000:
                raise ValidationError("manifiesto inválido o excesivo")
            validate_manifest(json.loads(file.read_text(encoding="utf-8")))
            print("evidencia de recuperación validada")
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        message = str(exc) if isinstance(exc, ValidationError) else "no se pudo leer/interpretar la entrada"
        parser.exit(1, f"error: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
