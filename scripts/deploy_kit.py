#!/usr/bin/env python3
"""Orquesta adapters fijos de deploy confinados al checkout consumidor."""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
if __package__:
    from scripts.runtime_health import HealthError, check_health, validate_origin
else:
    from runtime_health import HealthError, check_health, validate_origin

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
    return subprocess.run([str(path)], check=False).returncode

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
    runner: Runner = stage_runner,
    health: HealthCheck = check_health,
) -> None:
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
        )
    except (DeployError, HealthError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
