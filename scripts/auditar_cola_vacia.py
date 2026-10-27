#!/usr/bin/env python3
"""Auditor de cola F1082: sólo fixtures offline, cero GitHub/red/escrituras.

Entrada JSON mínima (stdin): version=1, source="fixture", complete=true,
issues=[{number,kind,status,parent,blocker}].
La lista DEBE contener el inventario completo de Issues de ese repositorio.
El resultado describe trabajo, nunca otorga permisos ni crea reservas.
"""
from __future__ import annotations

import json
import sys
from typing import Any

KINDS = frozenset({"roadmap", "container", "leaf"})
STATUSES = frozenset({
    "disponible", "reservado", "bloqueado", "planificado",
    "en revisión", "requiere recuperación", "completado", "cancelado",
})
BLOCKERS = frozenset({"dependency", "claims", "human_gate", "technical"})
TERMINAL = frozenset({"completado", "cancelado"})
MAX_ISSUES = 3100
MAX_BYTES = 1_000_000

# Nunca incluir el contenido de entrada, texto libre ni identidad de personas
# en respuestas UNKNOWN, incluidas excepciones del parser.
UNKNOWN: dict[str, object] = {
    "state": "UNKNOWN",
    "action_required": False,
    "available_count": None,
    "pending_count": None,
    "findings": [],
}

ACTIONS = {
    "dependency": "RESOLVER_DEPENDENCIA",
    "claims": "RESOLVER_COLISION_CLAIMS",
    "human_gate": "VERIFICAR_PUERTA_HUMANA",
    "technical": "REPARAR_BLOQUEO_TECNICO",
}


class IncompleteInventory(ValueError):
    """El fixture no demuestra una cola completa, inequívoca y sintética."""


def _require(value: object, typ: type) -> None:
    if type(value) is not typ:
        raise IncompleteInventory("invalid_shape")


def _validate(snapshot: object) -> list[dict[str, object]]:
    _require(snapshot, dict)
    if set(snapshot) != {"version", "source", "complete", "issues"}:
        raise IncompleteInventory("unknown_or_missing_fields")
    if type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise IncompleteInventory("unsupported_version")
    if snapshot["source"] != "fixture" or snapshot["complete"] is not True:
        raise IncompleteInventory("untrusted_or_partial_inventory")
    issues = snapshot["issues"]
    _require(issues, list)
    if len(issues) > MAX_ISSUES:
        raise IncompleteInventory("inventory_too_large")

    rows: dict[int, dict[str, object]] = {}
    for item in issues:
        _require(item, dict)
        if set(item) != {"number", "kind", "status", "parent", "blocker"}:
            raise IncompleteInventory("unknown_or_missing_issue_fields")
        number, kind, status = item["number"], item["kind"], item["status"]
        parent, blocker = item["parent"], item["blocker"]
        if type(number) is not int or number < 1 or number in rows:
            raise IncompleteInventory("invalid_or_duplicate_issue")
        if type(kind) is not str or kind not in KINDS:
            raise IncompleteInventory("unknown_kind")
        if type(status) is not str or status not in STATUSES:
            raise IncompleteInventory("unknown_status")
        if parent is not None and (
            type(parent) is not int or parent < 1 or parent == number
        ):
            raise IncompleteInventory("unknown_parent")
        if status == "bloqueado":
            if type(blocker) is not str or blocker not in BLOCKERS:
                raise IncompleteInventory("unknown_blocker")
        elif blocker is not None:
            raise IncompleteInventory("contradictory_blocker")
        rows[number] = item

    for number, item in rows.items():
        visited: set[int] = {number}
        ancestor = item["parent"]
        while ancestor is not None:
            if ancestor not in rows or ancestor in visited:
                raise IncompleteInventory("orphan_or_cycle")
            visited.add(ancestor)
            parent = rows[ancestor]
            if parent["kind"] == "leaf":
                raise IncompleteInventory("leaf_cannot_contain_issues")
            ancestor = parent["parent"]

    return list(rows.values())


def audit(snapshot: object) -> dict[str, object]:
    """Diagnóstico puro. Datos faltantes/ambiguos => UNKNOWN, nunca éxito."""
    try:
        issues = _validate(snapshot)
    except (IncompleteInventory, TypeError, KeyError, ValueError):
        return dict(UNKNOWN)

    children: dict[int, list[int]] = {row["number"]: [] for row in issues}
    by_id = {row["number"]: row for row in issues}
    for row in issues:
        if row["parent"] is not None:
            children[row["parent"]].append(row["number"])

    def contains_leaf(root: int) -> bool:
        pending = list(children[root])
        while pending:
            current = pending.pop()
            if by_id[current]["kind"] == "leaf":
                return True
            pending.extend(children[current])
        return False

    available = [r for r in issues if r["kind"] == "leaf"
                 and r["status"] == "disponible"]
    pending = [r for r in issues if r["status"] not in TERMINAL]
    findings: list[dict[str, object]] = []

    for row in sorted(pending, key=lambda item: item["number"]):
        number, kind, status = row["number"], row["kind"], row["status"]
        if kind in {"roadmap", "container"} and not contains_leaf(number):
            findings.append({
                "issue": number,
                "reason": "ROADMAP_SIN_HOJAS" if kind == "roadmap"
                          else "CONTENEDOR_SIN_HOJAS",
                "action": "DESCOMPONER_HOJAS" if kind == "roadmap"
                          else "MATERIALIZAR_HOJAS",
            })
        if status == "bloqueado":
            findings.append({
                "issue": number, "reason": "HOJA_BLOQUEADA" if kind == "leaf"
                          else "CONTENEDOR_BLOQUEADO",
                "action": ACTIONS[row["blocker"]],
            })
        elif kind == "leaf" and status == "planificado":
            findings.append({
                "issue": number, "reason": "HOJA_PLANIFICADA",
                "action": "VALIDAR_ELEGIBILIDAD",
            })
        elif kind == "leaf" and status == "requiere recuperación":
            findings.append({
                "issue": number, "reason": "RESERVA_RECUPERABLE",
                "action": "RECUPERAR_RESERVA_V3",
            })

    if available:
        state = "COLA_DISPONIBLE"
    elif pending:
        state = "COLA_VACIA_CON_PENDIENTES"
    else:
        state = "SIN_TRABAJO_PENDIENTE"
    return {
        "state": state,
        "action_required": state == "COLA_VACIA_CON_PENDIENTES",
        "available_count": len(available),
        "pending_count": len(pending),
        "findings": findings,
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise IncompleteInventory("duplicate_json_key")
        value[key] = item
    return value


def parse_fixture(raw: str) -> dict[str, object]:
    """Rechaza JSON no finito, keys duplicadas y payloads con PII no prevista."""
    if len(raw.encode("utf-8")) > MAX_BYTES:
        return dict(UNKNOWN)
    try:
        snapshot = json.loads(
            raw, object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(
                IncompleteInventory("nonfinite_number")
            ),
        )
    except (ValueError, UnicodeError, IncompleteInventory):
        return dict(UNKNOWN)
    return audit(snapshot)


def main() -> int:
    raw = sys.stdin.read(MAX_BYTES + 1)
    report = parse_fixture(raw)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    # UNKNOWN no es veredicto exitoso para callers de CI/automatización.
    return 2 if report["state"] == "UNKNOWN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
