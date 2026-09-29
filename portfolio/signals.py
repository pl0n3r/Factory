"""Portfolio Signals v1: trade-offs descriptivos sin sustituir al dueño."""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

VERSION = 1
MAX_ITEMS = 100
MAX_REFS = 50
MAX_REF_LENGTH = 240

OWNER_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
SIGNALS = (
    "unlocks",
    "urgency",
    "risk",
    "cost",
    "impact",
    "reversibility",
)
SIGNAL_FIELDS = frozenset(
    {"status", "value", "confidence", "source", "provenance"}
)
ITEM_FIELDS = frozenset(
    {"version", "work_id", "owner_priority", "eligible", "signals"}
)
KNOWN_STATUS = "known"
UNKNOWN_STATUS = "unknown"
SOURCES = frozenset({"observed", "estimated", "declared"})
URGENCY = frozenset({"low", "medium", "high", "critical"})
RISK = frozenset({"low", "medium", "high", "critical"})
IMPACT = frozenset({"low", "medium", "high"})
REVERSIBILITY = frozenset(
    {"reversible", "partially_reversible", "irreversible"}
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+-]{0,159}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@+-]{0,239}$")


class PortfolioSignalsError(ValueError):
    """Entrada o comparación de Portfolio Signals inválida."""


def _json_size(value: Any) -> None:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PortfolioSignalsError(
            "entrada debe ser JSON finito y serializable."
        ) from exc
    if len(encoded.encode("utf-8")) > 100_000:
        raise PortfolioSignalsError("entrada excede tamaño máximo.")


def _mapping(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PortfolioSignalsError(
            f"{label} contiene campos faltantes o no permitidos."
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PortfolioSignalsError(f"{label} debe ser texto.")
    normalized = value.strip()
    if not normalized or _ID.fullmatch(normalized) is None:
        raise PortfolioSignalsError(f"{label} inválido.")
    return normalized


def _refs(value: Any, label: str, *, allow_empty: bool) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_REFS
        or (not allow_empty and not value)
    ):
        raise PortfolioSignalsError(f"{label} debe ser lista acotada.")
    refs: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or len(item) > MAX_REF_LENGTH
            or _REF.fullmatch(item) is None
        ):
            raise PortfolioSignalsError(f"{label} contiene referencia inválida.")
        refs.append(item)
    if len(refs) != len(set(refs)):
        raise PortfolioSignalsError(f"{label} contiene duplicados.")
    return sorted(refs)


def _confidence(value: Any, *, known: bool) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= 1
    ):
        raise PortfolioSignalsError("signal.confidence fuera de límites.")
    normalized = round(float(value), 6)
    if known and normalized <= 0:
        raise PortfolioSignalsError(
            "signal conocido requiere confidence > 0."
        )
    if not known and normalized != 0:
        raise PortfolioSignalsError(
            "signal unknown requiere confidence=0."
        )
    return normalized


def _nonnegative_number(value: Any, label: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise PortfolioSignalsError(f"{label} debe ser numérico >= 0.")
    return value


def _validate_value(signal: str, value: Any) -> Any:
    if signal == "unlocks":
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise PortfolioSignalsError(
                "unlocks.value debe ser entero >= 0."
            )
        return value
    if signal == "urgency":
        if value not in URGENCY:
            raise PortfolioSignalsError("urgency.value fuera del catálogo.")
        return value
    if signal == "risk":
        if value not in RISK:
            raise PortfolioSignalsError("risk.value fuera del catálogo.")
        return value
    if signal == "reversibility":
        if value not in REVERSIBILITY:
            raise PortfolioSignalsError(
                "reversibility.value fuera del catálogo."
            )
        return value
    if signal == "cost":
        expected = frozenset({"agent_minutes", "ci_minutes", "tokens"})
        cost = _mapping(value, expected, "cost.value")
        return {
            "agent_minutes": _nonnegative_number(
                cost["agent_minutes"],
                "cost.agent_minutes",
            ),
            "ci_minutes": _nonnegative_number(
                cost["ci_minutes"],
                "cost.ci_minutes",
            ),
            "tokens": _nonnegative_number(cost["tokens"], "cost.tokens"),
        }
    if signal == "impact":
        expected = frozenset({"technical", "product"})
        impact = _mapping(value, expected, "impact.value")
        technical = impact["technical"]
        product = impact["product"]
        if technical not in IMPACT or product not in IMPACT:
            raise PortfolioSignalsError(
                "impact.value debe usar low|medium|high."
            )
        return {"technical": technical, "product": product}
    raise PortfolioSignalsError("signal fuera del catálogo.")


def _signal(name: str, raw: Any) -> dict[str, Any]:
    data = _mapping(raw, SIGNAL_FIELDS, f"signals.{name}")
    status = data["status"]
    if status not in {KNOWN_STATUS, UNKNOWN_STATUS}:
        raise PortfolioSignalsError(
            f"signals.{name}.status fuera del catálogo."
        )
    known = status == KNOWN_STATUS
    confidence = _confidence(data["confidence"], known=known)
    if known:
        source = data["source"]
        if source not in SOURCES:
            raise PortfolioSignalsError(
                f"signals.{name}.source fuera del catálogo."
            )
        provenance = _refs(
            data["provenance"],
            f"signals.{name}.provenance",
            allow_empty=False,
        )
        value = _validate_value(name, data["value"])
    else:
        if data["value"] is not None or data["source"] is not None:
            raise PortfolioSignalsError(
                f"signals.{name} unknown no puede inventar valor/source."
            )
        provenance = _refs(
            data["provenance"],
            f"signals.{name}.provenance",
            allow_empty=True,
        )
        value = None
        source = None
    return {
        "status": status,
        "value": value,
        "confidence": confidence,
        "source": source,
        "provenance": provenance,
    }


def validate_portfolio_item(payload: Any) -> dict[str, Any]:
    """Valida un WorkItem descriptivo sin derivar prioridad ni ganador."""
    _json_size(payload)
    data = _mapping(payload, ITEM_FIELDS, "portfolio_item")
    if data["version"] != VERSION:
        raise PortfolioSignalsError("version debe ser 1.")
    priority = data["owner_priority"]
    if priority not in OWNER_PRIORITIES:
        raise PortfolioSignalsError(
            "owner_priority fuera del catálogo."
        )
    if type(data["eligible"]) is not bool:
        raise PortfolioSignalsError("eligible debe ser booleano.")
    signals = data["signals"]
    if not isinstance(signals, Mapping) or set(signals) != set(SIGNALS):
        raise PortfolioSignalsError(
            "signals debe declarar exactamente las dimensiones requeridas."
        )
    return {
        "version": VERSION,
        "work_id": _text(data["work_id"], "work_id"),
        "owner_priority": priority,
        "eligible": data["eligible"],
        "signals": {
            name: _signal(name, signals[name])
            for name in SIGNALS
        },
    }


def explain_tradeoffs(items: Any) -> dict[str, Any]:
    """Expone dimensiones comparables sin ordenar ni decidir por el dueño."""
    _json_size(items)
    if (
        not isinstance(items, list)
        or not 2 <= len(items) <= MAX_ITEMS
    ):
        raise PortfolioSignalsError(
            "items debe contener entre 2 y 100 WorkItems."
        )
    normalized = [validate_portfolio_item(item) for item in items]
    ids = [item["work_id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise PortfolioSignalsError("work_id duplicado.")
    if not all(item["eligible"] for item in normalized):
        raise PortfolioSignalsError(
            "trade-offs solo aplican a WorkItems elegibles."
        )
    priorities = {item["owner_priority"] for item in normalized}
    if len(priorities) != 1:
        raise PortfolioSignalsError(
            "trade-offs solo comparan la misma owner_priority."
        )
    normalized.sort(key=lambda item: item["work_id"])

    dimensions: dict[str, list[dict[str, Any]]] = {}
    uncertainty: list[dict[str, str]] = []
    for signal in SIGNALS:
        rows = []
        for item in normalized:
            current = item["signals"][signal]
            rows.append(
                {
                    "work_id": item["work_id"],
                    **current,
                }
            )
            if current["status"] == UNKNOWN_STATUS:
                uncertainty.append(
                    {"work_id": item["work_id"], "signal": signal}
                )
        dimensions[signal] = rows

    return {
        "version": VERSION,
        "owner_priority": normalized[0]["owner_priority"],
        "owner_priority_authoritative": True,
        "items": normalized,
        "dimensions": dimensions,
        "uncertainty": sorted(
            uncertainty,
            key=lambda row: (row["work_id"], row["signal"]),
        ),
        "decision": None,
        "authority": "owner_unchanged",
    }
