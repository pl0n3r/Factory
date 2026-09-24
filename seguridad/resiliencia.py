"""Auditoría conservadora de workflows y evidencias de recuperación de Factory."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


class ValidationError(ValueError):
    """Entrada no verificable; el mensaje nunca contiene su contenido."""


_SHA_REF = re.compile(r"^[^\s@]+@[0-9a-f]{40}$")
_EVIDENCE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{5,159}$")
_PROJECT_REF = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_APP_REF = re.compile(r"^github-app:[a-z0-9-]{3,64}$")
_V2_EXECUTION_MECHANISMS = {
    "ci": "github-token:ephemeral",
    "observer": "github-token:ephemeral",
    "deploy": "hostinger:git",
}
_V2_CROSS_REPO_WRITE = {"required_mechanism": "github-app"}
_UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_WRITE_PERMISSION = re.compile(r"^[A-Za-z][A-Za-z0-9-]*\s*:\s*write\s*$")
_REQUIRED_CHECKS = frozenset(
    {"repo_backup", "secrets_escrow", "token_rotation", "restore_drill"}
)
_REQUIRED_ROLES = frozenset({"ci", "deploy", "observer"})
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / ".github" / "workflows"
MAX_WORKFLOW_BYTES = 256_000
MAX_WORKFLOWS = 100
MAX_MANIFEST_BYTES = 32_000


def _clean_yaml_line(raw: str) -> str:
    return raw.split("#", 1)[0].rstrip()


def _indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def _plain_yaml(line: str) -> str:
    return line.strip().replace('"', "").replace("'", "")


def _forbidden_trigger(line: str, indentation: int) -> bool:
    plain = _plain_yaml(line)
    if re.match(r"^pull_request_target\s*:", plain):
        return True
    if re.fullmatch(r"-\s*pull_request_target", plain):
        return True
    return (
        indentation == 0
        and re.match(r"^on\s*:", plain) is not None
        and re.search(r"\bpull_request_target\b", plain) is not None
    )


def _write_all(line: str) -> bool:
    plain = _plain_yaml(line)
    return re.fullmatch(r"permissions\s*:\s*write-all", plain) is not None


def _permission_alias(line: str) -> bool:
    plain = _plain_yaml(line)
    return re.match(r"^permissions\s*:\s*[&*]", plain) is not None


def _global_flow_write(line: str, indentation: int) -> bool:
    if indentation != 0:
        return False
    plain = _plain_yaml(line)
    if not re.match(r"^permissions\s*:\s*\{", plain):
        return False
    return re.search(r":\s*write\s*[,}]", plain) is not None


def _top_level_permission_block_has_write(
    lines: list[str],
    start: int,
) -> bool:
    for raw in lines[start + 1:]:
        clean = _clean_yaml_line(raw)
        if not clean.strip():
            continue
        level = _indentation(clean)
        if level == 0:
            return False
        if _WRITE_PERMISSION.fullmatch(clean.strip()):
            return True
    return False


def _validate_permissions(lines: list[str], index: int, line: str) -> None:
    indentation = _indentation(line)
    if _write_all(line):
        raise ValidationError(f"línea {index + 1}: write-all prohibido")
    if _permission_alias(line):
        raise ValidationError(
            f"línea {index + 1}: alias/anchor de permisos prohibido"
        )
    if _global_flow_write(line, indentation):
        raise ValidationError("permisos globales de escritura prohibidos")
    if (
        indentation == 0
        and _plain_yaml(line) == "permissions:"
        and _top_level_permission_block_has_write(lines, index)
    ):
        raise ValidationError(
            "permisos de escritura deben declararse por job"
        )


def _validate_action_ref(line: str, index: int) -> None:
    match = re.match(r"^\s*(?:-\s*)?uses\s*:\s*(\S*)", line)
    if not match:
        return
    ref = match.group(1).strip("'\"")
    if ref.startswith("./"):
        return
    if not _SHA_REF.fullmatch(ref):
        raise ValidationError(
            f"línea {index + 1}: acción sin SHA inmutable"
        )


def audit_workflow(content: str) -> None:
    """Rechaza disparadores privilegiados y permisos/acciones inseguros."""
    if len(content.encode("utf-8")) > MAX_WORKFLOW_BYTES:
        raise ValidationError("workflow supera el tamaño máximo")
    lines = content.splitlines()
    for index, raw in enumerate(lines):
        line = _clean_yaml_line(raw)
        if not line.strip():
            continue
        indentation = _indentation(line)
        if _forbidden_trigger(line, indentation):
            raise ValidationError(
                f"línea {index + 1}: pull_request_target prohibido"
            )
        _validate_permissions(lines, index, line)
        _validate_action_ref(line, index)


def _validate_manifest_root(
    document: object,
    *,
    version: int,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValidationError("manifiesto debe ser objeto")
    expected_by_version = {
        1: {"version", "project", "identities", "checks"},
        2: {
            "version",
            "project",
            "execution_mechanisms",
            "cross_repo_write",
            "checks",
        },
    }
    expected = expected_by_version[version]
    if set(document) != expected:
        raise ValidationError(
            "campos raíz del manifiesto incompletos o adicionales"
        )
    if type(document["version"]) is not int or document["version"] != version:
        raise ValidationError("versión del manifiesto no admitida")
    project = document["project"]
    if not isinstance(project, str) or not _PROJECT_REF.fullmatch(project):
        raise ValidationError("project debe usar owner/repo")
    return document


def _validate_legacy_identities(document: dict[str, Any]) -> None:
    identities = document["identities"]
    if not isinstance(identities, dict) or set(identities) != _REQUIRED_ROLES:
        raise ValidationError("identidades legacy incompletas")
    values = list(identities.values())
    if any(
        not isinstance(value, str) or not _GITHUB_APP_REF.fullmatch(value)
        for value in values
    ):
        raise ValidationError("identidad legacy inválida")
    if len(set(values)) != len(_REQUIRED_ROLES):
        raise ValidationError("identidades legacy deben ser distintas")


def _validate_execution_mechanisms(document: dict[str, Any]) -> None:
    mechanisms = document["execution_mechanisms"]
    if (
        not isinstance(mechanisms, dict)
        or set(mechanisms) != set(_V2_EXECUTION_MECHANISMS)
    ):
        raise ValidationError("mecanismos de ejecución incompletos o adicionales")
    if any(
        mechanisms.get(role) != expected
        for role, expected in _V2_EXECUTION_MECHANISMS.items()
    ):
        raise ValidationError("mecanismo de ejecución no aprobado")


def _validate_cross_repo_write(document: dict[str, Any]) -> None:
    policy = document["cross_repo_write"]
    if not isinstance(policy, dict) or policy != _V2_CROSS_REPO_WRITE:
        raise ValidationError(
            "escritura cross-repo debe exigir GitHub App dedicada"
        )


def _utc_now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValidationError("fecha de referencia sin zona horaria")
    return current.astimezone(timezone.utc)


def _verified_at(name: str, stamp: Any) -> datetime:
    if not isinstance(stamp, str) or not _UTC_STAMP.fullmatch(stamp):
        raise ValidationError(
            f"{name}: verified_at debe usar UTC RFC3339"
        )
    try:
        return datetime.strptime(
            stamp,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValidationError(f"{name}: fecha inválida") from exc


def _validate_check(
    name: str,
    item: Any,
    current: datetime,
) -> None:
    if (
        not isinstance(item, dict)
        or set(item) != {"verified_at", "evidence_ref"}
    ):
        raise ValidationError(
            f"{name}: se exige fecha y referencia, sin secretos"
        )
    verified = _verified_at(name, item["verified_at"])
    if not current - timedelta(days=90) <= verified <= current:
        raise ValidationError(f"{name}: evidencia vencida o futura")
    reference = item["evidence_ref"]
    if (
        not isinstance(reference, str)
        or not _EVIDENCE_REF.fullmatch(reference)
    ):
        raise ValidationError(
            f"{name}: referencia de evidencia inválida"
        )


def _validate_checks(document: dict[str, Any], current: datetime) -> None:
    checks = document["checks"]
    if not isinstance(checks, dict) or set(checks) != _REQUIRED_CHECKS:
        raise ValidationError(
            "evidencias de recuperación incompletas o adicionales"
        )
    for name in sorted(_REQUIRED_CHECKS):
        _validate_check(name, checks[name], current)


def validate_manifest(
    document: object,
    *,
    now: datetime | None = None,
) -> None:
    """Valida exclusivamente el contrato operativo v2 vigente."""
    if not isinstance(document, dict):
        raise ValidationError("manifiesto debe ser objeto")
    version = document.get("version")
    if version == 1:
        raise ValidationError("manifiesto v1 obsoleto; migrar a v2")
    if type(version) is not int or version != 2:
        raise ValidationError("versión del manifiesto no admitida")
    validated = _validate_manifest_root(document, version=2)
    _validate_execution_mechanisms(validated)
    _validate_cross_repo_write(validated)
    _validate_checks(validated, _utc_now(now))


def validate_legacy_manifest(
    document: object,
    *,
    now: datetime | None = None,
) -> None:
    """Valida v1 solo para diagnóstico/migración, nunca como gate operativo."""
    validated = _validate_manifest_root(document, version=1)
    _validate_legacy_identities(validated)
    _validate_checks(validated, _utc_now(now))


def _workflow_files() -> list[Path]:
    root = WORKFLOW_ROOT
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("directorio canónico de workflows inválido")
    files = sorted((*root.glob("*.yml"), *root.glob("*.yaml")))
    if not files or len(files) > MAX_WORKFLOWS:
        raise ValidationError("cantidad de workflows inválida")
    return files


def _audit_repo_workflows() -> None:
    files = _workflow_files()
    for file in files:
        if file.is_symlink():
            raise ValidationError("workflow simbólico prohibido")
        try:
            if file.stat().st_size > MAX_WORKFLOW_BYTES:
                raise ValidationError("workflow inválido o excesivo")
            content = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValidationError("no se pudo leer workflow canónico") from exc
        audit_workflow(content)
    print(f"workflows validados: {len(files)}")


def _manifest_from_stdin() -> object:
    raw = sys.stdin.read(MAX_MANIFEST_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise ValidationError("manifiesto supera el tamaño máximo")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("manifiesto JSON inválido") from exc


def _validate_manifest_stdin() -> None:
    validate_manifest(_manifest_from_stdin())
    print("evidencia de recuperación validada")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-workflows",
        action="store_true",
        help="audita únicamente .github/workflows del repositorio",
    )
    parser.add_argument(
        "--manifest-stdin",
        action="store_true",
        help="valida por stdin un manifiesto externo sin revelar su ruta",
    )
    args = parser.parse_args()
    if not args.audit_workflows and not args.manifest_stdin:
        parser.error("indicar --audit-workflows o --manifest-stdin")
    try:
        if args.audit_workflows:
            _audit_repo_workflows()
        if args.manifest_stdin:
            _validate_manifest_stdin()
    except ValidationError as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
