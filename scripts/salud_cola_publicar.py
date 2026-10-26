#!/usr/bin/env python3
"""Simulador de aviso de cola: jamás publica ni modifica GitHub.

La procedencia es una atestación inyectada: NO autentica datos por sí sola.
Sin evidencia completa y verificada el resultado falla cerrado.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

from scripts.salud_cola import QueueHealthError, REPOSITORIES, diagnose_queue

MAX_OBSERVATION_BYTES = 131072
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}\Z")


def _skip(reason: str) -> dict:
    return {"version": 1, "status": "SKIPPED", "reason": reason,
            "action": "none", "publish_allowed": False, "writes": 0}


def _verified_provenance(provenance: object) -> bool:
    return (
        type(provenance) is dict
        and set(provenance) == {
            "authenticated", "repository_scope", "identities_verified",
            "pagination_complete", "checks_complete",
        }
        and provenance["authenticated"] is True
        and provenance["identities_verified"] is True
        and provenance["pagination_complete"] is True
        and provenance["checks_complete"] is True
        and type(provenance["repository_scope"]) is list
        and provenance["repository_scope"] == list(REPOSITORIES)
    )


def preparar_publicacion(snapshot: object, provenance: object,
                         previous_fingerprint: object = None) -> dict:
    """Propuesta agregada determinista; ninguna salida concede autorización."""
    if not _verified_provenance(provenance):
        return _skip("unverified_provenance")
    if previous_fingerprint is not None and (
        type(previous_fingerprint) is not str
        or FINGERPRINT_RE.fullmatch(previous_fingerprint) is None
    ):
        return _skip("invalid_previous_fingerprint")
    try:
        diagnostic = diagnose_queue(snapshot)
    except (QueueHealthError, ValueError, TypeError, KeyError):
        return _skip("invalid_or_incomplete_inventory")
    if diagnostic["state"] == "budget_deferred":
        return _skip("low_quota")
    if diagnostic["state"] != "queue_empty":
        return _skip("no_queue_empty_trigger")
    if diagnostic["publication_allowed"] is not False:
        return _skip("unexpected_publish_authority")

    # Solo metadatos enumerados, sin cuerpos de Issues, usuarios ni secretos.
    proposal = {
        "state": diagnostic["state"],
        "reason": diagnostic["reason"],
        "available_total": diagnostic["available_total"],
        "open_total": diagnostic["open_total"],
        "blocked_cause_totals": diagnostic["blocked_cause_totals"],
        "candidate_count": len(diagnostic["roadmap_candidates"]),
    }
    encoded = json.dumps(proposal, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    action = "noop" if previous_fingerprint == fingerprint else "create_candidate"
    return {"version": 1, "status": "DRY_RUN", "action": action,
            "fingerprint": fingerprint, "proposal": proposal,
            "publish_allowed": False, "writes": 0}


def _read_local_observation(path: str) -> dict:
    """La observación local Factory NO acredita siete repositorios."""
    try:
        target = Path(path)
        if target.is_symlink() or not target.is_file():
            return _skip("observation_unreadable")
        with target.open("rb") as stream:
            raw = stream.read(MAX_OBSERVATION_BYTES + 1)
        if len(raw) > MAX_OBSERVATION_BYTES:
            return _skip("observation_oversized")
        observation = json.loads(raw)
    except (OSError, ValueError, UnicodeError, TypeError):
        return _skip("observation_unreadable")
    if type(observation) is not dict:
        return _skip("observation_invalid")
    if observation.get("status") == "DEFERRED_LOW_QUOTA":
        return _skip("low_quota")
    if (observation.get("scope") != "pl0n3r/Factory"
            or observation.get("writes") != 0
            or observation.get("status") not in ("OBSERVED_LOCAL_ONLY", "UNKNOWN")):
        return _skip("observation_invalid")
    return _skip("local_observation_not_global_proof")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--observacion":
        print("Uso: salud_cola_publicar.py --observacion ARCHIVO", file=sys.stderr)
        return 2
    report = _read_local_observation(sys.argv[2])
    print(json.dumps(report, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("### Salud de cola: simulación únicamente\n"
                             "Sin publicaciones ni mutaciones de Issues.\n")
        except OSError:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
