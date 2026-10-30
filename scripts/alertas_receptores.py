#!/usr/bin/env python3
"""Fail-closed, offline recipient selection; never sends or reads secret values.

The .yml file is intentionally restricted to the JSON subset of YAML 1.2 so
Factory's standard-library-only policy needs no YAML dependency.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "alertas" / "receptores.yml"
SCHEMA = ROOT / "alertas" / "receptores.schema.json"
REPOS = frozenset({
    "pl0n3r/Factory", "pl0n3r/Condor", "pl0n3r/GrindFlow", "pl0n3r/brvtal",
    "pl0n3r/ControlBot", "pl0n3r/AutoFactory", "pl0n3r/FactoryRunner",
})
GRAVEDADES = frozenset({"info", "warning", "critical"})
CANALES = frozenset({"github", "email", "sms", "webhook"})
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
IDENT = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z", re.ASCII)
REF = re.compile(r"FACTORY_ALERT_[A-Z0-9_]{1,80}\Z", re.ASCII)
TOP = frozenset({"version", "receptores"})
FIELDS = frozenset({
    "id", "nombre", "canal", "secreto_ref", "repos", "gravedades",
    "activo", "desde", "hasta",
})
MAX_BYTES = 100_000


class ConfigError(ValueError):
    """A safe, constant-message validation error with no user-provided data."""


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous JSON keys rather than silently keeping the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("duplicate configuration key")
        result[key] = value
    return result


def _stamp(value: Any, *, nullable: bool = False) -> datetime | None:
    """Parse one exact, UTC-only second-resolution instant; never guess a zone."""
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ConfigError("invalid UTC timestamp")
    try:
        date = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ConfigError("invalid UTC timestamp") from exc
    if date.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ConfigError("invalid UTC timestamp")
    return date


def _strings(value: Any, choices: frozenset[str], *, max_items: int) -> set[str]:
    """Validate nonempty, distinct, bounded selectors with known vocabulary."""
    if (not isinstance(value, list) or not 1 <= len(value) <= max_items
            or any(not isinstance(item, str) or item not in choices for item in value)
            or len(set(value)) != len(value)):
        raise ConfigError("invalid recipient selectors")
    return set(value)


def validate(config: Any) -> list[dict[str, Any]]:
    """Validate every recipient before resolving any, failing closed atomically."""
    if (not isinstance(config, dict) or set(config) != TOP
            or type(config["version"]) is not int or config["version"] != 1):
        raise ConfigError("invalid configuration envelope")
    rows = config["receptores"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
        raise ConfigError("invalid recipient count")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ConfigError("invalid recipient fields")
        ident, name, channel, ref = (row[k] for k in ("id", "nombre", "canal", "secreto_ref"))
        if not isinstance(ident, str) or not IDENT.fullmatch(ident) or ident in seen:
            raise ConfigError("invalid or duplicate recipient id")
        seen.add(ident)
        if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 80
                or name != name.strip() or any(ord(char) < 32 for char in name)
                or "@" in name or "://" in name):
            raise ConfigError("invalid public display name")
        if not isinstance(channel, str) or channel not in CANALES:
            raise ConfigError("invalid channel")
        if not isinstance(ref, str) or not REF.fullmatch(ref):
            raise ConfigError("invalid secret reference")
        _strings(row["repos"], REPOS | {"*"}, max_items=7)
        if "*" in row["repos"] and len(row["repos"]) != 1:
            raise ConfigError("ambiguous wildcard")
        _strings(row["gravedades"], GRAVEDADES, max_items=3)
        if type(row["activo"]) is not bool:
            raise ConfigError("invalid active state")
        start = _stamp(row["desde"])
        end = _stamp(row["hasta"], nullable=True)
        if end is not None and end <= start:
            raise ConfigError("invalid recipient window")
    return rows


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    """Read a bounded, duplicate-key-safe JSON/YAML 1.2 subset document."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ConfigError("configuration unavailable or oversized")
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw, object_pairs_hook=_unique)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigError("configuration unavailable or invalid") from exc
    validate(data)
    return data


def resolve(config: Any, repo: str, gravedad: str, instante: str) -> list[dict[str, str]]:
    """Select active recipients; no network, secret lookup, or local clock use."""
    rows = validate(config)
    if (not isinstance(repo, str) or repo not in REPOS
            or not isinstance(gravedad, str) or gravedad not in GRAVEDADES):
        raise ConfigError("unknown repository or severity")
    now = _stamp(instante)
    found: list[dict[str, str]] = []
    for row in rows:
        if (not row["activo"] or gravedad not in row["gravedades"]
                or ("*" not in row["repos"] and repo not in row["repos"])):
            continue
        start = _stamp(row["desde"])
        end = _stamp(row["hasta"], nullable=True)
        if start <= now and (end is None or now < end):
            found.append({k: row[k] for k in ("id", "nombre", "canal", "secreto_ref")})
    return found


def main(argv: list[str] | None = None) -> int:
    """Validate or print a synthetic routing plan, never dispatch alerts."""
    parser = argparse.ArgumentParser(description="Resolver receptores offline de Factory")
    parser.add_argument("--repo", choices=sorted(REPOS))
    parser.add_argument("--gravedad", choices=sorted(GRAVEDADES))
    parser.add_argument("--instante", help="UTC YYYY-MM-DDTHH:MM:SSZ")
    args = parser.parse_args(argv)
    if any(v is not None for v in (args.repo, args.gravedad, args.instante)) and not all(
        v is not None for v in (args.repo, args.gravedad, args.instante)
    ):
        parser.error("repo, gravedad e instante deben indicarse juntos")
    try:
        config = load_config()
        selected = resolve(config, args.repo, args.gravedad, args.instante) if args.repo else []
    except (ConfigError, TypeError):
        print("ERROR: configuración de alertas inválida", file=sys.stderr)
        return 2
    print(json.dumps({"version": 1, "valido": True, "receptores": selected}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
