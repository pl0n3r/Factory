#!/usr/bin/env python3
"""Contrato puro de una iteración desatendida canónica Factory."""

from __future__ import annotations

import re

from scripts.dispatcher_v2 import (\n    UNATTENDED_ACTIONS,\n    UNATTENDED_CANONICAL_PAIRS,\n    _unattended_dispatch_gate,\n)
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import WatchdogDecision

CYCLE_VERSION = 1
FRESHNESS = frozenset({"fresh", "stale", "unknown"})
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
DISPATCH_KEYS = frozenset(
    {
        "selected",
        "selected_class",
        "next_action",
        "ready_not_selected",
        "excluded",
        "candidates",
        "aging_threshold",
        "active_tranche",
        "unattended",
    }
)
UNATTENDED_KEYS = frozenset({"enabled", "action", "authority", "reasons"})
PROVENANCE_KEYS = frozenset(
    {"head_sha", "dispatch_ref", "guard_ref", "watchdog_ref", "freshness"}
)


def _clean_provenance(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or set(value) != PROVENANCE_KEYS:
        return None
    head_sha = value["head_sha"]
    dispatch_ref = value["dispatch_ref"]
    guard_ref = value["guard_ref"]
    watchdog_ref = value["watchdog_ref"]
    freshness = value["freshness"]
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        return None
    if (
        not isinstance(dispatch_ref, str)
        or not dispatch_ref
        or dispatch_ref.strip() != dispatch_ref
        or len(dispatch_ref) > 256
    ):
        return None
    if not isinstance(guard_ref, str) or not FINGERPRINT_RE.fullmatch(guard_ref):
        return None
    if not isinstance(watchdog_ref, str) or not FINGERPRINT_RE.fullmatch(watchdog_ref):
        return None
    if freshness not in FRESHNESS:
        return None
    return {
        "head_sha": head_sha,
        "dispatch_ref": dispatch_ref,
        "guard_ref": guard_ref,
        "watchdog_ref": watchdog_ref,
        "freshness": freshness,
    }


def _blocked(
    reason: str,
    *,
    provenance: dict[str, object] | None = None,
    components: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "version": CYCLE_VERSION,
        "action": "BLOCKED",
        "authority": "unchanged",
        "selected": None,
        "selected_class": None,
        "freshness": "unknown" if provenance is None else provenance["freshness"],
        "reasons": (reason,),
        "provenance": provenance,
        "components": components or {},
    }


def compose_unattended_cycle(
    dispatch: object,
    guard: object,
    watchdog: object,
    *,
    provenance: object,
) -> dict[str, object]:
    """Compone resultados ya calculados; valida coherencia y nunca recalcula política."""

    clean_provenance = _clean_provenance(provenance)
    if clean_provenance is None:
        return _blocked("cycle_provenance_invalid")

    if not isinstance(guard, GuardDecision):
        return _blocked("cycle_guard_invalid", provenance=clean_provenance)
    if not isinstance(watchdog, WatchdogDecision):
        return _blocked("cycle_watchdog_invalid", provenance=clean_provenance)
    if (
        guard.authority != "unchanged"
        or watchdog.authority != "unchanged"
        or guard.action not in UNATTENDED_ACTIONS
        or watchdog.action not in UNATTENDED_ACTIONS
    ):
        return _blocked("cycle_component_contract_invalid", provenance=clean_provenance)
    if (
        clean_provenance["guard_ref"] != guard.evidence_fingerprint
        or clean_provenance["watchdog_ref"] != watchdog.evidence_fingerprint
    ):
        return _blocked("cycle_evidence_ref_mismatch", provenance=clean_provenance)

    canonical_action, canonical_reasons = _unattended_dispatch_gate(guard, watchdog)
    expected_watchdog_reason = f"unattended_watchdog_{watchdog.action.lower()}"
    canonical_contract = (
        canonical_action == "ALLOW" and canonical_reasons == ()
        if watchdog.action == "ALLOW"
        else canonical_action == watchdog.action
        and expected_watchdog_reason in canonical_reasons
    )
    if not canonical_contract:
        return _blocked("cycle_component_contract_invalid", provenance=clean_provenance)

    if not isinstance(dispatch, dict) or set(dispatch) != DISPATCH_KEYS:
        return _blocked("cycle_dispatch_shape_invalid", provenance=clean_provenance)
    unattended = dispatch.get("unattended")
    if not isinstance(unattended, dict) or set(unattended) != UNATTENDED_KEYS:
        return _blocked("cycle_dispatch_unattended_invalid", provenance=clean_provenance)
    if (
        unattended["enabled"] is not True
        or unattended["authority"] != "unchanged"
        or unattended["action"] not in UNATTENDED_ACTIONS
        or not isinstance(unattended["reasons"], tuple)
        or any(not isinstance(reason, str) or not reason for reason in unattended["reasons"])
    ):
        return _blocked("cycle_dispatch_unattended_invalid", provenance=clean_provenance)

    components = {
        "dispatch": {
            "action": unattended["action"],
            "reasons": unattended["reasons"],
            "selected": dispatch["selected"],
            "selected_class": dispatch["selected_class"],
            "dispatch_ref": clean_provenance["dispatch_ref"],
        },
        "guard": {
            "action": guard.action,
            "reasons": guard.reasons,
            "evidence_ref": guard.evidence_fingerprint,
        },
        "watchdog": {
            "action": watchdog.action,
            "incident_codes": tuple(incident.code for incident in watchdog.incidents),
            "state_freshness": watchdog.daily_summary.state_freshness,
            "interrupt_owner": watchdog.interrupt_owner,
            "evidence_ref": watchdog.evidence_fingerprint,
        },
    }

    if (guard.action, watchdog.action) not in UNATTENDED_CANONICAL_PAIRS:
        return _blocked(
            "cycle_component_pair_incoherent",
            provenance=clean_provenance,
            components=components,
        )
    if unattended["action"] != watchdog.action:
        return _blocked(
            "cycle_component_action_mismatch",
            provenance=clean_provenance,
            components=components,
        )
    if unattended["action"] != "ALLOW" and (
        dispatch["selected"] is not None or dispatch["ready_not_selected"] != []
    ):
        return _blocked(
            "cycle_suppression_incoherent",
            provenance=clean_provenance,
            components=components,
        )
    if clean_provenance["freshness"] != "fresh":
        return _blocked(
            "cycle_evidence_not_fresh",
            provenance=clean_provenance,
            components=components,
        )
    if watchdog.daily_summary.state_freshness != "fresh":
        return _blocked(
            "cycle_watchdog_state_not_fresh",
            provenance=clean_provenance,
            components=components,
        )

    return {
        "version": CYCLE_VERSION,
        "action": unattended["action"],
        "authority": "unchanged",
        "selected": dispatch["selected"],
        "selected_class": dispatch["selected_class"],
        "freshness": "fresh",
        "reasons": unattended["reasons"],
        "provenance": clean_provenance,
        "components": components,
    }
