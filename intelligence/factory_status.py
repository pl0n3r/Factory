"""Vista derivada y fail-closed del estado global de tandas de Factory."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

CANONICAL_TANDA2_EPICS = (
    {"project": "Condor", "repository_ref": "pl0n3r/Condor", "issue_number": 192,
     "issue_ref": "Condor#192", "url": "https://github.com/pl0n3r/Condor/issues/192"},
    {"project": "GrindFlow", "repository_ref": "pl0n3r/GrindFlow", "issue_number": 129,
     "issue_ref": "GrindFlow#129", "url": "https://github.com/pl0n3r/GrindFlow/issues/129"},
    {"project": "BRVTAL", "repository_ref": "pl0n3r/brvtal", "issue_number": 630,
     "issue_ref": "brvtal#630", "url": "https://github.com/pl0n3r/brvtal/issues/630"},
    {"project": "FactoryRunner", "repository_ref": "pl0n3r/FactoryRunner", "issue_number": 1,
     "issue_ref": "FactoryRunner#1", "url": "https://github.com/pl0n3r/FactoryRunner/issues/1"},
)

# Snapshot normalizado de la vista comprometida; GitHub sigue siendo autoridad.
COMMITTED_TANDA2_EVIDENCE = (
    {"repository_ref": "pl0n3r/Condor", "issue_number": 192, "state": "closed",
     "state_reason": "completed", "labels": ("estado: completado",),
     "updated_at": "2026-09-26T20:01:32Z", "url": "https://github.com/pl0n3r/Condor/issues/192"},
    {"repository_ref": "pl0n3r/GrindFlow", "issue_number": 129, "state": "closed",
     "state_reason": "completed", "labels": ("estado: completado",),
     "updated_at": "2026-09-30T17:03:36Z", "url": "https://github.com/pl0n3r/GrindFlow/issues/129"},
    {"repository_ref": "pl0n3r/brvtal", "issue_number": 630, "state": "closed",
     "state_reason": "completed", "labels": ("status: completed",),
     "updated_at": "2026-09-30T13:42:20Z", "url": "https://github.com/pl0n3r/brvtal/issues/630"},
    {"repository_ref": "pl0n3r/FactoryRunner", "issue_number": 1, "state": "closed",
     "state_reason": "completed", "labels": ("estado: completado",),
     "updated_at": "2026-09-29T05:02:05Z", "url": "https://github.com/pl0n3r/FactoryRunner/issues/1"},
)

_COMPLETION_LABELS = frozenset({"estado: completado", "status: completed"})


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("updated_at debe ser timestamp UTC terminado en Z.")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _normalize_row(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("evidence debe contener objetos.")
    required = {
        "repository_ref", "issue_number", "state", "state_reason",
        "labels", "updated_at", "url",
    }
    if set(raw) != required:
        raise ValueError("fila de evidencia incompleta o con campos desconocidos.")
    if not isinstance(raw["issue_number"], int) or isinstance(raw["issue_number"], bool):
        raise ValueError("issue_number inválido.")
    if not isinstance(raw["labels"], (list, tuple)):
        raise ValueError("labels debe ser secuencia.")
    labels = tuple(sorted({str(value).strip() for value in raw["labels"] if str(value).strip()}))
    return {
        "repository_ref": str(raw["repository_ref"]).strip(),
        "issue_number": raw["issue_number"],
        "state": str(raw["state"]).strip().lower(),
        "state_reason": str(raw["state_reason"]).strip().lower(),
        "completion_label": bool(_COMPLETION_LABELS.intersection(labels)),
        "updated_at": _timestamp(raw["updated_at"]),
        "url": str(raw["url"]).strip(),
    }


def derive_factory_status(evidence: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Deriva tandas desde evidencia normalizada; ante duda nunca activa TANDA 3."""
    reasons: list[str] = []
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    try:
        for raw in evidence:
            row = _normalize_row(raw)
            key = (row["repository_ref"], row["issue_number"])
            if key in rows:
                reasons.append(f"duplicate:{key[0]}#{key[1]}")
            else:
                rows[key] = row
    except (TypeError, ValueError) as exc:
        reasons.append(f"invalid_evidence:{exc}")

    normalized: list[dict[str, Any]] = []
    for epic in CANONICAL_TANDA2_EPICS:
        key = (epic["repository_ref"], epic["issue_number"])
        row = rows.get(key)
        if row is None:
            reasons.append(f"missing:{epic['issue_ref']}")
            continue
        if row["url"] != epic["url"]:
            reasons.append(f"url_mismatch:{epic['issue_ref']}")
        if (
            row["state"] != "closed"
            or row["state_reason"] != "completed"
            or not row["completion_label"]
        ):
            reasons.append(f"not_completed:{epic['issue_ref']}")
        normalized.append({**epic, **row})

    canonical_keys = {
        (epic["repository_ref"], epic["issue_number"])
        for epic in CANONICAL_TANDA2_EPICS
    }
    for key in sorted(set(rows) - canonical_keys):
        reasons.append(f"unexpected:{key[0]}#{key[1]}")

    normalized.sort(key=lambda row: row["issue_ref"])
    encoded = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    freshness = max((row["updated_at"] for row in normalized), default="UNKNOWN")
    complete = not reasons and len(normalized) == len(CANONICAL_TANDA2_EPICS)
    return {
        "tanda1": "COMPLETADA",
        "tanda2": "COMPLETADA" if complete else "UNKNOWN",
        "tanda3": "ACTIVA" if complete else "BLOQUEADA",
        "tanda3_active": complete,
        "freshness": freshness,
        "snapshot_sha256": fingerprint,
        "reasons": tuple(sorted(set(reasons))),
        "evidence": tuple(normalized),
    }


def render_estado(evidence: Iterable[Mapping[str, Any]]) -> str:
    """Renderiza ESTADO.md desde el snapshot suministrado, sin consultar red."""
    status = derive_factory_status(evidence)
    lines = [
        "# Estado derivado de la fábrica",
        "",
        "> Vista generada y no autoritativa. GitHub y los health/smoke reales siguen",
        "> siendo la fuente operativa. Si esta vista deriva o queda vieja, falla cerrado",
        "> y debe regenerarse desde evidencia canónica.",
        "",
        f"- **TANDA 1:** {status['tanda1']}",
        f"- **TANDA 2:** {status['tanda2']}",
        f"- **TANDA 3:** {status['tanda3']}",
        f"- **Freshness de evidencia:** `{status['freshness']}` (máximo `updated_at` del snapshot)",
        f"- **Snapshot SHA-256:** `{status['snapshot_sha256']}`",
        "",
        "## Evidencia canónica de TANDA 2",
        "",
        "| Proyecto | Épico | Estado normalizado | updated_at | Fuente |",
        "| --- | --- | --- | --- | --- |",
    ]
    by_ref = {row["issue_ref"]: row for row in status["evidence"]}
    for epic in CANONICAL_TANDA2_EPICS:
        row = by_ref.get(epic["issue_ref"])
        completed = bool(
            row
            and row["state"] == "closed"
            and row["state_reason"] == "completed"
            and row["completion_label"]
            and row["url"] == epic["url"]
        )
        state = "COMPLETADO" if completed else "UNKNOWN"
        updated_at = row["updated_at"] if row else "UNKNOWN"
        lines.append(
            f"| {epic['project']} | {epic['issue_ref']} | {state} | "
            f"`{updated_at}` | [{epic['url']}]({epic['url']}) |"
        )
    lines.extend([
        "",
        "## Semántica fail-closed",
        "",
        "TANDA 3 solo figura ACTIVA cuando los cuatro épicos canónicos están presentes,",
        "cerrados, con razón `completed` y etiqueta de completado coherente. Evidencia",
        "faltante, abierta, contradictoria, no terminal o de otra URL produce TANDA 2",
        "UNKNOWN y mantiene TANDA 3 BLOQUEADA.",
    ])
    if status["reasons"]:
        lines.extend([
            "",
            "Razones actuales: " + ", ".join(f"`{reason}`" for reason in status["reasons"]),
        ])
    return "\n".join(lines) + "\n"


def render_committed_estado() -> str:
    """Generador declarado en derived_views.json para el snapshot comprometido."""
    return render_estado(COMMITTED_TANDA2_EVIDENCE)
