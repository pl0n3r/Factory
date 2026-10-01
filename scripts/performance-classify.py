#!/usr/bin/env python3
"""Offline CLI for Factory Performance v1 envelope classification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance.classifier import PerformanceClassifierError, classify_performance_envelope
from performance.contract import PerformanceContractError
from performance.detector import PerformanceDetectionError
from scripts.safe_io import SafeIOError, read_repo_text, write_repo_text


def _json(path: Path):
    return json.loads(read_repo_text(path, root=ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = classify_performance_envelope(
            _json(args.contract),
            _json(args.envelope),
            evaluated_at=args.evaluated_at,
        )
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        if args.output:
            write_repo_text(args.output, payload, root=ROOT)
        else:
            sys.stdout.write(payload)
    except (
        OSError,
        json.JSONDecodeError,
        PerformanceClassifierError,
        PerformanceContractError,
        PerformanceDetectionError,
        SafeIOError,
    ):
        print("performance-classify: invalid or unsafe input", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
