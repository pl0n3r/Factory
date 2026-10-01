#!/usr/bin/env python3
"""Ejecuta las suites Python canónicas y emite cobertura XML para Sonar."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "coverage"
PYTHON_XML = BUILD / "python.xml"
SUITES = (
    ("tests", None),
    ("metricas", "metricas"),
    ("seguridad", "seguridad"),
    ("lecciones", "lecciones"),
    ("producto", "producto"),
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def suite_environment(path_entry: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if path_entry is not None:
        prefix = str(ROOT / path_entry)
        current = env.get("PYTHONPATH")
        env["PYTHONPATH"] = prefix if not current else prefix + os.pathsep + current
    return env


def suite_command(directory: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--source=.",
        "--branch",
        "--parallel-mode",
        "-m",
        "unittest",
        "discover",
        "-s",
        directory,
        "-p",
        "test_*.py",
    ]


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "coverage", "--version"])
    run([sys.executable, "-m", "coverage", "erase"])

    executed = 0
    for directory, path_entry in SUITES:
        if not (ROOT / directory).is_dir():
            continue
        run(suite_command(directory), env=suite_environment(path_entry))
        executed += 1

    if executed == 0:
        raise RuntimeError("No existen suites Python canónicas para medir.")

    run([sys.executable, "-m", "coverage", "combine"])
    run(
        [
            sys.executable,
            "-m",
            "coverage",
            "xml",
            "-o",
            str(PYTHON_XML),
            "--omit=tests/*,*/test_*.py",
        ]
    )
    if not PYTHON_XML.is_file() or PYTHON_XML.stat().st_size == 0:
        raise RuntimeError("No se generó build/coverage/python.xml.")
    print(f"Python coverage: {PYTHON_XML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
