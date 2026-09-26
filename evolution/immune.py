"""Immune engine: visible incident lifecycle and immunity candidates."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from evolution.constitution import validate_candidate
from evolution.provenance import TrustedDecisionSource, TrustedIncidentRegistry
from evolution.repair import validate_repair_plan


IMMUNE_VERSION = 1
RECOVERY_LIFECYCLE = (
    "detect",
    "contain",
    "diagnose",
    "repair",
    "verify",
    "immunize",
)
MAX_EVIDENCE = 32
_TOKEN = re.compile(r"[a-z0-9]+")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ImmuneError(ValueError):
    """Invalid incident transition or immunity evidence."""


@dataclass(frozen=True)
class IncidentRecord:
    sequence: int
    stage: str
    reason: str
    evidence: tuple[str, ...]
    repair_fingerprint: str | None = None
    verification_passed: bool | None = None
    immunity_fingerprint: str | None = None


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, field: str, max_len: int = 500) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise ImmuneError(f"{field} debe ser texto de una línea")
    return value.strip()


def _evidence(value: Any) -> tuple[str, ...]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_EVIDENCE
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ImmuneError("evidence debe contener 1..32 referencias")
    return tuple(item.strip() for item in value)


def _canonical(value: Any, field: str) -> str:
    text = _text(value, field, 300)
    folded = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    tokens = _TOKEN.findall(ascii_text)
    if not tokens:
        raise ImmuneError(f"{field} no contiene patrón útil")
    return "-".join(tokens)


def _sha256_or_none(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ImmuneError(f"{field} inválido")
    return value


class ImmuneIncident:
    """Append-only incident history that cannot skip recovery stages."""

    def __init__(
        self,
        incident_id: str,
        *,
        signature: str,
        reason: str,
        evidence: list[str] | tuple[str, ...],
    ) -> None:
        self._incident_id = _text(incident_id, "incident_id", 120)
        self._signature = _canonical(signature, "signature")
        self._history: list[IncidentRecord] = [
            IncidentRecord(
                sequence=0,
                stage="detect",
                reason=_text(reason, "reason"),
                evidence=_evidence(evidence),
            )
        ]

    @property
    def current(self) -> IncidentRecord:
        return self._history[-1]

    @property
    def history(self) -> tuple[IncidentRecord, ...]:
        return tuple(self._history)

    def advance(
        self,
        stage: str,
        *,
        reason: str,
        evidence: list[str] | tuple[str, ...],
        repair_plan: Any = None,
        verification_passed: Any = None,
        immunity_candidate: Any = None,
        decision_source: TrustedDecisionSource | None = None,
        incident_registry: TrustedIncidentRegistry | None = None,
    ) -> IncidentRecord:
        """Advance exactly one recovery stage and preserve all prior evidence."""
        current_index = RECOVERY_LIFECYCLE.index(self.current.stage)
        if current_index >= len(RECOVERY_LIFECYCLE) - 1:
            raise ImmuneError("incidente ya está inmunizado")
        expected = RECOVERY_LIFECYCLE[current_index + 1]
        if stage != expected:
            raise ImmuneError(f"transición inválida: se esperaba {expected}")

        repair_fingerprint = None
        verify_value = None
        immunity_fingerprint = None

        if stage == "repair":
            if repair_plan is None:
                raise ImmuneError("repair exige plan verificable y reversible")
            validated = validate_repair_plan(
                repair_plan,
                decision_source=decision_source,
            )
            repair_fingerprint = validated["fingerprint"]
        elif repair_plan is not None or decision_source is not None:
            raise ImmuneError("repair_plan/decision_source solo se admiten en etapa repair")

        if stage == "verify":
            if type(verification_passed) is not bool:
                raise ImmuneError("verify exige resultado booleano")
            verify_value = verification_passed
        elif verification_passed is not None:
            raise ImmuneError("verification_passed solo se admite en verify")

        if stage == "immunize":
            if self.current.stage != "verify" or self.current.verification_passed is not True:
                raise ImmuneError("immunize exige verificación aprobada")
            immunity_fingerprint = _validate_immunity_candidate(
                immunity_candidate,
                incident_registry=incident_registry,
            )
        elif immunity_candidate is not None or incident_registry is not None:
            raise ImmuneError(
                "immunity_candidate/incident_registry solo se admiten en immunize"
            )

        record = IncidentRecord(
            sequence=len(self._history),
            stage=stage,
            reason=_text(reason, "reason"),
            evidence=_evidence(evidence),
            repair_fingerprint=repair_fingerprint,
            verification_passed=verify_value,
            immunity_fingerprint=immunity_fingerprint,
        )
        self._history.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        payload = {
            "version": IMMUNE_VERSION,
            "incident_id": self._incident_id,
            "signature": self._signature,
            "stage": self.current.stage,
            "visible": True,
            "history_preserved": True,
            "history": [asdict(item) for item in self._history],
        }
        payload["fingerprint"] = _stable_hash(payload)
        return payload


def _validate_origins(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= MAX_EVIDENCE:
        raise ImmuneError("fallo repetido exige al menos dos incidentes")
    origins: list[dict[str, str]] = []
    ids: set[str] = set()
    sources: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"incident_id", "source"}:
            raise ImmuneError("origin inválido")
        incident_id = _text(raw["incident_id"], "origin.incident_id", 120)
        source = _text(raw["source"], "origin.source", 220)
        if incident_id in ids:
            raise ImmuneError("incident_id repetido")
        ids.add(incident_id)
        sources.add(source)
        origins.append({"incident_id": incident_id, "source": source})
    if len(sources) < 2:
        raise ImmuneError("fallo repetido exige fuentes distintas")
    return sorted(origins, key=lambda item: (item["source"], item["incident_id"]))


def _validate_history_record(raw: Any, index: int) -> dict[str, Any]:
    required = {
        "sequence",
        "stage",
        "reason",
        "evidence",
        "repair_fingerprint",
        "verification_passed",
        "immunity_fingerprint",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ImmuneError("incident history inválido")
    if raw["sequence"] != index:
        raise ImmuneError("incident history sequence inválida")
    if index >= len(RECOVERY_LIFECYCLE) or raw["stage"] != RECOVERY_LIFECYCLE[index]:
        raise ImmuneError("incident history lifecycle inválido")
    record = {
        "sequence": index,
        "stage": raw["stage"],
        "reason": _text(raw["reason"], "incident.reason"),
        "evidence": _evidence(raw["evidence"]),
        "repair_fingerprint": None,
        "verification_passed": None,
        "immunity_fingerprint": None,
    }
    if raw["stage"] == "repair":
        record["repair_fingerprint"] = _sha256_or_none(
            raw["repair_fingerprint"],
            "incident.repair_fingerprint",
            required=True,
        )
    elif raw["repair_fingerprint"] is not None:
        raise ImmuneError("repair_fingerprint fuera de etapa repair")
    if raw["stage"] == "verify":
        if type(raw["verification_passed"]) is not bool:
            raise ImmuneError("verify history exige booleano")
        record["verification_passed"] = raw["verification_passed"]
    elif raw["verification_passed"] is not None:
        raise ImmuneError("verification_passed fuera de etapa verify")
    if raw["stage"] == "immunize":
        record["immunity_fingerprint"] = _sha256_or_none(
            raw["immunity_fingerprint"],
            "incident.immunity_fingerprint",
            required=True,
        )
    elif raw["immunity_fingerprint"] is not None:
        raise ImmuneError("immunity_fingerprint fuera de etapa immunize")
    return record


def _validate_incident_snapshot(
    value: Any,
    *,
    expected_signature: str,
) -> dict[str, Any]:
    required = {
        "version",
        "incident_id",
        "signature",
        "stage",
        "visible",
        "history_preserved",
        "history",
        "fingerprint",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ImmuneError("incident snapshot inválido")
    if type(value["version"]) is not int or value["version"] != IMMUNE_VERSION:
        raise ImmuneError("incident snapshot version inválida")
    incident_id = _text(value["incident_id"], "incident_id", 120)
    signature = _canonical(value["signature"], "signature")
    if signature != expected_signature:
        raise ImmuneError("incidentes no comparten failure_signature")
    if value["visible"] is not True or value["history_preserved"] is not True:
        raise ImmuneError("incident snapshot debe preservar historia visible")
    history = value["history"]
    if (
        not isinstance(history, list)
        or len(history) < RECOVERY_LIFECYCLE.index("verify") + 1
        or len(history) > len(RECOVERY_LIFECYCLE)
    ):
        raise ImmuneError("incident snapshot no alcanzó verify")
    normalized_history = [
        _validate_history_record(record, index)
        for index, record in enumerate(history)
    ]
    if value["stage"] != normalized_history[-1]["stage"]:
        raise ImmuneError("incident snapshot stage no coincide con history")
    verify = normalized_history[RECOVERY_LIFECYCLE.index("verify")]
    if verify["verification_passed"] is not True:
        raise ImmuneError("incident snapshot no tiene verificación durable aprobada")

    normalized = {
        "version": IMMUNE_VERSION,
        "incident_id": incident_id,
        "signature": signature,
        "stage": value["stage"],
        "visible": True,
        "history_preserved": True,
        "history": normalized_history,
    }
    fingerprint = value["fingerprint"]
    if (
        not isinstance(fingerprint, str)
        or _SHA256.fullmatch(fingerprint) is None
        or fingerprint != _stable_hash(normalized)
    ):
        raise ImmuneError("incident snapshot fingerprint no coincide")
    normalized["fingerprint"] = fingerprint
    return normalized


def _trusted_incident_evidence(
    incident_ids: Any,
    *,
    incident_registry: TrustedIncidentRegistry | None,
    failure_signature: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    if not isinstance(incident_registry, TrustedIncidentRegistry):
        raise ImmuneError("inmunidad exige registro confiable de incidentes")
    if (
        not isinstance(incident_ids, (list, tuple))
        or not 2 <= len(incident_ids) <= MAX_EVIDENCE
    ):
        raise ImmuneError("fallo repetido exige al menos dos incident IDs")

    signature = _canonical(failure_signature, "failure_signature")
    ids = [_text(item, "incident_id", 120) for item in incident_ids]
    if len(set(ids)) != len(ids):
        raise ImmuneError("incident IDs deben ser distintos")
    ids = sorted(ids)

    snapshots: list[dict[str, Any]] = []
    for incident_id in ids:
        raw = incident_registry.resolve_incident(incident_id)
        if raw is None:
            raise ImmuneError("incident ID no existe en registro confiable")
        snapshot = _validate_incident_snapshot(
            raw,
            expected_signature=signature,
        )
        if snapshot["incident_id"] != incident_id:
            raise ImmuneError("incident handle no coincide con snapshot registrado")
        snapshots.append(snapshot)

    origins = sorted(
        [
            {
                "incident_id": item["incident_id"],
                "source": (
                    f"{incident_registry.source_id}:"
                    f"{item['incident_id']}:{item['fingerprint']}"
                ),
            }
            for item in snapshots
        ],
        key=lambda item: (item["source"], item["incident_id"]),
    )
    provenance = {
        "source_id": incident_registry.source_id,
        "incident_ids": ids,
    }
    return snapshots, origins, provenance


def compile_immunity_candidate(
    *,
    failure_signature: Any,
    expected_prevention: Any,
    incident_ids: Any = None,
    incident_registry: TrustedIncidentRegistry | None = None,
    origins: Any = None,
    incident_snapshots: Any = None,
) -> dict[str, Any]:
    """Emit guardrail only from incidents resolved through trusted provenance."""
    if incident_snapshots is not None:
        raise ImmuneError(
            "incident_snapshots autocertificados no constituyen provenance"
        )
    signature = _canonical(failure_signature, "failure_signature")
    snapshots, canonical_origins, provenance = _trusted_incident_evidence(
        incident_ids,
        incident_registry=incident_registry,
        failure_signature=signature,
    )
    if origins is not None and _validate_origins(origins) != canonical_origins:
        raise ImmuneError("origins no coinciden con registro confiable")
    prevention = _text(expected_prevention, "expected_prevention", 500)
    sources = sorted({item["source"] for item in canonical_origins})
    immunity_id = f"immunity_{hashlib.sha256(signature.encode()).hexdigest()[:16]}"
    value = {
        "version": IMMUNE_VERSION,
        "immunity_id": immunity_id,
        "failure_signature": signature,
        "status": "candidate",
        "occurrences": len(canonical_origins),
        "origins": canonical_origins,
        "provenance": provenance,
        "expected_prevention": prevention,
    }
    candidate = {
        "version": 1,
        "changes": [
            {
                "path": f"evolution_state.heuristics.{immunity_id}",
                "operation": "add",
                "value": value,
            }
        ],
        "evidence": sources,
        "rollback": {"reversible": True, "strategy": "revert"},
    }
    candidate_fingerprint = validate_candidate(candidate)
    return {
        "version": IMMUNE_VERSION,
        "immunity_id": immunity_id,
        "candidate": candidate,
        "candidate_fingerprint": candidate_fingerprint,
        "origins": canonical_origins,
        "incidents": snapshots,
        "provenance": provenance,
        "expected_prevention": prevention,
    }


def _validate_immunity_candidate(
    value: Any,
    *,
    incident_registry: TrustedIncidentRegistry | None,
) -> str:
    if not isinstance(value, dict):
        raise ImmuneError("immunity_candidate inválido")
    required = {
        "version",
        "immunity_id",
        "candidate",
        "candidate_fingerprint",
        "origins",
        "incidents",
        "provenance",
        "expected_prevention",
    }
    if set(value) != required:
        raise ImmuneError("immunity_candidate incompleto")
    if type(value["version"]) is not int or value["version"] != IMMUNE_VERSION:
        raise ImmuneError("immunity_candidate version inválida")
    if not isinstance(incident_registry, TrustedIncidentRegistry):
        raise ImmuneError("immunity candidate exige registro confiable")

    provenance = value["provenance"]
    if (
        not isinstance(provenance, dict)
        or set(provenance) != {"source_id", "incident_ids"}
        or provenance.get("source_id") != incident_registry.source_id
    ):
        raise ImmuneError("immunity provenance no coincide con registro confiable")

    candidate = value["candidate"]
    fingerprint = validate_candidate(candidate)
    if fingerprint != value["candidate_fingerprint"]:
        raise ImmuneError("immunity candidate fingerprint no coincide")
    if (
        not isinstance(candidate, dict)
        or not isinstance(candidate.get("changes"), list)
        or len(candidate["changes"]) != 1
        or not isinstance(candidate["changes"][0], dict)
        or not isinstance(candidate["changes"][0].get("value"), dict)
    ):
        raise ImmuneError("immunity candidate shape inválida")
    payload = candidate["changes"][0]["value"]
    signature = _canonical(payload.get("failure_signature"), "failure_signature")
    snapshots, origins, canonical_provenance = _trusted_incident_evidence(
        provenance.get("incident_ids"),
        incident_registry=incident_registry,
        failure_signature=signature,
    )
    if provenance != canonical_provenance:
        raise ImmuneError("immunity provenance no está canonizada")
    if value["incidents"] != snapshots:
        raise ImmuneError("incidents no coinciden con registro confiable")
    if _validate_origins(value["origins"]) != origins:
        raise ImmuneError("origins no coinciden con registro confiable")
    if payload.get("origins") != origins or payload.get("occurrences") != len(origins):
        raise ImmuneError("candidate no refleja evidencia de incidentes")
    if payload.get("provenance") != canonical_provenance:
        raise ImmuneError("candidate no refleja provenance confiable")
    if payload.get("immunity_id") != value["immunity_id"]:
        raise ImmuneError("immunity_id inconsistente")
    if payload.get("expected_prevention") != value["expected_prevention"]:
        raise ImmuneError("expected_prevention inconsistente")
    return fingerprint
