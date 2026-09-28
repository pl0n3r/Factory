"""AI Gateway Phase 0: resuelve executor para un WorkItem ya despachado."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from scripts.work_origin import idempotency_scope, validate_work_item, work_fingerprint

DATA_LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
TRANSIENT = {"unavailable", "rate_limited"}
SECRET_FIELDS = {"secret", "token", "password", "api_key", "private_key"}


class AIGatewayError(ValueError):
    pass


@dataclass(frozen=True)
class Adapter:
    provider: str
    model: str
    executor: str
    kind: str
    capabilities: frozenset[str]
    authority_levels: frozenset[str]
    data_level: str
    cost: float
    quality: int
    security: int
    latency_ms: int
    outcome: str = "success"
    governed: bool = True
    workspace: str | None = None


def _reject_secrets(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_FIELDS:
                raise AIGatewayError("secret-field-not-allowed")
            _reject_secrets(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _reject_secrets(item)


def _policy(raw: dict[str, Any]) -> dict[str, Any]:
    required = {
        "max_cost", "data_classification", "min_quality", "min_security",
        "allowed_providers", "max_attempts",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise AIGatewayError("invalid-policy")
    _reject_secrets(raw)
    if raw["data_classification"] not in DATA_LEVEL:
        raise AIGatewayError("invalid-data-classification")
    if not isinstance(raw["allowed_providers"], list) or not raw["allowed_providers"]:
        raise AIGatewayError("invalid-allowed-providers")
    if not isinstance(raw["max_attempts"], int) or not 1 <= raw["max_attempts"] <= 5:
        raise AIGatewayError("invalid-max-attempts")
    return raw


def _adapter(raw: dict[str, Any]) -> Adapter:
    required = {
        "provider", "model", "executor", "kind", "capabilities", "authority_levels",
        "data_level", "cost", "quality", "security", "latency_ms", "outcome",
        "governed", "workspace",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise AIGatewayError("invalid-adapter")
    _reject_secrets(raw)
    if raw["kind"] not in {"manual", "api", "codex"}:
        raise AIGatewayError("invalid-adapter-kind")
    if raw["data_level"] not in DATA_LEVEL:
        raise AIGatewayError("invalid-adapter-data-level")
    if raw["outcome"] not in {"success", "unavailable", "rate_limited", "failed"}:
        raise AIGatewayError("invalid-adapter-outcome")
    return Adapter(
        provider=str(raw["provider"]),
        model=str(raw["model"]),
        executor=str(raw["executor"]),
        kind=str(raw["kind"]),
        capabilities=frozenset(raw["capabilities"]),
        authority_levels=frozenset(raw["authority_levels"]),
        data_level=str(raw["data_level"]),
        cost=float(raw["cost"]),
        quality=int(raw["quality"]),
        security=int(raw["security"]),
        latency_ms=int(raw["latency_ms"]),
        outcome=str(raw["outcome"]),
        governed=bool(raw["governed"]),
        workspace=raw["workspace"],
    )


def _reason(item: dict[str, Any], capability: str, policy: dict[str, Any], adapter: Adapter) -> str | None:
    if adapter.provider not in policy["allowed_providers"]:
        return "provider-not-allowed"
    if capability not in adapter.capabilities:
        return "capability-unsupported"
    if item["authority_level"] not in adapter.authority_levels:
        return "authority-not-allowed"
    if DATA_LEVEL[policy["data_classification"]] > DATA_LEVEL[adapter.data_level]:
        return "data-policy-blocked"
    if adapter.cost > policy["max_cost"]:
        return "budget-blocked"
    if adapter.quality < policy["min_quality"]:
        return "quality-below-minimum"
    if adapter.security < policy["min_security"]:
        return "security-below-minimum"
    if adapter.kind == "codex" and (
        not adapter.governed or adapter.workspace != item.get("repository_ref")
    ):
        return "codex-outside-factory"
    return None


def route_capability(
    work_item: dict[str, Any],
    *,
    capability: str,
    policy: dict[str, Any],
    adapters: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Elige adapters elegibles; no decide prioridad ni readiness de Factory."""
    _reject_secrets(work_item)
    item = validate_work_item(work_item)
    if capability not in item["requested_capabilities"]:
        raise AIGatewayError("capability-not-requested")
    rule = _policy(policy)
    eligible: list[Adapter] = []
    rejected: list[dict[str, str]] = []
    for raw in adapters:
        adapter = _adapter(raw)
        reason = _reason(item, capability, rule, adapter)
        if reason:
            rejected.append({"provider": adapter.provider, "model": adapter.model, "reason": reason})
        else:
            eligible.append(adapter)
    eligible.sort(key=lambda a: (a.cost, a.latency_ms, -a.quality, -a.security, a.provider, a.model))
    if not eligible:
        reasons = ",".join(sorted({entry["reason"] for entry in rejected}))
        raise AIGatewayError("no-eligible-adapter:" + reasons)
    return {
        "work_id": item["work_id"],
        "work_fingerprint": work_fingerprint(work_item),
        "idempotency_scope": idempotency_scope(work_item),
        "capability": capability,
        "eligible": eligible,
        "rejected": rejected,
        "policy": rule,
    }


def execute_capability(
    work_item: dict[str, Any],
    *,
    capability: str,
    policy: dict[str, Any],
    adapters: Iterable[dict[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    """Ejecuta adapters manuales/simulados con fallback transitorio y evidencia."""
    route = route_capability(work_item, capability=capability, policy=policy, adapters=adapters)
    item = validate_work_item(work_item)
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AIGatewayError("invalid-observed-at") from exc
    if observed.tzinfo is None:
        raise AIGatewayError("invalid-observed-at")
    timestamp = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    trace: list[dict[str, Any]] = []
    for attempt, adapter in enumerate(route["eligible"][: route["policy"]["max_attempts"]], 1):
        trace.append({
            "attempt": attempt, "provider": adapter.provider, "model": adapter.model,
            "executor": adapter.executor, "outcome": adapter.outcome, "cost": adapter.cost,
        })
        if adapter.outcome == "success":
            evidence = f"ai-gateway:{item['work_id']}:{adapter.provider}:{attempt}"
            feedback = {
                "work_id": item["work_id"],
                "work_fingerprint": route["work_fingerprint"],
                "idempotency_scope": route["idempotency_scope"],
                "executor_ref": f"{adapter.provider}/{adapter.executor}",
                "producer_ref": item["producer_ref"],
                "status": "success",
                "evidence_refs": [evidence],
                "observed_at": timestamp,
            }
            return {
                "status": "success", "work_id": item["work_id"], "capability": capability,
                "provider": adapter.provider, "model": adapter.model, "executor": adapter.executor,
                "kind": adapter.kind, "venture_id": item.get("venture_id"),
                "project_id": item.get("project_id"), "repository_ref": item.get("repository_ref"),
                "estimated_cost": adapter.cost, "actual_cost": adapter.cost,
                "budget_ref": item.get("budget_ref"), "policy_ref": item["policy_ref"],
                "route_trace": trace, "rejected": route["rejected"],
                "evidence_refs": [evidence], "feedback": feedback,
            }
        if adapter.outcome in TRANSIENT:
            continue
        raise AIGatewayError(f"execution-failed:{adapter.outcome}")
    raise AIGatewayError("fallback-exhausted")
