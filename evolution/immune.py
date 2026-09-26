"""Immune engine: visible incident lifecycle and immunity candidates."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from evolution.constitution import validate_candidate
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
            validated = validate_repair_plan(repair_plan)
            repair_fingerprint = validated["fingerprint"]
        elif repair_plan is not None:
            raise ImmuneError("repair_plan solo se admite en etapa repair")

        if stage == "verify":
            if type(verification_passed) is not bool:
                raise ImmuneError("verify exige resultado booleano")
            verify_value = verification_passed
        elif verification_passed is not None:
            raise ImmuneError("verification_passed solo se admite en verify")

        if stage == "immunize":
            if self.current.stage != "verify" or self.current.verification_passed is not True:
                raise ImmuneError("immunize exige verificación aprobada")
            immunity_fingerprint = _validate_immunity_candidate(immunity_candidate)
        elif immunity_candidate is not None:
            raise ImmuneError("immunity_candidate solo se admite en immunize")

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
        source = _text(raw["source"], "origin.source", 160)
        if incident_id in ids:
            raise ImmuneError("incident_id repetido")
        ids.add(incident_id)
        sources.add(source)
        origins.append({"incident_id": incident_id, "source": source})
    if len(sources) < 2:
        raise ImmuneError("fallo repetido exige fuentes distintas")
    return sorted(origins, key=lambda item: (item["source"], item["incident_id"]))


def compile_immunity_candidate(
    *,
    failure_signature: Any,
    origins: Any,
    expected_prevention: Any,
) -> dict[str, Any]:
    """Emit a Constitution-valid guardrail candidate from repeated failures."""
    signature = _canonical(failure_signature, "failure_signature")
    validated_origins = _validate_origins(origins)
    prevention = _text(expected_prevention, "expected_prevention", 500)
    sources = sorted({item["source"] for item in validated_origins})
    immunity_id = f"immunity_{hashlib.sha256(signature.encode()).hexdigest()[:16]}"
    value = {
        "version": IMMUNE_VERSION,
        "immunity_id": immunity_id,
        "failure_signature": signature,
        "status": "candidate",
        "occurrences": len(validated_origins),
        "origins": validated_origins,
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
        "origins": validated_origins,
        "expected_prevention": prevention,
    }


def _validate_immunity_candidate(value: Any) -> str:
    if not isinstance(value, dict):
        raise ImmuneError("immunity_candidate inválido")
    required = {
        "version",
        "immunity_id",
        "candidate",
        "candidate_fingerprint",
        "origins",
        "expected_prevention",
    }
    if set(value) != required:
        raise ImmuneError("immunity_candidate incompleto")
    fingerprint = validate_candidate(value["candidate"])
    if fingerprint != value["candidate_fingerprint"]:
        raise ImmuneError("immunity candidate fingerprint no coincide")
    return fingerprint
