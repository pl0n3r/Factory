#!/usr/bin/env python3
"""Deduplicación pura de publicaciones NO_WORK del despachador.

No realiza I/O. El caller construye un snapshot global vivo, conserva la
identidad del comentario canónico y ejecuta la acción create|update|omit que
devuelve este módulo.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

CANONICAL_SINK = "pl0n3r/Factory#904"
REFRESH_AFTER_SECONDS = 30 * 60
REPOSITORIES = (
    "Factory",
    "Condor",
    "GrindFlow",
    "brvtal",
    "ControlBot",
    "AutoFactory",
    "FactoryRunner",
)
REPO_FIELDS = (
    "available",
    "recovery",
    "reservations",
    "blockers",
    "pull_requests",
)


class NoWorkInventoryError(ValueError):
    """El snapshot no demuestra el inventario global requerido."""


@dataclass(frozen=True)
class NoWorkPublicationState:
    comment_id: int
    fingerprint: str
    published_at: int


@dataclass(frozen=True)
class NoWorkDecision:
    action: Literal["create", "update", "omit"]
    fingerprint: str
    sink: str
    comment_id: int | None
    reason: str


def _stable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        normalized = [_stable(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, dict):
        return {
            str(key): _stable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    raise NoWorkInventoryError("inventory_value_invalid")


def _repo_state(name: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NoWorkInventoryError(f"repository_state_invalid:{name}")
    missing = [field for field in REPO_FIELDS if field not in value]
    if missing:
        raise NoWorkInventoryError(
            f"repository_fields_missing:{name}:{','.join(missing)}"
        )

    for field in REPO_FIELDS:
        if not isinstance(value[field], list):
            raise NoWorkInventoryError(f"repository_field_invalid:{name}:{field}")

    live_reservations = []
    for reservation in value["reservations"]:
        if isinstance(reservation, dict) and reservation.get("active") is False:
            continue
        live_reservations.append(reservation)

    open_prs = []
    for pr in value["pull_requests"]:
        if isinstance(pr, dict):
            state = pr.get("state")
            if state not in (None, "open"):
                continue
            open_prs.append(
                {
                    key: pr[key]
                    for key in ("number", "state", "head_sha")
                    if key in pr
                }
            )
        else:
            open_prs.append(pr)

    return {
        "available": _stable(value["available"]),
        "recovery": _stable(value["recovery"]),
        "reservations": _stable(live_reservations),
        "blockers": _stable(value["blockers"]),
        "pull_requests": _stable(open_prs),
    }


def canonical_inventory(snapshot: object) -> dict[str, object]:
    """Reduce el snapshot a las únicas señales autorizadas por Factory#904."""
    if not isinstance(snapshot, dict):
        raise NoWorkInventoryError("inventory_invalid")

    kill_switch = snapshot.get("kill_switch")
    repositories = snapshot.get("repositories")
    if not isinstance(kill_switch, dict) or "state" not in kill_switch:
        raise NoWorkInventoryError("kill_switch_missing")
    if not isinstance(repositories, dict):
        raise NoWorkInventoryError("repositories_missing")
    if set(repositories) != set(REPOSITORIES):
        raise NoWorkInventoryError("repositories_incomplete")

    return {
        "version": 1,
        "kill_switch": {"state": _stable(kill_switch["state"])},
        "repositories": {
            name: _repo_state(name, repositories[name])
            for name in REPOSITORIES
        },
    }


def inventory_fingerprint(snapshot: object) -> str:
    canonical = canonical_inventory(snapshot)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_now(value: object) -> int:
    if type(value) is not int or value < 0:
        raise NoWorkInventoryError("now_invalid")
    return value


def _valid_previous(value: object) -> NoWorkPublicationState | None:
    if value is None:
        return None
    if not isinstance(value, NoWorkPublicationState):
        raise NoWorkInventoryError("publication_state_invalid")
    if type(value.comment_id) is not int or value.comment_id <= 0:
        raise NoWorkInventoryError("comment_id_invalid")
    if (
        not isinstance(value.fingerprint, str)
        or len(value.fingerprint) != 64
        or any(ch not in "0123456789abcdef" for ch in value.fingerprint)
    ):
        raise NoWorkInventoryError("publication_fingerprint_invalid")
    _valid_now(value.published_at)
    return value


def decide_no_work(
    snapshot: object,
    previous: NoWorkPublicationState | None,
    now: int,
) -> NoWorkDecision:
    """Decide create|update|omit sin publicar ni leer GitHub."""
    observed_at = _valid_now(now)
    prior = _valid_previous(previous)
    fingerprint = inventory_fingerprint(snapshot)

    if prior is None:
        return NoWorkDecision(
            "create",
            fingerprint,
            CANONICAL_SINK,
            None,
            "canonical_comment_missing",
        )

    if observed_at < prior.published_at:
        raise NoWorkInventoryError("time_moved_backwards")

    if fingerprint != prior.fingerprint:
        return NoWorkDecision(
            "update",
            fingerprint,
            CANONICAL_SINK,
            prior.comment_id,
            "inventory_changed",
        )

    if observed_at - prior.published_at >= REFRESH_AFTER_SECONDS:
        return NoWorkDecision(
            "update",
            fingerprint,
            CANONICAL_SINK,
            prior.comment_id,
            "refresh_interval_elapsed",
        )

    return NoWorkDecision(
        "omit",
        fingerprint,
        CANONICAL_SINK,
        prior.comment_id,
        "unchanged_within_refresh_interval",
    )
