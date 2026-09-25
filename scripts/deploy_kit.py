#!/usr/bin/env python3
"""Orquesta adapters fijos de deploy confinados al checkout consumidor."""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
if __package__:
    from scripts.runtime_health import HealthError, check_health, validate_origin
else:
    from runtime_health import HealthError, check_health, validate_origin

TRANSPORT_NONE = "none"
TRANSPORT_HOSTINGER_SSH = "hostinger-ssh"
_HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")
_USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REQUIRED_HOSTINGER_ENV = (
    "HOSTINGER_SSH_HOST",
    "HOSTINGER_SSH_USER",
    "HOSTINGER_SSH_PORT",
    "HOSTINGER_RELEASE_ROOT",
    "HOSTINGER_KNOWN_HOSTS",
    "DEPLOY_SSH_KEY",
)

ADAPTERS = {
    "build": Path("ops/factory/build"),
    "backup": Path("ops/factory/backup"),
    "migrate": Path("ops/factory/migrate"),
    "deploy": Path("ops/factory/deploy"),
    "rollback": Path("ops/factory/rollback"),
}

class DeployError(RuntimeError):
    pass

Runner = Callable[[str], int]
HealthCheck = Callable[..., dict]


def _validate_host(value: str) -> str:
    host = value.strip()
    if not host or not _HOST_RE.fullmatch(host):
        raise DeployError("HOSTINGER_SSH_HOST inválido.")
    labels = host.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        raise DeployError("HOSTINGER_SSH_HOST inválido.")
    return host


def _validate_release_root(value: str) -> str:
    raw = value.strip()
    if not raw.startswith("/") or "\x00" in raw or "\\" in raw:
        raise DeployError("HOSTINGER_RELEASE_ROOT debe ser una ruta POSIX absoluta.")
    path = PurePosixPath(raw)
    normalized = str(path)
    if normalized == "/" or normalized != raw.rstrip("/") or any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise DeployError("HOSTINGER_RELEASE_ROOT debe estar normalizada.")
    return normalized


def _validate_known_hosts(value: str, host: str, port: int) -> None:
    expected = {host, f"[{host}]:{port}"}
    matched = False
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            raise DeployError("HOSTINGER_KNOWN_HOSTS contiene una entrada inválida.")
        hosts, key_type, key_data = parts[0], parts[1], parts[2]
        if (
            hosts in expected
            and (
                key_type.startswith("ssh-")
                or key_type.startswith("ecdsa-")
                or key_type.startswith("sk-")
            )
            and len(key_data) >= 16
        ):
            matched = True
    if not matched:
        raise DeployError("HOSTINGER_KNOWN_HOSTS no fija el host configurado.")


def validate_transport_environment(
    transport: str,
    environment: Mapping[str, str] | None = None,
) -> None:
    if transport == TRANSPORT_NONE:
        return
    if transport != TRANSPORT_HOSTINGER_SSH:
        raise DeployError("transport inválido.")
    env = environment if environment is not None else os.environ
    missing = [name for name in _REQUIRED_HOSTINGER_ENV if not str(env.get(name, "")).strip()]
    if missing:
        raise DeployError("Transporte Hostinger SSH incompleto; faltan: " + ", ".join(missing) + ".")

    host = _validate_host(str(env["HOSTINGER_SSH_HOST"]))
    user = str(env["HOSTINGER_SSH_USER"]).strip()
    if not _USER_RE.fullmatch(user):
        raise DeployError("HOSTINGER_SSH_USER inválido.")
    port_text = str(env["HOSTINGER_SSH_PORT"]).strip()
    if not port_text.isdigit() or not (1 <= int(port_text) <= 65535):
        raise DeployError("HOSTINGER_SSH_PORT debe estar entre 1 y 65535.")
    _validate_release_root(str(env["HOSTINGER_RELEASE_ROOT"]))
    known_hosts = str(env["HOSTINGER_KNOWN_HOSTS"])
    if "\x00" in known_hosts or "\r" in known_hosts:
        raise DeployError("HOSTINGER_KNOWN_HOSTS inválido.")
    _validate_known_hosts(known_hosts, host, int(port_text))
    private_key = str(env["DEPLOY_SSH_KEY"])
    if "\x00" in private_key or "PRIVATE KEY" not in private_key:
        raise DeployError("DEPLOY_SSH_KEY no contiene una clave privada válida.")


def adapter_path(stage: str, *, root: Path | None = None) -> Path:
    if stage not in ADAPTERS:
        raise DeployError("Etapa de deploy inválida.")
    base = (root or Path.cwd()).resolve()
    raw = base / ADAPTERS[stage]
    if raw.is_symlink():
        raise DeployError("Los adapters de deploy no pueden ser symlinks.")
    try:
        resolved = raw.resolve(strict=True)
        resolved.relative_to(base)
    except (OSError, ValueError) as exc:
        raise DeployError("Adapter fuera del checkout permitido.") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise DeployError(f"Falta adapter ejecutable: {ADAPTERS[stage]}.")
    return resolved

def stage_runner(stage: str) -> int:
    path = adapter_path(stage)
    # S2076: adapter_path() maps stage through a closed constant table, rejects
    # unknown stages, symlinks and paths outside the checkout. No user argument
    # becomes executable text or a subprocess argument.
    return subprocess.run([str(path)], check=False).returncode  # NOSONAR(S2076)

def execute(stage: str, runner: Runner) -> None:
    code = runner(stage)
    if code != 0:
        raise DeployError(f"Falló etapa {stage} con exit code {code}.")

def run_pipeline(
    *,
    origin: str,
    health_path: str,
    version: str,
    sha: str,
    phase: str,
    migration_mode: str,
    live_migration_approved: bool = False,
    transport: str = TRANSPORT_NONE,
    environment: Mapping[str, str] | None = None,
    runner: Runner = stage_runner,
    health: HealthCheck = check_health,
) -> None:
    validate_transport_environment(transport, environment)
    if phase not in {"construccion", "live"}:
        raise DeployError("phase inválida.")
    if migration_mode not in {"none", "additive"}:
        raise DeployError("migration_mode inválido.")
    if phase == "live" and migration_mode == "additive" and not live_migration_approved:
        raise DeployError("Migración aditiva en live requiere aprobación operativa explícita.")
    validate_origin(origin)
    execute("build", runner)
    execute("backup", runner)
    if migration_mode == "additive":
        try:
            execute("migrate", runner)
        except DeployError as exc:
            raise DeployError(
                "Migración aditiva falló; el esquema puede estar parcialmente aplicado. "
                "Deploy no inició y no se restaura BD automáticamente."
            ) from exc
    try:
        execute("deploy", runner)
        health(
            origin,
            health_path,
            version,
            sha,
            require_schema=migration_mode == "additive",
        )
    except Exception as exc:
        try:
            execute("rollback", runner)
        except Exception as rollback_error:
            raise DeployError(
                "Deploy falló y rollback de artefacto también falló."
            ) from rollback_error
        if isinstance(exc, DeployError):
            raise
        if isinstance(exc, HealthError):
            raise DeployError(str(exc)) from exc
        raise DeployError("Deploy falló durante validación final.") from exc

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--health-path", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--migration-mode", required=True)
    parser.add_argument("--live-migration-approved", action="store_true")
    parser.add_argument("--transport", default=TRANSPORT_NONE)
    args = parser.parse_args()
    try:
        run_pipeline(
            origin=args.origin,
            health_path=args.health_path,
            version=args.version,
            sha=args.sha,
            phase=args.phase,
            migration_mode=args.migration_mode,
            live_migration_approved=args.live_migration_approved,
            transport=args.transport,
        )
    except (DeployError, HealthError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
