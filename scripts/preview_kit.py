#!/usr/bin/env python3
"""Preview efímero que reutiliza el pipeline de deploy sin secretos live."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable, Iterator, Mapping

if __package__:
    from scripts.deploy_kit import DeployError, execute, run_pipeline, stage_runner
    from scripts.runtime_health import SEMVER, SHA
else:
    from deploy_kit import DeployError, execute, run_pipeline, stage_runner
    from runtime_health import SEMVER, SHA

PREVIEW_ADAPTERS = {
    "preview-health": Path("ops/factory/preview-health"),
    "preview-smoke": Path("ops/factory/preview-smoke"),
    "preview-e2e": Path("ops/factory/preview-e2e"),
}
PRODUCTION_CREDENTIALS = frozenset(
    {
        "DEPLOY_TOKEN",
        "DATABASE_URL",
        "DEPLOY_SSH_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
    }
)
SAFE_ENV_KEYS = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "CI",
        "GITHUB_ACTIONS",
        "GITHUB_SHA",
        "GITHUB_REPOSITORY",
        "RUNNER_OS",
        "RUNNER_ARCH",
    }
)
Runner = Callable[[str], int]


class PreviewError(RuntimeError):
    pass


def _adapter_path(stage: str, *, root: Path | None = None) -> Path:
    relative = PREVIEW_ADAPTERS.get(stage)
    if relative is None:
        raise PreviewError("Etapa de verificación preview inválida.")
    base = (root or Path.cwd()).resolve()
    raw = base / relative
    if raw.is_symlink():
        raise PreviewError("Adapters de preview no pueden ser symlinks.")
    try:
        resolved = raw.resolve(strict=True)
        resolved.relative_to(base)
    except (OSError, ValueError) as exc:
        raise PreviewError("Adapter preview fuera del checkout.") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise PreviewError(f"Falta adapter ejecutable: {relative}.")
    return resolved


def preview_stage_runner(stage: str) -> int:
    return subprocess.run(
        [str(_adapter_path(stage))],
        check=False,
    ).returncode


def _validate_release(version: str, sha: str) -> None:
    if not SEMVER.fullmatch(version) or not SHA.fullmatch(sha):
        raise PreviewError("Versión o SHA de preview inválidos.")


def _reject_production_credentials(source: Mapping[str, str]) -> None:
    present = sorted(
        name
        for name in PRODUCTION_CREDENTIALS
        if source.get(name)
    )
    if present:
        raise PreviewError(
            "Preview recibió credenciales prohibidas: "
            + ", ".join(present)
            + "."
        )


def _safe_environment(
    source: Mapping[str, str],
    *,
    preview_root: str,
    version: str,
    sha: str,
    migration_mode: str,
) -> dict[str, str]:
    _reject_production_credentials(source)
    safe = {
        key: value
        for key, value in source.items()
        if key in SAFE_ENV_KEYS and isinstance(value, str)
    }
    private_home = str(Path(preview_root) / "home")
    private_tmp = str(Path(preview_root) / "tmp")
    private_composer = str(Path(preview_root) / "composer")
    safe.update(
        {
            "HOME": private_home,
            "RUNNER_TEMP": private_tmp,
            "TMPDIR": private_tmp,
            "COMPOSER_HOME": private_composer,
            "XDG_CACHE_HOME": str(Path(preview_root) / "cache"),
            "XDG_CONFIG_HOME": str(Path(preview_root) / "config"),
            "FACTORY_PREVIEW": "1",
            "FACTORY_SYNTHETIC_DATA": "1",
            "FACTORY_PREVIEW_ROOT": preview_root,
            "FACTORY_EXPECTED_VERSION": version,
            "FACTORY_EXPECTED_SHA": sha,
            "FACTORY_REQUIRE_SCHEMA": (
                "1" if migration_mode == "additive" else "0"
            ),
        }
    )
    return safe


@contextmanager
def preview_environment(
    *,
    preview_root: str,
    version: str,
    sha: str,
    migration_mode: str,
) -> Iterator[None]:
    original = dict(os.environ)
    safe = _safe_environment(
        original,
        preview_root=preview_root,
        version=version,
        sha=sha,
        migration_mode=migration_mode,
    )
    for name in ("home", "tmp", "composer", "cache", "config"):
        (Path(preview_root) / name).mkdir(parents=True, exist_ok=True)
    os.environ.clear()
    os.environ.update(safe)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def run_preview(
    *,
    version: str,
    sha: str,
    migration_mode: str,
    phase: str = "construccion",
    runner: Runner = stage_runner,
    verification_runner: Runner = preview_stage_runner,
) -> None:
    _validate_release(version, sha)
    if phase != "construccion":
        raise PreviewError("Preview solo admite phase=construccion.")
    if migration_mode not in {"none", "additive"}:
        raise PreviewError("migration_mode de preview inválido.")

    try:
        with tempfile.TemporaryDirectory(prefix="factory-preview-") as root:
            with preview_environment(
                preview_root=root,
                version=version,
                sha=sha,
                migration_mode=migration_mode,
            ):
                def verify_health(*_args: object, **_kwargs: object) -> dict:
                    execute("preview-health", verification_runner)
                    return {"status": "ok"}

                run_pipeline(
                    origin="https://preview.invalid",
                    health_path="/health",
                    version=version,
                    sha=sha,
                    phase="construccion",
                    migration_mode=migration_mode,
                    live_migration_approved=False,
                    runner=runner,
                    health=verify_health,
                )
                execute("preview-smoke", verification_runner)
                execute("preview-e2e", verification_runner)
    except DeployError:
        raise
    except OSError as exc:
        raise PreviewError(
            "No fue posible crear o limpiar el entorno preview."
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument(
        "--migration-mode",
        choices=("none", "additive"),
        default="none",
    )
    args = parser.parse_args()
    try:
        run_preview(
            version=args.version,
            sha=args.sha,
            migration_mode=args.migration_mode,
        )
    except (PreviewError, DeployError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print("Preview sintético validado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
