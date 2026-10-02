#!/usr/bin/env python3
"""CLI offline y confinada para el contrato canónico de ciclo desatendido."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.unattended_cycle import compose_unattended_cycle
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import DailySummary, WatchdogDecision, WatchdogIncident

SNAPSHOT_VERSION = 1
MAX_SNAPSHOT_CHARS = 1_000_000
SNAPSHOT_KEYS = frozenset({"version", "dispatch", "guard", "watchdog", "provenance"})
GUARD_KEYS = frozenset(
    {"action", "authority", "pause_allowed", "reasons", "evidence_fingerprint"}
)
WATCHDOG_KEYS = frozenset(
    {
        "action",
        "authority",
        "incidents",
        "new_alert_fingerprints",
        "interrupt_owner",
        "daily_summary",
        "evidence_fingerprint",
    }
)
INCIDENT_KEYS = frozenset({"code", "severity", "fingerprint", "repeated", "reasons"})
SUMMARY_KEYS = frozenset(
    {
        "active_fronts",
        "state_freshness",
        "incidents",
        "blockers",
        "human_gates",
        "integrated",
        "reverted",
        "next_actions",
    }
)
SENSITIVE_VALUE_RE = re.compile(
    r"(?:password|passwd|secret|token|cookie|credential|authorization|private_key)\\s*[:=]",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\\b[^\\s@]+@[^\\s@]+\\.[^\\s@]+\\b")


class SnapshotError(ValueError):
    """Snapshot inválido o acceso fuera del checkout."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError("duplicate_json_key")
        result[key] = value
    return result


def _exact_dict(value: object, keys: frozenset[str], reason: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SnapshotError(reason)
    return value


def _string_tuple(value: object, reason: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SnapshotError(reason)
    return tuple(value)


def _adapt_dispatch(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SnapshotError("invalid_dispatch")
    result = dict(value)
    unattended = result.get("unattended")
    if not isinstance(unattended, dict):
        raise SnapshotError("invalid_dispatch_unattended")
    adapted = dict(unattended)
    adapted["reasons"] = _string_tuple(
        adapted.get("reasons"),
        "invalid_dispatch_reasons",
    )
    result["unattended"] = adapted
    return result


def _adapt_guard(value: object) -> GuardDecision:
    item = _exact_dict(value, GUARD_KEYS, "invalid_guard")
    return GuardDecision(
        action=item["action"],
        authority=item["authority"],
        pause_allowed=item["pause_allowed"],
        reasons=_string_tuple(item["reasons"], "invalid_guard_reasons"),
        evidence_fingerprint=item["evidence_fingerprint"],
    )


def _adapt_incident(value: object) -> WatchdogIncident:
    item = _exact_dict(value, INCIDENT_KEYS, "invalid_watchdog_incident")
    return WatchdogIncident(
        code=item["code"],
        severity=item["severity"],
        fingerprint=item["fingerprint"],
        repeated=item["repeated"],
        reasons=_string_tuple(item["reasons"], "invalid_watchdog_incident_reasons"),
    )


def _adapt_summary(value: object) -> DailySummary:
    item = _exact_dict(value, SUMMARY_KEYS, "invalid_watchdog_summary")
    return DailySummary(
        active_fronts=_string_tuple(item["active_fronts"], "invalid_active_fronts"),
        state_freshness=item["state_freshness"],
        incidents=_string_tuple(item["incidents"], "invalid_summary_incidents"),
        blockers=_string_tuple(item["blockers"], "invalid_summary_blockers"),
        human_gates=_string_tuple(item["human_gates"], "invalid_summary_human_gates"),
        integrated=_string_tuple(item["integrated"], "invalid_summary_integrated"),
        reverted=_string_tuple(item["reverted"], "invalid_summary_reverted"),
        next_actions=_string_tuple(item["next_actions"], "invalid_summary_next_actions"),
    )


def _adapt_watchdog(value: object) -> WatchdogDecision:
    item = _exact_dict(value, WATCHDOG_KEYS, "invalid_watchdog")
    incidents = item["incidents"]
    if not isinstance(incidents, list):
        raise SnapshotError("invalid_watchdog_incidents")
    return WatchdogDecision(
        action=item["action"],
        authority=item["authority"],
        incidents=tuple(_adapt_incident(incident) for incident in incidents),
        new_alert_fingerprints=_string_tuple(
            item["new_alert_fingerprints"],
            "invalid_watchdog_alerts",
        ),
        interrupt_owner=item["interrupt_owner"],
        daily_summary=_adapt_summary(item["daily_summary"]),
        evidence_fingerprint=item["evidence_fingerprint"],
    )


def cycle_from_snapshot(value: object) -> dict[str, object]:
    snapshot = _exact_dict(value, SNAPSHOT_KEYS, "invalid_snapshot_shape")
    version = snapshot["version"]
    if type(version) is not int or version != SNAPSHOT_VERSION:
        raise SnapshotError("invalid_snapshot_version")
    return compose_unattended_cycle(
        _adapt_dispatch(snapshot["dispatch"]),
        _adapt_guard(snapshot["guard"]),
        _adapt_watchdog(snapshot["watchdog"]),
        provenance=snapshot["provenance"],
    )


def _is_within_checkout(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_snapshot_text(path: str | None, stdin: TextIO, *, root: Path = ROOT) -> str:
    if path is None:
        content = stdin.read(MAX_SNAPSHOT_CHARS + 1)
    else:
        checkout = root.resolve()
        candidate = Path(path)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (checkout / candidate).resolve()
        )
        if not _is_within_checkout(resolved, checkout):
            raise SnapshotError("snapshot_path_outside_checkout")
        if not resolved.is_file():
            raise SnapshotError("snapshot_path_invalid")
        content = resolved.read_text(encoding="utf-8")
    if len(content) > MAX_SNAPSHOT_CHARS:
        raise SnapshotError("snapshot_too_large")
    return content


def _contains_sensitive_output(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_sensitive_output(key) or _contains_sensitive_output(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_output(item) for item in value)
    if not isinstance(value, str):
        return False
    return bool(SENSITIVE_VALUE_RE.search(value) or EMAIL_RE.search(value))


def _emit(payload: object, stdout: TextIO) -> None:
    stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compone offline un snapshot canónico del ciclo desatendido."
    )
    parser.add_argument(
        "--snapshot",
        metavar="PATH",
        help="JSON local dentro del checkout; si se omite, se lee stdin.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    try:
        raw = _read_snapshot_text(args.snapshot, input_stream)
        snapshot = json.loads(raw, object_pairs_hook=_unique_object)
        result = cycle_from_snapshot(snapshot)
        if _contains_sensitive_output(result):
            raise SnapshotError("unsafe_output")
    except (SnapshotError, json.JSONDecodeError, UnicodeError, OSError):
        _emit({"error": "invalid_snapshot"}, output_stream)
        return 2
    _emit(result, output_stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
