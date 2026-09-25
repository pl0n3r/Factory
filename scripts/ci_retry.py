#!/usr/bin/env python3
"""Reintenta un conjunto cerrado de operaciones externas idempotentes."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

OPERATIONS: dict[str, tuple[str, ...]] = {
    "composer-install": (
        "composer",
        "install",
        "--no-interaction",
        "--prefer-dist",
        "--no-progress",
    ),
    "composer-audit": ("composer", "audit", "--locked", "--no-interaction"),
    "npm-ci": ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
    "npm-audit": ("npm", "audit", "--audit-level=high"),
}
CACHE_ENV_KEYS = frozenset(
    {
        "ACTIONS_CACHE_URL",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_RESULTS_URL",
        "ACTIONS_CACHE_SERVICE_V2",
    }
)
TRANSIENT_EXIT_CODES = {75}
TRANSIENT_PATTERNS = (
    re.compile(r"\btimed?\s*out\b", re.I),
    re.compile(r"\btimeout\b", re.I),
    re.compile(r"connection reset(?: by peer)?", re.I),
    re.compile(r"\beconnreset\b", re.I),
    re.compile(r"\betimedout\b", re.I),
    re.compile(r"\beconnrefused\b", re.I),
    re.compile(r"\bHTTP(?:/\S+)?\s+(?:429|502|503|504)\b", re.I),
    re.compile(r"socket hang up", re.I),
)


def operation_command(name: str) -> tuple[str, ...]:
    try:
        return OPERATIONS[name]
    except KeyError as exc:
        raise ValueError("Operación de retry no permitida.") from exc


def transient(code: int, output: str) -> bool:
    return (
        code in TRANSIENT_EXIT_CODES
        or any(pattern.search(output) for pattern in TRANSIENT_PATTERNS)
    )


def run(name: str, attempts: int, base_delay: float) -> int:
    if attempts < 1 or attempts > 5 or base_delay < 0 or base_delay > 30:
        raise ValueError("Parámetros de retry fuera de rango.")

    # S2076: operation_command() is the security boundary. It returns only
    # immutable argv tuples declared in OPERATIONS; caller input can select a
    # key but can never supply an executable, argument, shell fragment or env.
    command = operation_command(name)
    environment = os.environ.copy()
    for key in CACHE_ENV_KEYS:
        environment.pop(key, None)
    for attempt in range(1, attempts + 1):
        result = subprocess.run(  # NOSONAR(S2076)
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            env=environment,
        )
        output = result.stdout or ""
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        if result.returncode == 0:
            return 0
        if not transient(result.returncode, output) or attempt == attempts:
            return result.returncode
        time.sleep(min(30, base_delay * (2 ** (attempt - 1))))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True, choices=sorted(OPERATIONS))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--base-delay", type=float, default=2)
    args = parser.parse_args()
    try:
        return run(args.operation, args.attempts, args.base_delay)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
