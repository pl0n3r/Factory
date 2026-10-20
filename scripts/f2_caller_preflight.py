#!/usr/bin/env python3
"""Read-only, fail-closed audit of Factory reusable-workflow callers (F2B)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Sequence


CONSUMERS = (
    "Condor", "GrindFlow", "brvtal", "ControlBot", "AutoFactory", "FactoryRunner",
)
DEFAULT_TARGETS = ("readme.yml", "roles.yml", "etiquetas.yml", "etiquetas-pr.yml")
TARGET = re.compile(r"[A-Za-z0-9_.-]+\.ya?ml\Z")
# GitHub Actions accepts 'uses:' either at the job level or in a step.
# Capture pinned SHA, version tag, or branch without relying on a YAML dependency.
CALLER = re.compile(
    r"^\s*(?:-\s*)?uses:\s*['\"]?"
    r"pl0n3r/factory/\.github/workflows/([A-Za-z0-9_.-]+\.ya?ml)"
    r"@([^\s'\"#]+)",
    re.MULTILINE | re.IGNORECASE,
)


def audit(root: Path, targets: Sequence[str] = DEFAULT_TARGETS) -> dict[str, object]:
    """Observe exactly six consumer checkouts; never access the network or write."""
    if not targets or any(not TARGET.fullmatch(t) for t in targets):
        raise ValueError("Los targets deben ser nombres de workflow .yml/.yaml")
    expected = sorted(set(targets))
    wanted = {t.lower() for t in expected}
    missing: list[str] = []
    unreadable: list[str] = []
    references: list[dict[str, str]] = []
    scanned: list[str] = []

    for consumer in CONSUMERS:
        workflow_dir = root / consumer / ".github" / "workflows"
        if not workflow_dir.is_dir() or workflow_dir.is_symlink():
            missing.append(consumer)
            continue
        scanned.append(consumer)
        for file in sorted(workflow_dir.rglob("*")):
            if file.suffix not in (".yml", ".yaml"):
                continue
            if file.is_symlink() or not file.is_file():
                unreadable.append(f"{consumer}:{file.relative_to(workflow_dir).as_posix()}")
                continue
            try:
                contents = file.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                unreadable.append(f"{consumer}:{file.relative_to(workflow_dir).as_posix()}")
                continue
            for match in CALLER.finditer(contents):
                reusable, ref = match.groups()
                if reusable.lower() in wanted:
                    references.append({
                        "consumer": consumer,
                        "file": file.relative_to(root / consumer).as_posix(),
                        "reusable": reusable,
                        "ref": ref,
                    })

    references.sort(key=lambda item: (item["consumer"], item["file"], item["reusable"], item["ref"]))
    return {
        "status": "BLOCKED" if missing or unreadable or references else "SAFE",
        "targets": expected,
        "scanned_consumers": scanned,
        "missing_consumers": missing,
        "unreadable_files": unreadable,
        "references": references,
        "scope": "Solo seis checkouts proporcionados; SAFE no autoriza eliminar ni publicar reusables.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Directorio que contiene los seis repositorios")
    parser.add_argument("--target", action="append", dest="targets", help="Reusable .yml/.yaml propuesto para retirada")
    args = parser.parse_args()
    try:
        report = audit(args.root, args.targets or DEFAULT_TARGETS)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "SAFE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
