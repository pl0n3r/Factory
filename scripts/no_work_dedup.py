#!/usr/bin/env python3
"""Deduplicación pura de publicaciones NO_WORK del despachador.

No realiza I/O. El caller construye un snapshot global vivo, conserva la
identidad del comentario canónico y ejecuta la acción create|update|omit que
devuelve este módulo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

# Son campos del acto de observar, no de la lease ni de su bloqueo.
OBSERVATION_FIELDS = frozenset({"observed_at", "fetched_at", "captured_at"})
# `updated_at` es material salvo si viene explícitamente en este namespace.
OBSERVATION_METADATA_KEYS = OBSERVATION_FIELDS | {"updated_at"}


class NoWorkInventoryError(ValueError):
    """El snapshot no demuestra el inventario global requerido."""


@dataclass(frozen=True)
class NoWorkPublicationState:
    comment_id: int
    fingerprint: str
    published_at: int
    observed_at: int | None = None


@dataclass(frozen=True)
class NoWorkDecision:
    action: Literal["create", "update", "omit"]
    fingerprint: str
    sink: str
    comment_id: int | None
    reason: str
    observed_at: int
    expected_comment_id: int | None
    expected_fingerprint: str | None


@dataclass(frozen=True)
class NoWorkApplicationDecision:
    action: Literal["apply", "omit", "recompute"]
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


def _observation_timestamp(value: object) -> bool:
    if type(value) is int:
        return value >= 0
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        return False
    return instant.tzinfo is not None and instant.utcoffset() is not None


def _material_entry(value: object, *, noun: str) -> object:
    """Omite solo metadata observacional reconocida de reservas/bloqueos.

    Cualquier campo de dominio desconocido se conserva en la huella; nunca se
    borra `updated_at` si no se clasifica expresamente como observación.
    """
    if not isinstance(value, dict):
        return value
    for key in OBSERVATION_FIELDS:
        if key in value and not _observation_timestamp(value[key]):
            raise NoWorkInventoryError(f"observation_timestamp_invalid:{noun}:{key}")
    if "observation_metadata" in value:
        metadata = value["observation_metadata"]
        if not isinstance(metadata, dict) or any(
            not isinstance(key, str)
            or key not in OBSERVATION_METADATA_KEYS
            or not _observation_timestamp(timestamp)
            for key, timestamp in metadata.items()
        ):
            raise NoWorkInventoryError(f"observation_metadata_invalid:{noun}")
    return {
        key: item for key, item in value.items()
        if key not in OBSERVATION_FIELDS and key != "observation_metadata"
    }


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

    for field in ("available", "recovery"):
        issue_ids = value[field]
        if any(type(item) is not int or item <= 0 for item in issue_ids):
            raise NoWorkInventoryError(f"issue_ids_invalid:{name}:{field}")
        if len(set(issue_ids)) != len(issue_ids):
            raise NoWorkInventoryError(f"issue_ids_duplicate:{name}:{field}")

    # Las reservas V3 pueden usar "issue" o "issue_number" según el caller.
    # La forma inválida no debe producir una huella publicable.
    live_reservations = []
    for reservation in value["reservations"]:
        if not isinstance(reservation, dict):
            raise NoWorkInventoryError(f"reservation_invalid:{name}:shape")
        if type(reservation.get("active")) is not bool:
            raise NoWorkInventoryError(f"reservation_invalid:{name}:active")
        issue_id = reservation.get("issue", reservation.get("issue_number"))
        if type(issue_id) is not int or issue_id <= 0 or (
            "issue_number" in reservation
            and (
                type(reservation["issue_number"]) is not int
                or reservation["issue_number"] <= 0
                or reservation["issue_number"] != issue_id
            )
        ):
            raise NoWorkInventoryError(f"reservation_invalid:{name}:issue")
        reservation_id = reservation.get("reservation_id")
        if not isinstance(reservation_id, str) or not reservation_id.strip():
            raise NoWorkInventoryError(f"reservation_invalid:{name}:reservation_id")
        if not reservation["active"]:
            continue
        live_reservations.append(_material_entry(reservation, noun=f"reservation:{name}"))

    for blocker in value["blockers"]:
        if not isinstance(blocker, dict) and (
            type(blocker) is not int or blocker <= 0
        ):
            raise NoWorkInventoryError(f"blocker_invalid:{name}")

    open_prs = []
    for pr in value["pull_requests"]:
        if not isinstance(pr, dict):
            raise NoWorkInventoryError(f"pull_request_invalid:{name}")
        state = pr.get("state")
        if state != "open":
            if isinstance(state, str):
                continue
            raise NoWorkInventoryError(f"pull_request_state_invalid:{name}")
        number = pr.get("number")
        head_sha = pr.get("head_sha")
        if type(number) is not int or number <= 0:
            raise NoWorkInventoryError(f"pull_request_number_invalid:{name}")
        if (
            not isinstance(head_sha, str)
            or len(head_sha) not in (40, 64)
            or any(ch not in "0123456789abcdef" for ch in head_sha)
        ):
            raise NoWorkInventoryError(f"pull_request_head_invalid:{name}")
        open_prs.append(
            {
                "number": number,
                "state": "open",
                "head_sha": head_sha,
            }
        )

    return {
        "available": _stable(value["available"]),
        "recovery": _stable(value["recovery"]),
        "reservations": _stable(live_reservations),
        "blockers": _stable([
            _material_entry(blocker, noun=f"blocker:{name}")
            for blocker in value["blockers"]
        ]),
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
    published_at = _valid_now(value.published_at)
    observed_at = (
        published_at
        if value.observed_at is None
        else _valid_now(value.observed_at)
    )
    if observed_at > published_at:
        raise NoWorkInventoryError("observation_after_publication")
    if value.observed_at is None:
        return NoWorkPublicationState(
            comment_id=value.comment_id,
            fingerprint=value.fingerprint,
            published_at=published_at,
            observed_at=observed_at,
        )
    return value


def decide_no_work(
    snapshot: object,
    previous: NoWorkPublicationState | None,
    now: int,
    *,
    observed_at: int | None = None,
) -> NoWorkDecision:
    """Decide create|update|omit sin publicar ni leer GitHub."""
    decision_at = _valid_now(now)
    observation_at = (
        decision_at if observed_at is None else _valid_now(observed_at)
    )
    if observation_at > decision_at:
        raise NoWorkInventoryError("observation_in_future")

    prior = _valid_previous(previous)
    fingerprint = inventory_fingerprint(snapshot)

    if prior is None:
        return NoWorkDecision(
            "create",
            fingerprint,
            CANONICAL_SINK,
            None,
            "canonical_comment_missing",
            observation_at,
            None,
            None,
        )

    if decision_at < prior.published_at:
        raise NoWorkInventoryError("time_moved_backwards")

    if fingerprint != prior.fingerprint:
        return NoWorkDecision(
            "update",
            fingerprint,
            CANONICAL_SINK,
            prior.comment_id,
            "inventory_changed",
            observation_at,
            prior.comment_id,
            prior.fingerprint,
        )

    if decision_at - prior.published_at >= REFRESH_AFTER_SECONDS:
        return NoWorkDecision(
            "update",
            fingerprint,
            CANONICAL_SINK,
            prior.comment_id,
            "refresh_interval_elapsed",
            observation_at,
            prior.comment_id,
            prior.fingerprint,
        )

    return NoWorkDecision(
        "omit",
        fingerprint,
        CANONICAL_SINK,
        prior.comment_id,
        "unchanged_within_refresh_interval",
        observation_at,
        prior.comment_id,
        prior.fingerprint,
    )


def revalidate_no_work_application(
    decision: NoWorkDecision,
    current: NoWorkPublicationState | None,
) -> NoWorkApplicationDecision:
    """Revalida el sink canónico releído inmediatamente antes de mutar.

    El caller debe recomputar desde inventario vivo cuando esta función devuelve
    ``recompute``. ``apply`` es la única autorización para create/update.
    """
    if not isinstance(decision, NoWorkDecision):
        raise NoWorkInventoryError("decision_invalid")

    if decision.action == "omit":
        return NoWorkApplicationDecision("omit", "decision_already_omit")

    live = _valid_previous(current)

    if decision.action == "create":
        if live is None:
            return NoWorkApplicationDecision("apply", "canonical_still_missing")
        return NoWorkApplicationDecision("recompute", "canonical_created_concurrently")

    if live is None:
        return NoWorkApplicationDecision("recompute", "canonical_missing_before_update")

    if live.comment_id != decision.expected_comment_id:
        return NoWorkApplicationDecision("recompute", "comment_id_changed")

    if live.fingerprint != decision.expected_fingerprint:
        return NoWorkApplicationDecision("recompute", "fingerprint_changed")

    assert live.observed_at is not None
    if live.observed_at > decision.observed_at:
        return NoWorkApplicationDecision("recompute", "canonical_observation_newer")

    return NoWorkApplicationDecision("apply", "prewrite_revalidation_passed")
