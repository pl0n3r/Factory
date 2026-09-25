#!/usr/bin/env python3
"""Ejecuta validaciones del consumidor sin exponer credenciales de caché de Actions."""
from __future__ import annotations

import argparse
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

CACHE_ENV_KEYS = frozenset(
    {
        "ACTIONS_CACHE_URL",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_RESULTS_URL",
        "ACTIONS_CACHE_SERVICE_V2",
    }
)


def sanitized_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in CACHE_ENV_KEYS:
        env.pop(key, None)
    return env


def run_command(command: Sequence[str], cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=sanitized_environment(),
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def composer_validate(cwd: Path) -> int:
    if not (cwd / "composer.json").is_file():
        return 0
    return run_command(("composer", "validate", "--strict"), cwd).returncode


def _php_file(path: Path, root: Path) -> bool:
    if path.suffix != ".php" or not path.is_file():
        return False
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return "vendor" not in relative.parts


def php_contract(cwd: Path, stack: str) -> int:
    files = sorted(path for path in cwd.rglob("*.php") if _php_file(path, cwd))

    def lint(path: Path) -> int:
        result = run_command(("php", "-l", str(path)), cwd, capture=True)
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        return result.returncode

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(lint, files))
    if any(code != 0 for code in codes):
        return 1

    composer = cwd / "composer.json"
    if composer.is_file():
        listed = run_command(("composer", "run-script", "--list", "--no-interaction"), cwd, capture=True)
        if listed.returncode != 0:
            if listed.stdout:
                print(listed.stdout, file=sys.stderr)
            return listed.returncode
        if " test" in f" {listed.stdout or ''} ":
            return run_command(("composer", "test", "--no-interaction"), cwd).returncode

    if stack == "symfony" and (cwd / "vendor/bin/simple-phpunit").is_file():
        return run_command(("vendor/bin/simple-phpunit",), cwd).returncode
    if stack == "laravel" and (cwd / "artisan").is_file():
        return run_command(("php", "artisan", "test"), cwd).returncode
    return 0


def node_test_build(cwd: Path) -> int:
    for command in (
        ("npm", "test", "--if-present"),
        ("npm", "run", "build", "--if-present"),
    ):
        code = run_command(command, cwd).returncode
        if code != 0:
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("composer-validate", "php-contract", "node-test-build"))
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--stack", choices=("php", "symfony", "laravel"), default="php")
    args = parser.parse_args()

    cwd = Path(args.working_directory).resolve()
    root = Path.cwd().resolve()
    try:
        cwd.relative_to(root)
    except ValueError:
        print("ERROR: working-directory fuera del checkout.", file=sys.stderr)
        return 2
    if not cwd.is_dir():
        print("ERROR: working-directory no existe.", file=sys.stderr)
        return 2

    if args.operation == "composer-validate":
        return composer_validate(cwd)
    if args.operation == "php-contract":
        return php_contract(cwd, args.stack)
    return node_test_build(cwd)


if __name__ == "__main__":
    raise SystemExit(main())
