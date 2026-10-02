#!/usr/bin/env python3
"""Clasificador fail-closed de startup_failure post-release en consumidores."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
import sys
from typing import Any, Mapping


CANONICAL_CONSUMERS = frozenset(
    {
        "pl0n3r/Condor",
        "pl0n3r/ControlBot",
        "pl0n3r/FactoryRunner",
        "pl0n3r/GrindFlow",
        "pl0n3r/brvtal",
        "pl0n3r/AutoFactory",
    }
)
WATCHED_REUSABLES = {
    "pl0n3r/factory/.github/workflows/etiquetas.yml@v1": "labels",
    "pl0n3r/factory/.github/workflows/coordinacion.yml@v1": "coordination",
}
WATCHED_WORKFLOW_NAMES = {
    "labels": frozenset(
        {
            "Etiquetas",
            "Etiquetas Factory v1",
            "Factory Labels",
        }
    ),
    "coordination": frozenset(
        {
            "Coordinación",
            "Coordinación multiagente (V 0.1.0)",
        }
    ),
}
CHANNEL = "v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CALLER_PATH_RE = re.compile(r"^\.github/workflows/[A-Za-z0-9._/-]+\.ya?ml$")
MAX_INPUT = 1_000_000
MAX_OBSERVATIONS = 200
ROOT_FIELDS = frozenset(
    {"factory_sha", "factory_channel", "release_started_at", "observations"}
)
OBSERVATION_FIELDS = frozenset(
    {
        "repository_ref",
        "workflow",
        "run_id",
        "observed_at",
        "factory_sha",
        "factory_channel",
        "conclusion",
        "caller_sha",
        "caller_path",
        "reusable_ref",
    }
)


class ReusableReleaseWatchdogError(ValueError):
    """La evidencia no permite una clasificación segura."""


def _closed(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ReusableReleaseWatchdogError(f"{label} fuera del contrato.")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ReusableReleaseWatchdogError(f"{label} inválido.")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReusableReleaseWatchdogError(f"{label} debe ser UTC con sufijo Z.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReusableReleaseWatchdogError(f"{label} inválido.") from exc
    if parsed.utcoffset() is None:
        raise ReusableReleaseWatchdogError(f"{label} sin zona horaria.")
    return parsed


def _normalize_observation(
    value: Any,
    *,
    factory_sha: str,
    release_started_at: datetime,
) -> dict[str, Any]:
    row = _closed(value, OBSERVATION_FIELDS, "observación")

    repository = row["repository_ref"]
    if repository not in CANONICAL_CONSUMERS:
        raise ReusableReleaseWatchdogError("consumer repository desconocido.")

    reusable_ref = row["reusable_ref"]
    if reusable_ref not in WATCHED_REUSABLES:
        raise ReusableReleaseWatchdogError("reusable ref fuera del allowlist.")

    workflow = row["workflow"]
    kind = WATCHED_REUSABLES[reusable_ref]
    if (
        not isinstance(workflow, str)
        or workflow not in WATCHED_WORKFLOW_NAMES[kind]
    ):
        raise ReusableReleaseWatchdogError("workflow fuera del allowlist.")

    run_id = row["run_id"]
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise ReusableReleaseWatchdogError("run_id inválido.")

    observed_text = row["observed_at"]
    observed_at = _timestamp(observed_text, "observed_at")
    if observed_at < release_started_at:
        raise ReusableReleaseWatchdogError(
            "observación anterior al release monitoreado."
        )

    if row["factory_sha"] != factory_sha:
        raise ReusableReleaseWatchdogError("factory_sha no coincide.")
    if row["factory_channel"] != CHANNEL:
        raise ReusableReleaseWatchdogError("factory_channel no coincide.")
    if row["conclusion"] != "startup_failure":
        raise ReusableReleaseWatchdogError(
            "solo startup_failure pertenece a este clasificador."
        )

    caller_sha = _sha(row["caller_sha"], "caller_sha")
    caller_path = row["caller_path"]
    if (
        not isinstance(caller_path, str)
        or CALLER_PATH_RE.fullmatch(caller_path) is None
    ):
        raise ReusableReleaseWatchdogError("caller_path inválido.")

    return {
        "repository_ref": repository,
        "workflow": workflow,
        "run_id": run_id,
        "observed_at": observed_text,
        "factory_sha": factory_sha,
        "factory_channel": CHANNEL,
        "conclusion": "startup_failure",
        "caller_sha": caller_sha,
        "caller_path": caller_path,
        "reusable_ref": reusable_ref,
    }


def evaluate_release_watchdog(payload: Any) -> dict[str, Any]:
    """Clasifica evidencia ya recolectada; no hace red ni ejecuta rollback."""
    root = _closed(payload, ROOT_FIELDS, "payload")
    factory_sha = _sha(root["factory_sha"], "factory_sha")
    if root["factory_channel"] != CHANNEL:
        raise ReusableReleaseWatchdogError("factory_channel debe ser v1.")
    release_started_text = root["release_started_at"]
    release_started_at = _timestamp(
        release_started_text,
        "release_started_at",
    )

    observations = root["observations"]
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise ReusableReleaseWatchdogError("observations inválidas.")

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for raw in observations:
        normalized = _normalize_observation(
            raw,
            factory_sha=factory_sha,
            release_started_at=release_started_at,
        )
        key = (
            normalized["repository_ref"],
            normalized["workflow"],
            normalized["run_id"],
        )
        previous = unique.get(key)
        if previous is not None and previous != normalized:
            raise ReusableReleaseWatchdogError(
                "evidencia ambigua para el mismo workflow run."
            )
        unique[key] = normalized

    normalized_observations = sorted(
        unique.values(),
        key=lambda item: (
            item["repository_ref"],
            item["workflow"],
            item["run_id"],
        ),
    )
    affected_repositories = sorted(
        {item["repository_ref"] for item in normalized_observations}
    )
    fingerprint_payload = {
        "version": 1,
        "factory_sha": factory_sha,
        "factory_channel": CHANNEL,
        "observations": normalized_observations,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    rollback_recommended = len(affected_repositories) >= 2
    return {
        "version": 1,
        "status": "ALERT" if normalized_observations else "CLEAR",
        "factory_sha": factory_sha,
        "factory_channel": CHANNEL,
        "release_started_at": release_started_text,
        "fingerprint": fingerprint,
        "affected_repositories": affected_repositories,
        "affected_repository_count": len(affected_repositories),
        "observations": normalized_observations,
        "rollback_recommended": rollback_recommended,
        "recommendation": (
            "rollback_v1_recommended"
            if rollback_recommended
            else "observe_without_rollback_recommendation"
        ),
        "authority": "unchanged",
        "execute_rollback": False,
    }


def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        print("ERROR: payload demasiado grande.", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
        result = evaluate_release_watchdog(payload)
    except (json.JSONDecodeError, ReusableReleaseWatchdogError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
