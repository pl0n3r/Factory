"""Capability × authority contract for Factory Living Software.

Authority is granted only by authenticated provenance. Autonomy may change how
much supervision an already-authorized capability needs, never what it may do.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from evolution.autonomy import AUTONOMY_LEVELS
from evolution.provenance import (
    AuthenticatedDecisionReader,
    is_authenticated_decision_reader,
)


AUTHORITY_VERSION = 1
ACTIONS = ("observe", "propose", "experiment", "execute", "promote_adopt")
AUTHORITY_CLASSES = (
    "operational",
    "money",
    "legal",
    "personal_data",
    "irreversible_delete",
    "authority_expansion",
)
RESERVED_AUTHORITY_CLASSES = frozenset(AUTHORITY_CLASSES[1:])
MAX_ITEMS = 32


class CapabilityAuthorityError(ValueError):
    """Invalid or untrusted authority input."""


@dataclass(frozen=True)
class CapabilityGrant:
    grant_id: str
    capability: str
    actions: tuple[str, ...]
    scopes: tuple[str, ...]
    targets: tuple[str, ...]
    authority_class: str
    human_gate: bool
    degrade_on: tuple[str, ...]
    revoke_on: tuple[str, ...]
    decision_ref: str
    source_id: str
    decision_fingerprint: str
    reason: str
    active: bool = True


@dataclass(frozen=True)
class AuthorityEvent:
    sequence: int
    event: str
    grant_id: str
    actor_ref: str
    reason: str
    decision_ref: str
    source_id: str
    decision_fingerprint: str


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, field: str, max_len: int = 240) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise CapabilityAuthorityError(f"{field} debe ser texto de una línea")
    return value.strip()


def _closed_list(
    value: Any,
    field: str,
    *,
    allowed: set[str] | None = None,
) -> tuple[str, ...]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_ITEMS
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise CapabilityAuthorityError(
            f"{field} debe contener 1..{MAX_ITEMS} valores"
        )
    normalized = tuple(sorted(set(item.strip() for item in value)))
    if len(normalized) != len(value):
        raise CapabilityAuthorityError(f"{field} contiene duplicados")
    if allowed is not None and not set(normalized) <= allowed:
        raise CapabilityAuthorityError(f"{field} contiene valores no admitidos")
    return normalized


def _validate_decision(
    decision_ref: Any,
    source: AuthenticatedDecisionReader | None,
    *,
    expected_operation: str,
) -> dict[str, Any]:
    ref = _text(decision_ref, "decision_ref")
    if not is_authenticated_decision_reader(source):
        raise CapabilityAuthorityError(
            "authority provenance no es una fuente autenticada"
        )
    payload = source.resolve_decision(ref)
    if not isinstance(payload, dict):
        raise CapabilityAuthorityError("decision_ref no existe en provenance")
    expected = {
        "version",
        "operation",
        "capability",
        "actions",
        "scopes",
        "targets",
        "authority_class",
        "degrade_on",
        "revoke_on",
        "actor_ref",
        "reason",
        "status",
        "grant_id",
        "fingerprint",
    }
    if set(payload) != expected:
        raise CapabilityAuthorityError(
            "decision de authority tiene campos incompletos o extra"
        )
    if (
        type(payload["version"]) is not int
        or payload["version"] != AUTHORITY_VERSION
    ):
        raise CapabilityAuthorityError("decision.version no admitida")
    if (
        payload["operation"] != expected_operation
        or payload["status"] != "resolved"
    ):
        raise CapabilityAuthorityError(
            "decision no está resuelta para la operación requerida"
        )
    unsigned = dict(payload)
    fingerprint = unsigned.pop("fingerprint")
    if (
        not isinstance(fingerprint, str)
        or fingerprint != _stable_hash(unsigned)
    ):
        raise CapabilityAuthorityError("decision fingerprint no coincide")
    return payload


def _normalized_grant_payload(decision: dict[str, Any]) -> dict[str, Any]:
    capability = _text(decision["capability"], "capability")
    authority_class = _text(decision["authority_class"], "authority_class")
    if authority_class not in AUTHORITY_CLASSES:
        raise CapabilityAuthorityError("authority_class no admitida")
    actions = _closed_list(
        decision["actions"], "actions", allowed=set(ACTIONS)
    )
    scopes = _closed_list(decision["scopes"], "scopes")
    targets = _closed_list(decision["targets"], "targets")
    degrade_on = _closed_list(decision["degrade_on"], "degrade_on")
    revoke_on = _closed_list(decision["revoke_on"], "revoke_on")
    if authority_class in RESERVED_AUTHORITY_CLASSES and any(
        action in {"experiment", "execute", "promote_adopt"}
        for action in actions
    ):
        raise CapabilityAuthorityError(
            "authority reservada permanece human-gated"
        )
    return {
        "capability": capability,
        "actions": actions,
        "scopes": scopes,
        "targets": targets,
        "authority_class": authority_class,
        "human_gate": authority_class in RESERVED_AUTHORITY_CLASSES,
        "degrade_on": degrade_on,
        "revoke_on": revoke_on,
        "reason": _text(decision["reason"], "reason", 500),
    }


class CapabilityAuthorityRegistry:
    """Append-only authority history with fail-closed evaluations."""

    def __init__(self) -> None:
        self._grants: dict[str, CapabilityGrant] = {}
        self._events: list[AuthorityEvent] = []

    @property
    def history(self) -> tuple[AuthorityEvent, ...]:
        return tuple(self._events)

    def grant(
        self,
        decision_ref: str,
        *,
        decision_source: AuthenticatedDecisionReader | None,
    ) -> CapabilityGrant:
        decision = _validate_decision(
            decision_ref,
            decision_source,
            expected_operation="grant",
        )
        normalized = _normalized_grant_payload(decision)
        actor_ref = _text(decision["actor_ref"], "actor_ref")
        requested_grant_id = _text(decision["grant_id"], "grant_id")
        canonical_id = _stable_hash(
            {
                **normalized,
                "decision_ref": decision_ref,
                "source_id": decision_source.source_id,
                "actor_ref": actor_ref,
            }
        )
        if requested_grant_id != canonical_id:
            raise CapabilityAuthorityError(
                "grant_id no coincide con el scope autorizado"
            )
        if canonical_id in self._grants:
            raise CapabilityAuthorityError("grant ya existe")
        grant = CapabilityGrant(
            grant_id=canonical_id,
            decision_ref=decision_ref,
            source_id=decision_source.source_id,
            decision_fingerprint=decision["fingerprint"],
            **normalized,
        )
        self._grants[canonical_id] = grant
        self._events.append(
            AuthorityEvent(
                sequence=len(self._events),
                event="grant",
                grant_id=canonical_id,
                actor_ref=actor_ref,
                reason=grant.reason,
                decision_ref=decision_ref,
                source_id=decision_source.source_id,
                decision_fingerprint=decision["fingerprint"],
            )
        )
        return grant

    def revoke(
        self,
        grant_id: str,
        decision_ref: str,
        *,
        decision_source: AuthenticatedDecisionReader | None,
    ) -> CapabilityGrant:
        key = _text(grant_id, "grant_id")
        current = self._grants.get(key)
        if current is None or not current.active:
            raise CapabilityAuthorityError("grant activo inexistente")
        decision = _validate_decision(
            decision_ref,
            decision_source,
            expected_operation="revoke",
        )
        actor_ref = _text(decision["actor_ref"], "actor_ref")
        if decision["grant_id"] != key:
            raise CapabilityAuthorityError(
                "revocación apunta a otro grant"
            )
        normalized = _normalized_grant_payload(decision)
        for field in (
            "capability",
            "actions",
            "scopes",
            "targets",
            "authority_class",
            "human_gate",
            "degrade_on",
            "revoke_on",
        ):
            if normalized[field] != getattr(current, field):
                raise CapabilityAuthorityError(
                    "revocación no coincide con el grant original"
                )
        revoked = CapabilityGrant(
            **{**asdict(current), "active": False}
        )
        self._grants[key] = revoked
        self._events.append(
            AuthorityEvent(
                sequence=len(self._events),
                event="revoke",
                grant_id=key,
                actor_ref=actor_ref,
                reason=normalized["reason"],
                decision_ref=decision_ref,
                source_id=decision_source.source_id,
                decision_fingerprint=decision["fingerprint"],
            )
        )
        return revoked

    def matrix(self, capability: str) -> dict[str, Any]:
        name = _text(capability, "capability")
        active = sorted(
            (
                grant
                for grant in self._grants.values()
                if grant.active and grant.capability == name
            ),
            key=lambda grant: grant.grant_id,
        )
        actions = {
            action: {
                "allowed": False,
                "scopes": [],
                "targets": [],
                "human_gate": False,
                "degrade_on": [],
                "revoke_on": [],
                "bindings": [],
            }
            for action in ACTIONS
        }
        for grant in active:
            for action in grant.actions:
                row = actions[action]
                row["allowed"] = True
                row["scopes"] = sorted(
                    set(row["scopes"]) | set(grant.scopes)
                )
                row["targets"] = sorted(
                    set(row["targets"]) | set(grant.targets)
                )
                row["human_gate"] = (
                    row["human_gate"] or grant.human_gate
                )
                row["degrade_on"] = sorted(
                    set(row["degrade_on"]) | set(grant.degrade_on)
                )
                row["revoke_on"] = sorted(
                    set(row["revoke_on"]) | set(grant.revoke_on)
                )
                row["bindings"].append(
                    {
                        "grant_id": grant.grant_id,
                        "scopes": list(grant.scopes),
                        "targets": list(grant.targets),
                        "human_gate": grant.human_gate,
                        "degrade_on": list(grant.degrade_on),
                        "revoke_on": list(grant.revoke_on),
                    }
                )
        return {
            "version": AUTHORITY_VERSION,
            "capability": name,
            "actions": actions,
            "grant_ids": [grant.grant_id for grant in active],
        }

    def authorize(
        self,
        capability: str,
        action: str,
        scope: str,
        target: str,
    ) -> bool:
        name = _text(capability, "capability")
        action_name = _text(action, "action")
        if action_name not in ACTIONS:
            return False
        scope_name = _text(scope, "scope")
        target_name = _text(target, "target")
        for grant in self._grants.values():
            if (
                grant.active
                and grant.capability == name
                and action_name in grant.actions
                and scope_name in grant.scopes
                and target_name in grant.targets
                and not grant.human_gate
            ):
                return True
        return False

    def autonomy_scope(
        self,
        capability: str,
        level: str,
    ) -> dict[str, Any]:
        """Return authority unchanged across autonomy levels."""
        if level not in AUTONOMY_LEVELS:
            raise CapabilityAuthorityError(
                "autonomy level no admitido"
            )
        matrix = self.matrix(capability)
        snapshot = {"level": level, "authority": matrix}
        snapshot["fingerprint"] = _stable_hash(matrix)
        return snapshot
