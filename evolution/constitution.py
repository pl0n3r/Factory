"""Constitución ejecutable de Factory Living Software.

La autoridad estable y los invariantes protegidos nunca son superficie de
mutación autónoma. Los candidatos solo pueden modificar namespaces evolutivos
declarados y deben aportar evidencia y rollback.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


class ConstitutionError(ValueError):
    """Contrato constitucional inválido o candidato no autorizado."""


CONSTITUTION_VERSION = 1
CONSTITUTION_PATH = Path(__file__).with_name("constitution.json")
PLAN_AGENTES_SOURCE = "PLAN-AGENTES.md"

EXPECTED_AUTHORITY_SOURCES = (
    PLAN_AGENTES_SOURCE,
    "AGENTES.md",
    "decisiones.yml",
    "seguridad/puertas-humanas.json",
    "docs/puertas-humanas.md",
    "docs/resiliencia-fabrica.md",
)
HUMAN_GATE_REGISTRY = "seguridad/puertas-humanas.json"
PROTECTED_INVARIANTS = (
    "security",
    "privacy",
    "traceability",
    "reversibility",
    "authority",
)
EXPECTED_INVARIANT_SOURCES = {
    "security": PLAN_AGENTES_SOURCE,
    "privacy": PLAN_AGENTES_SOURCE,
    "traceability": "AGENTES.md",
    "reversibility": "docs/resiliencia-fabrica.md",
    "authority": "docs/puertas-humanas.md",
}
EVOLVABLE_NAMESPACES = (
    "observations",
    "hypotheses",
    "experiments",
    "heuristics",
    "thresholds",
    "metrics",
    "autonomy_scores",
)
EXPECTED_LIFECYCLE = (
    "observe",
    "remember",
    "learn",
    "propose",
    "shadow",
    "experiment",
    "validate",
    "promote_or_reject",
    "measure",
    "prune",
    "rollback",
)
ALLOWED_OPERATIONS = ("add", "replace", "remove")
REQUIRED_CANDIDATE_FIELDS = ("version", "changes", "evidence", "rollback")
MAX_CANDIDATE_CHANGES = 32
MAX_JSON_VALUE_DEPTH = 32
MAX_JSON_VALUE_NODES = 4096
MAX_JSON_VALUE_BYTES = 1_048_576
_PATH = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def _exact_keys(value: Any, expected: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ConstitutionError(f"{name}: campos incompletos o adicionales")
    return value


def _unique_strings(value: Any, expected: tuple[str, ...], name: str) -> None:
    if (
        not isinstance(value, list)
        or tuple(value) != expected
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ConstitutionError(f"{name}: lista canónica inválida")


def validate_constitution(document: Any) -> dict[str, Any]:
    """Valida el contrato v1 con esquema cerrado y orden canónico."""
    root = _exact_keys(
        document,
        {
            "version",
            "stable_authority",
            "protected_invariants",
            "evolvable_state",
            "candidate_policy",
            "lifecycle",
        },
        "constitution",
    )
    if type(root["version"]) is not int or root["version"] != CONSTITUTION_VERSION:
        raise ConstitutionError("constitution: versión no admitida")

    authority = _exact_keys(
        root["stable_authority"],
        {"sources", "autonomous_mutation", "human_gate_registry"},
        "stable_authority",
    )
    _unique_strings(
        authority["sources"],
        EXPECTED_AUTHORITY_SOURCES,
        "stable_authority.sources",
    )
    if authority["human_gate_registry"] != HUMAN_GATE_REGISTRY:
        raise ConstitutionError("stable_authority: registro de puertas inválido")
    if authority["autonomous_mutation"] != "forbidden":
        raise ConstitutionError("stable_authority: mutación autónoma prohibida")

    invariants = _exact_keys(
        root["protected_invariants"],
        set(PROTECTED_INVARIANTS),
        "protected_invariants",
    )
    for invariant in PROTECTED_INVARIANTS:
        rule = _exact_keys(
            invariants[invariant],
            {"policy", "autonomous_mutation", "source"},
            f"protected_invariants.{invariant}",
        )
        if (
            rule["policy"] != "must_not_weaken"
            or rule["autonomous_mutation"] != "forbidden"
            or not isinstance(rule["source"], str)
            or rule["source"] != EXPECTED_INVARIANT_SOURCES[invariant]
            or rule["source"] not in authority["sources"]
        ):
            raise ConstitutionError(
                f"protected_invariants.{invariant}: regla o fuente no protegida"
            )

    evolvable = _exact_keys(
        root["evolvable_state"],
        {"namespaces"},
        "evolvable_state",
    )
    _unique_strings(
        evolvable["namespaces"],
        EVOLVABLE_NAMESPACES,
        "evolvable_state.namespaces",
    )

    policy = _exact_keys(
        root["candidate_policy"],
        {
            "version",
            "allowed_prefixes",
            "required_fields",
            "operations",
            "max_changes",
        },
        "candidate_policy",
    )
    if type(policy["version"]) is not int or policy["version"] != 1:
        raise ConstitutionError("candidate_policy: versión no admitida")

    expected_prefixes = tuple(
        f"evolution_state.{name}" for name in EVOLVABLE_NAMESPACES
    )
    _unique_strings(
        policy["allowed_prefixes"],
        expected_prefixes,
        "candidate_policy.allowed_prefixes",
    )
    _unique_strings(
        policy["required_fields"],
        REQUIRED_CANDIDATE_FIELDS,
        "candidate_policy.required_fields",
    )
    _unique_strings(
        policy["operations"],
        ALLOWED_OPERATIONS,
        "candidate_policy.operations",
    )
    if (
        type(policy["max_changes"]) is not int
        or policy["max_changes"] != MAX_CANDIDATE_CHANGES
    ):
        raise ConstitutionError("candidate_policy.max_changes inválido")

    _unique_strings(root["lifecycle"], EXPECTED_LIFECYCLE, "lifecycle")
    return root


def load_constitution() -> dict[str, Any]:
    """Carga exclusivamente el contrato canónico del repositorio."""
    try:
        raw = CONSTITUTION_PATH.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConstitutionError("no se pudo cargar la Constitución canónica") from exc
    return validate_constitution(document)


def _under_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + ".")


def _consume_json_budget(
    budget: dict[str, int],
    *,
    nodes: int = 0,
    byte_count: int = 0,
) -> None:
    budget["nodes"] += nodes
    budget["bytes"] += byte_count
    if budget["nodes"] > MAX_JSON_VALUE_NODES:
        raise ConstitutionError("candidate.change.value: presupuesto de nodos excedido")
    if budget["bytes"] > MAX_JSON_VALUE_BYTES:
        raise ConstitutionError("candidate.change.value: presupuesto de bytes excedido")


def _json_scalar_size(value: Any) -> int:
    try:
        return len(
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise ConstitutionError("candidate.change.value: valor no JSON") from exc


def _validate_json_value(
    value: Any,
    budget: dict[str, int],
    depth: int = 0,
    active: set[int] | None = None,
) -> None:
    if depth > MAX_JSON_VALUE_DEPTH:
        raise ConstitutionError("candidate.change.value: profundidad JSON excesiva")

    _consume_json_budget(budget, nodes=1)
    if value is None or isinstance(value, (str, bool, int)):
        _consume_json_budget(budget, byte_count=_json_scalar_size(value))
        return
    if isinstance(value, float):
        if math.isfinite(value):
            _consume_json_budget(budget, byte_count=_json_scalar_size(value))
            return
        raise ConstitutionError("candidate.change.value: número no finito")
    if not isinstance(value, (list, dict)):
        raise ConstitutionError("candidate.change.value: valor no JSON")

    active_path = active if active is not None else set()
    marker = id(value)
    if marker in active_path:
        raise ConstitutionError("candidate.change.value: ciclo JSON")
    active_path.add(marker)
    try:
        if isinstance(value, list):
            _consume_json_budget(
                budget,
                byte_count=2 + max(0, len(value) - 1),
            )
            for item in value:
                _validate_json_value(item, budget, depth + 1, active_path)
            return
        if not all(isinstance(key, str) for key in value):
            raise ConstitutionError("candidate.change.value: claves JSON no string")
        _consume_json_budget(
            budget,
            byte_count=2 + max(0, len(value) - 1),
        )
        for key, item in value.items():
            _consume_json_budget(
                budget,
                byte_count=_json_scalar_size(key) + 1,
            )
            _validate_json_value(item, budget, depth + 1, active_path)
    finally:
        active_path.remove(marker)


def _validate_change(
    change: Any,
    prefixes: tuple[str, ...],
    operations: set[str],
    budget: dict[str, int],
) -> None:
    row = _exact_keys(
        change,
        {"path", "operation", "value"},
        "candidate.change",
    )
    path = row["path"]
    operation = row["operation"]
    if not isinstance(path, str) or _PATH.fullmatch(path) is None:
        raise ConstitutionError("candidate.change.path inválido")
    if not isinstance(operation, str) or operation not in operations:
        raise ConstitutionError("candidate.change.operation inválida")
    if not any(_under_prefix(path, prefix) for prefix in prefixes):
        raise ConstitutionError(
            "candidate intenta modificar autoridad o invariantes protegidos"
        )
    _validate_json_value(row["value"], budget)


def _validate_changes(changes: Any, contract: dict[str, Any]) -> None:
    max_changes = contract["candidate_policy"]["max_changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= max_changes:
        raise ConstitutionError("candidate.changes: lista vacía o excesiva")

    prefixes = tuple(contract["candidate_policy"]["allowed_prefixes"])
    operations = set(contract["candidate_policy"]["operations"])
    budget = {"nodes": 0, "bytes": 0}
    for change in changes:
        _validate_change(change, prefixes, operations, budget)


def _validate_evidence(evidence: Any) -> None:
    if (
        not isinstance(evidence, list)
        or not 1 <= len(evidence) <= 32
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise ConstitutionError("candidate.evidence inválida")


def _validate_rollback(value: Any) -> None:
    rollback = _exact_keys(
        value,
        {"reversible", "strategy"},
        "candidate.rollback",
    )
    if rollback["reversible"] is not True:
        raise ConstitutionError("candidate.rollback debe ser reversible")
    strategy = rollback["strategy"]
    if not isinstance(strategy, str) or strategy not in {
        "revert",
        "restore_baseline",
    }:
        raise ConstitutionError("candidate.rollback.strategy inválida")


def _candidate_fingerprint(candidate_root: dict[str, Any]) -> str:
    try:
        canonical = json.dumps(
            candidate_root,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConstitutionError("candidate contiene valores no serializables") from exc
    return hashlib.sha256(canonical).hexdigest()


def validate_candidate(
    candidate: Any,
    constitution: dict[str, Any] | None = None,
) -> str:
    """Valida un candidato y devuelve su huella SHA-256 determinista."""
    contract = validate_constitution(
        constitution if constitution is not None else load_constitution()
    )
    candidate_root = _exact_keys(
        candidate,
        set(REQUIRED_CANDIDATE_FIELDS),
        "candidate",
    )
    if type(candidate_root["version"]) is not int or candidate_root["version"] != 1:
        raise ConstitutionError("candidate: versión no admitida")

    _validate_changes(candidate_root["changes"], contract)
    _validate_evidence(candidate_root["evidence"])
    _validate_rollback(candidate_root["rollback"])
    return _candidate_fingerprint(candidate_root)
