"""Métrica de complejidad organizacional por WorkItem, sin score mágico."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any

from evolution.constitution import PROTECTED_INVARIANTS
from evolution.fitness import compare_fitness


VERSION = 1
MAX_ITEMS = 64
MAX_OBSERVATIONS = 1_000

RISKS = frozenset({"low", "medium", "high", "critical"})
SIZES = frozenset({"small", "medium", "large"})
RISK_MULTIPLIER = {
    "low": 0.85,
    "medium": 1.0,
    "high": 1.2,
    "critical": 1.4,
}
BASE_LIMITS = {
    "small": {
        "rules_consulted": 6,
        "active_roles": 3,
        "reviewers": 2,
        "checks": 6,
        "handoffs": 1,
        "engines_consulted": 4,
        "overhead_ratio": 0.55,
    },
    "medium": {
        "rules_consulted": 10,
        "active_roles": 5,
        "reviewers": 3,
        "checks": 10,
        "handoffs": 2,
        "engines_consulted": 6,
        "overhead_ratio": 0.65,
    },
    "large": {
        "rules_consulted": 16,
        "active_roles": 7,
        "reviewers": 4,
        "checks": 14,
        "handoffs": 4,
        "engines_consulted": 8,
        "overhead_ratio": 0.75,
    },
}
OBSERVATION_FIELDS = frozenset(
    {
        "version",
        "work_id",
        "comparison_scope",
        "task_type",
        "task_size",
        "risk",
        "rules_consulted",
        "active_roles",
        "reviewers",
        "checks",
        "handoffs",
        "engines_consulted",
        "context_tokens",
        "coordination_minutes",
        "wait_minutes",
        "review_minutes",
        "useful_execution_minutes",
        "protected_metrics",
        "evidence_refs",
        "observed_at",
    }
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+-]{0,159}$")
_SLUG = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class OrganizationalComplexityError(ValueError):
    """Entrada o comparación de complejidad organizacional inválida."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _number(value: Any, label: str, *, positive: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrganizationalComplexityError(f"{label} debe ser número.")
    if isinstance(value, float) and not math.isfinite(value):
        raise OrganizationalComplexityError(f"{label} debe ser finito.")
    if value < 0 or (positive and value <= 0):
        raise OrganizationalComplexityError(f"{label} fuera de límites.")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrganizationalComplexityError(f"{label} debe ser entero >= 0.")
    return value


def _text(value: Any, label: str, *, slug: bool = False) -> str:
    if not isinstance(value, str):
        raise OrganizationalComplexityError(f"{label} debe ser texto.")
    normalized = value.strip()
    pattern = _SLUG if slug else _ID
    if not normalized or pattern.fullmatch(normalized) is None:
        raise OrganizationalComplexityError(f"{label} inválido.")
    return normalized


def _items(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_ITEMS
        or not all(isinstance(item, str) for item in value)
    ):
        raise OrganizationalComplexityError(f"{label} debe ser lista acotada.")
    normalized = [_text(item, f"{label}[]") for item in value]
    if len(normalized) != len(set(normalized)):
        raise OrganizationalComplexityError(f"{label} contiene duplicados.")
    return sorted(normalized)


def _protected_metrics(value: Any) -> dict[str, float | int | None]:
    expected = set(PROTECTED_INVARIANTS)
    if not isinstance(value, dict) or set(value) != expected:
        raise OrganizationalComplexityError(
            "protected_metrics debe declarar exactamente invariantes constitucionales."
        )
    result: dict[str, float | int | None] = {}
    for key in sorted(expected):
        raw = value[key]
        if raw is None:
            result[key] = None
            continue
        number = _number(raw, f"protected_metrics.{key}")
        if not 0 <= number <= 1:
            raise OrganizationalComplexityError(
                f"protected_metrics.{key} debe estar entre 0 y 1."
            )
        result[key] = number
    return result


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise OrganizationalComplexityError("observed_at debe ser ISO-8601.")
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(
            raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        )
    except ValueError as exc:
        raise OrganizationalComplexityError(
            "observed_at debe ser ISO-8601."
        ) from exc
    if parsed.tzinfo is None:
        raise OrganizationalComplexityError(
            "observed_at debe incluir zona horaria."
        )
    return parsed.isoformat()


def normalize_observation(value: Any) -> dict[str, Any]:
    """Valida un snapshot de overhead sin inferir costo faltante como cero."""
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        raise OrganizationalComplexityError(
            "observación contiene campos faltantes o no permitidos."
        )
    if value["version"] != VERSION:
        raise OrganizationalComplexityError("version debe ser 1.")

    task_type = _text(value["task_type"], "task_type", slug=True)
    size = value["task_size"]
    risk = value["risk"]
    if size not in SIZES:
        raise OrganizationalComplexityError("task_size fuera del catálogo.")
    if risk not in RISKS:
        raise OrganizationalComplexityError("risk fuera del catálogo.")

    return {
        "version": VERSION,
        "work_id": _text(value["work_id"], "work_id"),
        "comparison_scope": _text(
            value["comparison_scope"],
            "comparison_scope",
        ),
        "task_type": task_type,
        "task_size": size,
        "risk": risk,
        "rules_consulted": _items(value["rules_consulted"], "rules_consulted"),
        "active_roles": _items(value["active_roles"], "active_roles"),
        "reviewers": _items(value["reviewers"], "reviewers"),
        "checks": _items(value["checks"], "checks"),
        "handoffs": _items(value["handoffs"], "handoffs"),
        "engines_consulted": _items(
            value["engines_consulted"],
            "engines_consulted",
        ),
        "context_tokens": _integer(value["context_tokens"], "context_tokens"),
        "coordination_minutes": _number(
            value["coordination_minutes"],
            "coordination_minutes",
        ),
        "wait_minutes": _number(value["wait_minutes"], "wait_minutes"),
        "review_minutes": _number(value["review_minutes"], "review_minutes"),
        "useful_execution_minutes": _number(
            value["useful_execution_minutes"],
            "useful_execution_minutes",
            positive=True,
        ),
        "protected_metrics": _protected_metrics(value["protected_metrics"]),
        "evidence_refs": _items(value["evidence_refs"], "evidence_refs"),
        "observed_at": _timestamp(value["observed_at"]),
    }


def _validate_cost_budgets(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise OrganizationalComplexityError("cost_budgets inválido.")
    sizes = value.get("sizes")
    multipliers = value.get("task_type_multipliers")
    if not isinstance(sizes, dict) or not isinstance(multipliers, dict):
        raise OrganizationalComplexityError("cost_budgets incompleto.")
    for size in SIZES:
        current = sizes.get(size)
        if not isinstance(current, dict):
            raise OrganizationalComplexityError("cost_budgets size inválido.")
        for key in ("tokens", "agent_minutes"):
            _number(current.get(key), f"cost_budgets.{size}.{key}", positive=True)
    default = multipliers.get("default")
    _number(default, "cost_budgets.default", positive=True)
    return value


def contextual_budget(
    observation: Any,
    cost_budgets: Any,
) -> dict[str, Any]:
    """Deriva budget contextual desde #7 + riesgo, sin tocar Constitution."""
    item = normalize_observation(observation)
    budgets = _validate_cost_budgets(cost_budgets)
    task_multiplier = budgets["task_type_multipliers"].get(
        item["task_type"],
        budgets["task_type_multipliers"]["default"],
    )
    task_multiplier = _number(
        task_multiplier,
        "task_type_multiplier",
        positive=True,
    )
    scale = task_multiplier * RISK_MULTIPLIER[item["risk"]]
    base = BASE_LIMITS[item["task_size"]]
    source = budgets["sizes"][item["task_size"]]

    limits: dict[str, float | int] = {}
    for key in (
        "rules_consulted",
        "active_roles",
        "reviewers",
        "checks",
        "handoffs",
        "engines_consulted",
    ):
        limits[key] = max(1, round(base[key] * scale))

    effective_tokens = source["tokens"] * scale
    effective_agent_minutes = source["agent_minutes"] * scale
    limits.update(
        {
            "context_tokens": max(1, round(effective_tokens * 0.25)),
            "coordination_minutes": round(effective_agent_minutes * 0.25, 3),
            "wait_minutes": round(effective_agent_minutes * 0.50, 3),
            "review_minutes": round(effective_agent_minutes * 0.35, 3),
            "overhead_ratio": round(
                min(
                    0.90,
                    base["overhead_ratio"]
                    + (RISK_MULTIPLIER[item["risk"]] - 1.0) * 0.20,
                ),
                4,
            ),
        }
    )
    return {
        "version": VERSION,
        "task_type": item["task_type"],
        "task_size": item["task_size"],
        "risk": item["risk"],
        "cost_budget_schema_version": budgets["schema_version"],
        "task_multiplier": task_multiplier,
        "risk_multiplier": RISK_MULTIPLIER[item["risk"]],
        "limits": limits,
        "protected_controls": sorted(PROTECTED_INVARIANTS),
    }


def _measurements(item: dict[str, Any]) -> dict[str, float | int]:
    overhead_minutes = (
        item["coordination_minutes"]
        + item["wait_minutes"]
        + item["review_minutes"]
    )
    total_minutes = overhead_minutes + item["useful_execution_minutes"]
    return {
        "rules_consulted": len(item["rules_consulted"]),
        "active_roles": len(item["active_roles"]),
        "reviewers": len(item["reviewers"]),
        "checks": len(item["checks"]),
        "handoffs": len(item["handoffs"]),
        "engines_consulted": len(item["engines_consulted"]),
        "context_tokens": item["context_tokens"],
        "coordination_minutes": item["coordination_minutes"],
        "wait_minutes": item["wait_minutes"],
        "review_minutes": item["review_minutes"],
        "useful_execution_minutes": item["useful_execution_minutes"],
        "organizational_overhead_minutes": round(overhead_minutes, 6),
        "total_minutes": round(total_minutes, 6),
        "overhead_ratio": round(overhead_minutes / total_minutes, 6),
        "governance_items": (
            len(item["rules_consulted"])
            + len(item["active_roles"])
            + len(item["reviewers"])
            + len(item["checks"])
            + len(item["handoffs"])
            + len(item["engines_consulted"])
        ),
    }


def evaluate_workitem_complexity(
    observation: Any,
    cost_budgets: Any,
) -> dict[str, Any]:
    """Evalúa cada dimensión contra su budget, sin colapsarlas a un score."""
    item = normalize_observation(observation)
    budget = contextual_budget(item, cost_budgets)
    measurements = _measurements(item)

    dimensions: dict[str, dict[str, Any]] = {}
    over: list[str] = []
    for key, limit in budget["limits"].items():
        observed = measurements[key]
        status = "over" if observed > limit else "within"
        dimensions[key] = {
            "observed": observed,
            "budget": limit,
            "status": status,
        }
        if status == "over":
            over.append(key)

    candidate = None
    if over:
        candidate = {
            "status": "candidate",
            "work_id": item["work_id"],
            "comparison_scope": item["comparison_scope"],
            "target_dimensions": sorted(over),
            "evidence_refs": list(item["evidence_refs"]),
            "protected_controls": sorted(PROTECTED_INVARIANTS),
            "authority": "unchanged",
            "execute": False,
        }

    result = {
        "version": VERSION,
        "work_id": item["work_id"],
        "comparison_scope": item["comparison_scope"],
        "task_type": item["task_type"],
        "task_size": item["task_size"],
        "risk": item["risk"],
        "measurements": measurements,
        "dimensions": dimensions,
        "over_budget_dimensions": sorted(over),
        "protected_controls": sorted(PROTECTED_INVARIANTS),
        "simplification_candidate": candidate,
        "evidence_refs": list(item["evidence_refs"]),
        "observed_at": item["observed_at"],
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def compare_simplification(
    before: Any,
    after: Any,
) -> dict[str, Any]:
    """Valida before/after con Fitness y bloquea regresiones protegidas."""
    left = normalize_observation(before)
    right = normalize_observation(after)
    comparable = (
        "comparison_scope",
        "task_type",
        "task_size",
        "risk",
    )
    if any(left[key] != right[key] for key in comparable):
        raise OrganizationalComplexityError(
            "before/after no pertenecen a una cohorte comparable."
        )

    def vector(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
        measures = _measurements(item)
        value = {
            key: {"value": item["protected_metrics"][key], "direction": "higher"}
            for key in sorted(PROTECTED_INVARIANTS)
        }
        value.update(
            {
                "organizational_overhead_minutes": {
                    "value": measures["organizational_overhead_minutes"],
                    "direction": "lower",
                },
                "context_tokens": {
                    "value": measures["context_tokens"],
                    "direction": "lower",
                },
                "governance_items": {
                    "value": measures["governance_items"],
                    "direction": "lower",
                },
            }
        )
        return value

    fitness = compare_fitness(
        baseline=vector(left),
        candidate=vector(right),
    )
    return {
        "version": VERSION,
        "comparison_scope": left["comparison_scope"],
        "before_work_id": left["work_id"],
        "after_work_id": right["work_id"],
        "fitness": fitness,
        "can_claim_simplification": (
            fitness["claim"] == "improved"
            and not fitness["protected_regressions"]
            and not fitness["missing_dimensions"]
        ),
        "authority": "unchanged",
        "execute": False,
    }


def build_complexity_report(
    observations: Any,
    cost_budgets: Any,
) -> dict[str, Any]:
    """Agrega costo útil y overhead manteniendo dimensiones separadas."""
    if (
        not isinstance(observations, list)
        or not observations
        or len(observations) > MAX_OBSERVATIONS
    ):
        raise OrganizationalComplexityError(
            "observations debe ser lista no vacía y acotada."
        )

    rows = [
        evaluate_workitem_complexity(item, cost_budgets)
        for item in observations
    ]
    ids = [row["work_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise OrganizationalComplexityError("work_id duplicado.")
    rows.sort(key=lambda row: row["work_id"])

    useful = sum(
        row["measurements"]["useful_execution_minutes"]
        for row in rows
    )
    overhead = sum(
        row["measurements"]["organizational_overhead_minutes"]
        for row in rows
    )
    total = useful + overhead
    over_counts: dict[str, int] = {}
    for row in rows:
        for dimension in row["over_budget_dimensions"]:
            over_counts[dimension] = over_counts.get(dimension, 0) + 1

    result = {
        "version": VERSION,
        "samples": len(rows),
        "useful_execution_minutes": round(useful, 6),
        "organizational_overhead_minutes": round(overhead, 6),
        "total_minutes": round(total, 6),
        "overhead_ratio": round(overhead / total, 6) if total else None,
        "simplification_candidates": sum(
            row["simplification_candidate"] is not None for row in rows
        ),
        "over_budget_counts": dict(sorted(over_counts.items())),
        "protected_controls": sorted(PROTECTED_INVARIANTS),
        "rows": rows,
    }
    result["fingerprint"] = _stable_hash(result)
    return result
