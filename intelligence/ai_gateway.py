"""AI Gateway Phase 0: routing determinista de capabilities sin duplicar Dispatcher."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable

from scripts.work_origin import (
    idempotency_scope,
    validate_work_item,
    work_fingerprint,
)

_SLUG = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_DATA_LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_TRANSIENT = {"unavailable", "rate_limited"}
_SECRET_KEYS = {"secret", "token", "password", "api_key", "private_key"}


class AIGatewayError(ValueError):
    """Solicitud, policy o adapter no elegible."""


@dataclass(frozen=True)
class Adapter:
    provider: str
    model: str
    executor: str
    kind: str
    capabilities: frozenset[str]
    authority_levels: frozenset[str]
    max_data_classification: str
    estimated_cost: float
    quality: int
    security: int
    latency_ms: int
    available: bool = True
    fallback_allowed: bool = True
    outcome: str = "success"
    actual_cost: float | None = None
    governed_by_factory: bool = True
    workspace_ref: str | None = None


@dataclass(frozen=True)
class RoutingPolicy:
    max_cost: float
    data_classification: str
    min_quality: int
    min_security: int
    allowed_providers: frozenset[str]
    max_attempts: int = 2


def _slug(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AIGatewayError(f"{field} debe ser texto.")
    cleaned = value.strip().lower()
    if not _SLUG.fullmatch(cleaned):
        raise AIGatewayError(f"{field} inválido.")
    return cleaned


def _number(value: Any, field: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise AIGatewayError(f"{field} inválido.")
    return float(value)


def _score(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise AIGatewayError(f"{field} debe estar entre 0 y 100.")
    return value


def _no_secret_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.strip().lower() in _SECRET_KEYS:
                raise AIGatewayError("AI Gateway no acepta secretos en WorkItems, policy o adapters.")
            _no_secret_fields(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _no_secret_fields(item)


def normalize_policy(payload: Any) -> RoutingPolicy:
    if not isinstance(payload, dict):
        raise AIGatewayError("policy debe ser objeto.")
    _no_secret_fields(payload)
    expected = {
        "max_cost", "data_classification", "min_quality", "min_security",
        "allowed_providers", "max_attempts",
    }
    if set(payload) != expected:
        raise AIGatewayError("policy contiene campos faltantes o desconocidos.")
    classification = _slug(payload["data_classification"], "data_classification")
    if classification not in _DATA_LEVEL:
        raise AIGatewayError("data_classification fuera del catálogo.")
    providers_raw = payload["allowed_providers"]
    if not isinstance(providers_raw, (list, tuple, set)) or not providers_raw:
        raise AIGatewayError("allowed_providers debe ser colección no vacía.")
    providers = frozenset(_slug(value, "allowed_providers[]") for value in providers_raw)
    attempts = payload["max_attempts"]
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 5:
        raise AIGatewayError("max_attempts debe estar entre 1 y 5.")
    return RoutingPolicy(
        max_cost=_number(payload["max_cost"], "max_cost"),
        data_classification=classification,
        min_quality=_score(payload["min_quality"], "min_quality"),
        min_security=_score(payload["min_security"], "min_security"),
        allowed_providers=providers,
        max_attempts=attempts,
    )


def normalize_adapter(payload: Any) -> Adapter:
    if not isinstance(payload, dict):
        raise AIGatewayError("adapter debe ser objeto.")
    _no_secret_fields(payload)
    expected = {
        "provider", "model", "executor", "kind", "capabilities",
        "authority_levels", "max_data_classification", "estimated_cost",
        "quality", "security", "latency_ms", "available", "fallback_allowed",
        "outcome", "actual_cost", "governed_by_factory", "workspace_ref",
    }
    if set(payload) != expected:
        raise AIGatewayError("adapter contiene campos faltantes o desconocidos.")
    kind = _slug(payload["kind"], "kind")
    if kind not in {"manual", "api", "codex"}:
        raise AIGatewayError("kind fuera del catálogo.")
    classification = _slug(payload["max_data_classification"], "max_data_classification")
    if classification not in _DATA_LEVEL:
        raise AIGatewayError("max_data_classification fuera del catálogo.")
    capabilities = payload["capabilities"]
    authorities = payload["authority_levels"]
    if not isinstance(capabilities, (list, tuple, set)) or not capabilities:
        raise AIGatewayError("capabilities debe ser colección no vacía.")
    if not isinstance(authorities, (list, tuple, set)) or not authorities:
        raise AIGatewayError("authority_levels debe ser colección no vacía.")
    outcome = _slug(payload["outcome"], "outcome")
    if outcome not in {"success", "unavailable", "rate_limited", "failed"}:
        raise AIGatewayError("outcome fuera del catálogo.")
    actual = payload["actual_cost"]
    if actual is not None:
        actual = _number(actual, "actual_cost")
    for field in ("available", "fallback_allowed", "governed_by_factory"):
        if not isinstance(payload[field], bool):
            raise AIGatewayError(f"{field} debe ser booleano.")
    workspace = payload["workspace_ref"]
    if workspace is not None and (not isinstance(workspace, str) or not workspace.strip()):
        raise AIGatewayError("workspace_ref inválido.")
    return Adapter(
        provider=_slug(payload["provider"], "provider"),
        model=_slug(payload["model"], "model"),
        executor=_slug(payload["executor"], "executor"),
        kind=kind,
        capabilities=frozenset(_slug(v, "capabilities[]") for v in capabilities),
        authority_levels=frozenset(_slug(v, "authority_levels[]") for v in authorities),
        max_data_classification=classification,
        estimated_cost=_number(payload["estimated_cost"], "estimated_cost"),
        quality=_score(payload["quality"], "quality"),
        security=_score(payload["security"], "security"),
        latency_ms=int(_number(payload["latency_ms"], "latency_ms")),
        available=payload["available"],
        fallback_allowed=payload["fallback_allowed"],
        outcome=outcome,
        actual_cost=actual,
        governed_by_factory=payload["governed_by_factory"],
        workspace_ref=workspace.strip() if isinstance(workspace, str) else None,
    )


def _eligible(
    item: dict[str, Any],
    capability: str,
    policy: RoutingPolicy,
    adapter: Adapter,
) -> tuple[bool, str]:
    if not adapter.available:
        return False, "provider-unavailable"
    if adapter.provider not in policy.allowed_providers:
        return False, "provider-not-allowed"
    if capability not in adapter.capabilities:
        return False, "capability-unsupported"
    if item["authority_level"] not in adapter.authority_levels:
        return False, "authority-not-allowed"
    if _DATA_LEVEL[policy.data_classification] > _DATA_LEVEL[adapter.max_data_classification]:
        return False, "data-policy-blocked"
    if adapter.estimated_cost > policy.max_cost:
        return False, "budget-blocked"
    if adapter.quality < policy.min_quality:
        return False, "quality-below-minimum"
    if adapter.security < policy.min_security:
        return False, "security-below-minimum"
    if adapter.kind == "codex":
        if not adapter.governed_by_factory:
            return False, "codex-outside-factory"
        if adapter.workspace_ref != item.get("repository_ref"):
            return False, "codex-workspace-mismatch"
    return True, ""


def route_capability(
    work_item: dict[str, Any],
    *,
    capability: str,
    policy: dict[str, Any],
    adapters: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Selecciona adapters elegibles sin alterar prioridad/readiness del WorkItem."""
    _no_secret_fields(work_item)
    item = validate_work_item(work_item)
    requested = _slug(capability, "capability")
    if requested not in item["requested_capabilities"]:
        raise AIGatewayError("capability no fue solicitada por el WorkItem.")
    normalized_policy = normalize_policy(policy)
    normalized_adapters = [normalize_adapter(adapter) for adapter in adapters]
    eligible: list[Adapter] = []
    rejected: list[dict[str, str]] = []
    for adapter in normalized_adapters:
        ok, reason = _eligible(item, requested, normalized_policy, adapter)
        if ok:
            eligible.append(adapter)
        else:
            rejected.append({
                "provider": adapter.provider,
                "model": adapter.model,
                "executor": adapter.executor,
                "reason": reason,
            })
    eligible.sort(
        key=lambda a: (
            a.estimated_cost,
            a.latency_ms,
            -a.quality,
            -a.security,
            a.provider,
            a.model,
            a.executor,
        )
    )
    if not eligible:
        reasons = sorted({entry["reason"] for entry in rejected})
        raise AIGatewayError("no-eligible-adapter:" + ",".join(reasons))
    return {
        "schema_version": 1,
        "work_id": item["work_id"],
        "work_fingerprint": work_fingerprint(work_item),
        "idempotency_scope": idempotency_scope(work_item),
        "capability": requested,
        "eligible": eligible,
        "rejected": rejected,
        "policy": normalized_policy,
    }


def execute_capability(
    work_item: dict[str, Any],
    *,
    capability: str,
    policy: dict[str, Any],
    adapters: Iterable[dict[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    """Ejecuta el adapter simulado/manual elegido y emite evidencia atribuible."""
    routed = route_capability(
        work_item,
        capability=capability,
        policy=policy,
        adapters=adapters,
    )
    item = validate_work_item(work_item)
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AIGatewayError("observed_at inválido.") from exc
    if observed.tzinfo is None:
        raise AIGatewayError("observed_at debe incluir zona horaria.")
    timestamp = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    policy_obj: RoutingPolicy = routed["policy"]
    trace: list[dict[str, Any]] = []
    for attempt, adapter in enumerate(routed["eligible"][: policy_obj.max_attempts], 1):
        trace.append({
            "attempt": attempt,
            "provider": adapter.provider,
            "model": adapter.model,
            "executor": adapter.executor,
            "kind": adapter.kind,
            "outcome": adapter.outcome,
            "estimated_cost": adapter.estimated_cost,
        })
        if adapter.outcome == "success":
            actual_cost = adapter.actual_cost if adapter.actual_cost is not None else adapter.estimated_cost
            evidence_ref = (
                f"ai-gateway:{item['work_id']}:{adapter.provider}:"
                f"{adapter.executor}:{attempt}"
            )
            feedback = {
                "work_id": item["work_id"],
                "work_fingerprint": routed["work_fingerprint"],
                "idempotency_scope": routed["idempotency_scope"],
                "executor_ref": f"{adapter.provider}/{adapter.executor}",
                "producer_ref": item["producer_ref"],
                "status": "success",
                "evidence_refs": [evidence_ref],
                "observed_at": timestamp,
            }
            return {
                "schema_version": 1,
                "status": "success",
                "work_id": item["work_id"],
                "capability": routed["capability"],
                "provider": adapter.provider,
                "model": adapter.model,
                "executor": adapter.executor,
                "kind": adapter.kind,
                "venture_id": item.get("venture_id"),
                "project_id": item.get("project_id"),
                "repository_ref": item.get("repository_ref"),
                "estimated_cost": adapter.estimated_cost,
                "actual_cost": actual_cost,
                "budget_ref": item.get("budget_ref"),
                "policy_ref": item["policy_ref"],
                "route_trace": trace,
                "rejected": routed["rejected"],
                "evidence_refs": [evidence_ref],
                "feedback": feedback,
            }
        if adapter.outcome in _TRANSIENT and adapter.fallback_allowed:
            continue
        raise AIGatewayError(
            f"execution-failed:{adapter.provider}:{adapter.executor}:{adapter.outcome}"
        )
    raise AIGatewayError("fallback-exhausted")
