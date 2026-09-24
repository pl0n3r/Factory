#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
if __package__:
    from scripts.runtime_health import HealthError, check_health, check_no_5xx, validate_path
else:
    from runtime_health import HealthError, check_health, check_no_5xx, validate_path

def parse_paths(value: str) -> list[str]:
    if not isinstance(value, str) or len(value) > 10_000:
        raise HealthError("paths inválido.")
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HealthError("paths inválido.") from exc
    if not isinstance(raw, list) or not 1 <= len(raw) <= 20:
        raise HealthError("paths debe contener entre 1 y 20 rutas.")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise HealthError("paths inválido.")
        path = validate_path(item)
        if path not in result:
            result.append(path)
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--health-path", default="/health")
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--paths", default='["/"]')
    parser.add_argument("--require-schema", action="store_true")
    args = parser.parse_args()
    try:
        health = check_health(
            args.origin,
            args.health_path,
            args.version,
            args.sha,
            require_schema=args.require_schema,
        )
        surfaces = check_no_5xx(args.origin, parse_paths(args.paths))
        print(json.dumps({
            "ok": True,
            "health": {
                "status": health.get("status"),
                "version": health.get("version"),
                "release_sha": health.get("release_sha"),
            },
            "surfaces": surfaces,
        }, sort_keys=True))
        return 0
    except HealthError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
