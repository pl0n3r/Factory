"""Constitución ejecutable de Factory Living Software.

La autoridad estable y los invariantes protegidos nunca son superficie de
mutación autónoma. Los candidatos solo pueden modificar namespaces evolutivos
declarados y deben aportar evidencia y rollback.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ConstitutionError(ValueError):
    """Contrato constitucional inválido o candidato no autorizado."""


CONSTITUTION_VERSION = 1
CONSTITUTION_PATH = Path(__file__).with_name("constitution.json")

EXPECTED_AUTHORITY_SOURCES = (
    "PLAN-AGENTES.md",
    "AGENTES.md",
    "decisiones.yml",
    "docs/puertas-humanas.md",
)
EXPECTED_HUMAN_GATES = (
    "product_direction",
    "brand",
    "money",
    "legal",
    "real_customer_data",
    "factory_release",
    "factory_maintenance",
    "go_live",
)
PROTECTED_INVARIANTS = (
    "security",
    "privacy",
    "traceability",
    "reversibility",
    "authority",
)
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
        {"sources", "autonomous_mutation", "human_gate_categories"},
        "stable_authority",
    )
    _unique_strings(
        authority["sources"],
        EXPECTED_AUTHORITY_SOURCES,
        "stable_authority.sources",
    )
    _unique_strings(
        authority["human_gate_categories"],
        EXPECTED_HUMAN_GATES,
        "stable_authority.human_gate_categories",
    )
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
            or not rule["source"]
        ):
            raise ConstitutionError(
                f"protected_invariants.{invariant}: regla no protegida"
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
        or not 1 <= policy["max_changes"] <= 128
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


def validate_candidate(
    candidate: Any,
    constitution: dict[str, Any] | None = None,
) -> str:
    """Valida un candidato y devuelve su huella SHA-256 determinista."""
    contract = validate_constitution(constitution or load_constitution())
    required = set(REQUIRED_CANDIDATE_FIELDS)
    candidate_root = _exact_keys(candidate, required, "candidate")

    if type(candidate_root["version"]) is not int or candidate_root["version"] != 1:
        raise ConstitutionError("candidate: versión no admitida")

    changes = candidate_root["changes"]
    max_changes = contract["candidate_policy"]["max_changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= max_changes:
        raise ConstitutionError("candidate.changes: lista vacía o excesiva")

    prefixes = tuple(contract["candidate_policy"]["allowed_prefixes"])
    operations = set(contract["candidate_policy"]["operations"])
    for change in changes:
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

    evidence = candidate_root["evidence"]
    if (
        not isinstance(evidence, list)
        or not 1 <= len(evidence) <= 32
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise ConstitutionError("candidate.evidence inválida")

    rollback = _exact_keys(
        candidate_root["rollback"],
        {"reversible", "strategy"},
        "candidate.rollback",
    )
    if rollback["reversible"] is not True:
        raise ConstitutionError("candidate.rollback debe ser reversible")
    if rollback["strategy"] not in {"revert", "restore_baseline"}:
        raise ConstitutionError("candidate.rollback.strategy inválida")

    try:
        canonical = json.dumps(
            candidate_root,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConstitutionError("candidate contiene valores no serializables") from exc
    return hashlib.sha256(canonical).hexdigest()
