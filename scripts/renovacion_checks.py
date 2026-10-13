"""Evaluación PURA y fail-closed de recuperación tras renovar aceptación.

Nunca publica checks ni modifica reservas. El adaptador operativo debe cargar
los datos exclusivamente de APIs autenticadas, revalidar después de decidir y
aplicar las puertas de protección reales antes de cualquier mutación.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_PIN = re.compile(r"[0-9a-f]{64}\Z")
# Perfiles estrictos observados en GitHub; un alias distinto NO hereda autoridad.
# Runner expone nombres prefijados por reusable workflow, Factory usa jobs locales.
# Nunca aceptar estas listas desde el cuerpo de un Issue ni del PR.
_PROFILES = {
    "pl0n3r/factory": {
        "Tests de scripts": "github-actions",
        "Validar claims V3 del PR": "github-actions",
        "Presupuesto del PR": "github-actions",
        "Validar": "github-actions",
        "Criterios de aceptación": "github-actions",
        "Validar coordinación": "github-actions",
        "Ventana de release Factory": "github-actions",
        "CodeQL": "github-advanced-security",
        "SonarCloud Code Analysis": "sonarqubecloud",
    },
    "pl0n3r/factoryrunner": {
        "ci / Validar": "github-actions",
        "validar-pr / Validar coordinación": "github-actions",
        "acceptance / Criterios de aceptación": "github-actions",
        "privacidad / Privacidad como código": "github-actions",
        "politica / Validar decisiones y límite de revisión": "github-actions",
        "SonarCloud Code Analysis": "sonarqubecloud",
    },
}
# El nombre del job NO acredita su workflow. Solo estas rutas exactas
# están autorizadas para cada gate nativo de Factory (API Actions run.path).
_FACTORY_WORKFLOW_PATHS = {
    "Tests de scripts": ".github/workflows/factory-ci.yml",
    "Validar": ".github/workflows/factory-ci.yml",
    "Criterios de aceptación": ".github/workflows/factory-ci.yml",
    "Validar coordinación": ".github/workflows/factory-ci.yml",
    "Ventana de release Factory": ".github/workflows/factory-ci.yml",
    "Validar claims V3 del PR": ".github/workflows/coordinacion-trabajo.yml",
    "Presupuesto del PR": ".github/workflows/costos.yml",
}

_MAX_CHECKS = 500


@dataclass(frozen=True)
class Decision:
    ready: bool
    reason: str
    fingerprint: str = ""


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def evaluate(evidence: object) -> Decision:
    """Devuelve CANDIDATE solamente con pruebas frescas, completas y correlacionadas.

    CANDIDATE no autoriza la publicación: un writer tendrá que leer el estado
    de nuevo bajo autoridad canónica, validar reglasets y verificar #767.
    """
    denied = Decision(False, "evidence_incomplete_or_untrusted")
    now = datetime.now(timezone.utc)
    if not isinstance(evidence, dict):
        return denied
    try:
        statuses = evidence["statuses"]
        repo = evidence["repo"]
        issue = evidence["issue"]
        pr = evidence["pr"]
        before = evidence["before"]
        after = evidence["after"]
        renewal = evidence["renewal"]
        runs = evidence["checks"]
        reviews = evidence["reviews"]
        reviewer_required = evidence["reviewer_required"]
        threads = evidence["review_threads"]
    except KeyError:
        return denied

    if not isinstance(repo, str) or not re.fullmatch(r"pl0n3r/[A-Za-z][A-Za-z0-9_-]*", repo):
        return denied
    required = _PROFILES.get(repo.lower())
    if required is None:
        return Decision(False, "unsupported_repository_profile")
    if not isinstance(issue, dict) or not isinstance(pr, dict):
        return denied
    if not isinstance(before, dict) or not isinstance(after, dict):
        return denied
    if (not isinstance(threads, list) or len(threads) >= 100
        or any(not isinstance(row, dict) or row.get("isResolved") is not True
               for row in threads)):
        return Decision(False, "unresolved_or_untrusted_review_thread")
    if issue.get("owner") != "pl0n3r":
        return Decision(False, "reservation_owner_untrusted")
    if type(reviewer_required) is not bool or not reviewer_required:
        # Sin evidencia autenticada de la exención D-069, exigir revisión real.
        return Decision(False, "review_authority_missing")
    reviewer_permissions = evidence.get("reviewer_permissions")
    if (not isinstance(reviewer_permissions, dict)
        or any(not isinstance(actor, str) or actor != actor.lower()
               or permission not in ("none", "read", "triage", "write",
                                     "maintain", "admin")
               for actor, permission in reviewer_permissions.items())):
        return Decision(False, "review_authority_unverified")
    sha = pr.get("head_sha")
    base_sha = pr.get("base_sha")
    pin = issue.get("acceptance_sha256")
    uuid = issue.get("reservation_id")
    num = issue.get("number")
    if (not isinstance(base_sha, str) or _SHA.fullmatch(base_sha) is None
        or not isinstance(sha, str) or _SHA.fullmatch(sha) is None
        or not isinstance(pin, str) or _PIN.fullmatch(pin) is None
        or not isinstance(uuid, str) or _UUID.fullmatch(uuid) is None
        or type(num) is not int or num < 1):
        return denied
    branch = f"trabajo/issue-{num}"
    if (pr.get("branch") != branch or pr.get("repo") != repo
        or pr.get("state") != "open" or pr.get("draft") is not False
        or issue.get("state") != "open"
        or issue.get("status") not in ("estado: reservado", "estado: en revisión")
        or issue.get("active") is not True
        or issue.get("version") != 3
        or issue.get("branch") != branch):
        return denied
    stamp = _time(renewal.get("created_at")) if isinstance(renewal, dict) else None
    if (stamp is None or stamp > now or renewal.get("user") != "github-actions[bot]"
        or renewal.get("reason") != "renovar-contrato"
        or renewal.get("uuid") != uuid or renewal.get("pin") != pin):
        return denied
    required_fields = ("repo", "issue", "uuid", "pin", "head_sha", "base_sha", "branch")
    if any(before.get(k) != after.get(k) for k in required_fields):
        return Decision(False, "identity_changed_during_revalidation")
    expected = {"repo": repo, "issue": num, "uuid": uuid,
                "pin": pin, "head_sha": sha, "base_sha": base_sha, "branch": branch}
    if any(after.get(k) != v for k, v in expected.items()):
        return denied

    if not isinstance(runs, list) or len(runs) < len(required) or len(runs) > _MAX_CHECKS:
        return denied
    if not isinstance(reviews, list) or len(reviews) > 100:
        return denied
    if not isinstance(statuses, list) or not 1 <= len(statuses) < 100:
        return Decision(False, "external_statuses_unavailable")
    seen_contexts: set[str] = set()
    coderabbit = False
    for item in statuses:
        if not isinstance(item, dict) or not isinstance(item.get("context"), str):
            return Decision(False, "external_status_unreadable")
        context = item["context"]
        # El lector debe entregar un solo estado (el más reciente) por contexto.
        if context in seen_contexts:
            return Decision(False, "ambiguous_external_status")
        seen_contexts.add(context)
        state = item.get("state")
        if state != "success":
            return Decision(False, "external_status_not_green")
        if context == "CodeRabbit":
            coderabbit = True
            if item.get("creator") != "coderabbitai[bot]":
                return Decision(False, "coderabbit_creator_not_authenticated")
            created = _time(item.get("created_at"))
            description = str(item.get("description") or "").lower()
            if (created is None or not stamp < created <= now
                or "skipped" in description or "manual review required" in description
                or not description.strip()):
                return Decision(False, "coderabbit_review_not_verified")
    if not coderabbit:
        return Decision(False, "missing_coderabbit")
    by_name: dict[str, dict] = {}
    seen_ids: set[int] = set()
    for row in runs:
        if not isinstance(row, dict):
            return denied
        ident, name, app = row.get("id"), row.get("name"), row.get("app")
        if type(ident) is not int or ident <= 0 or ident in seen_ids:
            return denied
        seen_ids.add(ident)
        if not isinstance(name, str) or not isinstance(app, str):
            return denied
        if row.get("head_sha") != sha:
            return Decision(False, "stale_or_wrong_head_check")
        # Una invalidación previa nunca reemplaza el job CI del mismo nombre;
        # ni autoriza limpiar el veto sin una publicación posterior autorizada.
        invalidation = (name == "Validar"
                        and row.get("title") == "Renovación explícita del contrato")
        if invalidation:
            if (app != "github-actions" or row.get("status") != "completed"
                or row.get("conclusion") != "failure"):
                return Decision(False, "invalid_renewal_invalidation")
            continue

        if name in required:
            # El check puede acabar después de renovar aunque el workflow
            # comenzase ANTES. run_created_at debe ser el run real (API Actions).
            made = _time(row.get("run_created_at"))
            if (made is None or made <= stamp or type(row.get("run_attempt")) is not int
                or row["run_attempt"] != 1):
                return Decision(False, "old_or_retried_required_run")
            if name in by_name or app != required[name]:
                return Decision(False, "ambiguous_check_identity")
            if row.get("status") != "completed" or row.get("conclusion") != "success":
                return Decision(False, "required_check_not_green")
            completed = _time(row.get("completed_at"))
            if completed is None or not stamp < made <= completed <= now:
                return Decision(False, "required_check_not_fresh")
            by_name[name] = row
        else:
            # Los jobs informativos de simulación no son puertas: un SKIPPED
            # autenticado de ese nombre exacto no altera el fingerprint.
            # Un check de Policy, gate requerido o alias NUNCA hereda exención.
            if (name == "Auto-merge simulación" and app == "github-actions"
                and row.get("status") == "completed"
                and row.get("conclusion") == "skipped"):
                continue
            if row.get("status") != "completed":
                return Decision(False, "other_check_in_progress")
            if row.get("conclusion") != "success":
                return Decision(False, "other_check_not_green")
            # No heredar un Policy/seguridad "verde" emitido antes de
            # renovar la aceptación sobre el mismo HEAD. Solo cuenta
            # ejecución nueva, primer intento y finalización comprobable.
            extra_started = _time(row.get("run_created_at"))
            extra_finished = _time(row.get("completed_at"))
            if (extra_started is None or extra_finished is None
                or not stamp < extra_started <= extra_finished <= now
                or type(row.get("run_attempt")) is not int
                or row["run_attempt"] != 1):
                return Decision(False, "other_check_not_fresh")
    if set(by_name) != set(required):
        return Decision(False, "missing_required_checks")

    # Una solicitud de cambios NO se invalida por avanzar HEAD ni por COMMENTED
    # ni por APPROVED de otro usuario. Solo el mismo autor puede superarla con
    # una nueva APPROVED exact-HEAD; una review DISMISSED ya no es veto efectivo.
    ordered = []
    review_ids = set()
    for review in reviews:
        if not isinstance(review, dict):
            return Decision(False, "unreadable_review")
        actor, state, ident = review.get("actor"), review.get("state"), review.get("id")
        when = _time(review.get("submitted_at"))
        if (not isinstance(actor, str) or not actor.strip()
            or type(ident) is not int or ident <= 0 or ident in review_ids
            or when is None or state not in (
                "CHANGES_REQUESTED", "APPROVED", "COMMENTED", "DISMISSED")):
            return Decision(False, "ambiguous_review_history")
        review_ids.add(ident)
        ordered.append((when, ident, actor.lower(), state, review.get("head_sha")))
    ordered.sort(key=lambda row: (row[0], row[1]))
    # Un timestamp igual para revisiones distintas impide probar precedencia.
    if len({entry[0] for entry in ordered}) != len(ordered):
        return Decision(False, "ambiguous_review_order")
    veto_by_author = set()
    approved_by_author = set()
    approval_ids: dict[str, int] = {}
    for when, _, actor, state, review_head in ordered:
        if state == "CHANGES_REQUESTED":
            veto_by_author.add(actor)
            approved_by_author.discard(actor)
            approval_ids.pop(actor, None)
        elif state == "APPROVED" and review_head == sha:
            # Una review auténtica no prueba autoridad para aprobar.
            if reviewer_permissions.get(actor) not in ("write", "maintain", "admin"):
                return Decision(False, "review_authority_unverified")
            # Una aprobación nueva del mismo autor puede levantar su propio veto.
            veto_by_author.discard(actor)
            if stamp < when <= now and actor != str(issue.get("owner", "")).lower():
                approved_by_author.add(actor)
                approval_ids[actor] = _
        elif state == "DISMISSED":
            # No usar un dismissal ajeno para borrar un veto de otra review:
            # GitHub marca como DISMISSED la review específica revocada.
            pass
    if veto_by_author:
        return Decision(False, "requested_changes")
    if not approved_by_author:
        return Decision(False, "required_review_not_approved")

    material = {"repo": repo, "issue": num, "uuid": uuid, "pin": pin,
                "sha": sha, "base_sha": base_sha,
                "checks": sorted(row["id"] for row in by_name.values()),
                "approvals": sorted(approval_ids.values())}
    key = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
    return Decision(True, "fresh_evidence_candidate_only", key)


class EvidenceUnavailable(ValueError):
    """No hay snapshot autenticado, completo y coherente para recuperar."""


_ACTIONS_URL = re.compile(
    r"^https://github\.com/([^/]+/[^/]+)/actions/runs/([0-9]+)/job/([0-9]+)$"
)


def _bounded_list(api: Any, suffix: str) -> list[dict]:
    """Lee listas REST completas con un máximo de 99 entradas, fail-closed."""
    path = f"/repos/{api.repo}/{suffix}"
    rows = api.request("GET", path + ("&" if "?" in path else "?") + "per_page=100")
    if (not isinstance(rows, list) or len(rows) >= 100
            or any(not isinstance(row, dict) for row in rows)):
        raise EvidenceUnavailable("collection_unreadable_or_truncated")
    return rows


def _check_inventory(api: Any, sha: str, filter_name: str) -> list[dict]:
    """Lee todas las páginas con inventario estable y presupuesto acotado.

    Un total mutable, una página truncada, IDs repetidos o un cambio entre
    recorridos nunca pueden convertirse en evidencia terminal positiva.
    """
    if filter_name not in ("latest", "all"):
        raise EvidenceUnavailable("check_inventory_filter_invalid")
    error = ("check_inventory_partial" if filter_name == "latest"
             else "recovery_history_partial")
    path = (f"/repos/{api.repo}/commits/{sha}/check-runs?"
            f"filter={filter_name}&per_page=100")

    def scan() -> list[dict]:
        rows: list[dict] = []
        seen: set[int] = set()
        count = None
        for page in range(1, (_MAX_CHECKS + 99) // 100 + 1):
            url = path if page == 1 else f"{path}&page={page}"
            payload = api.request("GET", url)
            if not isinstance(payload, dict):
                raise EvidenceUnavailable(error)
            total, batch = payload.get("total_count"), payload.get("check_runs")
            if (type(total) is not int or not 1 <= total <= _MAX_CHECKS
                    or not isinstance(batch, list)
                    or any(not isinstance(row, dict) for row in batch)):
                raise EvidenceUnavailable(error)
            if count is None:
                count = total
            if total != count or len(batch) != min(100, count - len(rows)):
                raise EvidenceUnavailable(error)
            for item in batch:
                ident = item.get("id")
                if type(ident) is not int or ident <= 0 or ident in seen:
                    raise EvidenceUnavailable(error)
                seen.add(ident)
            rows.extend(batch)
            if len(rows) == count:
                return rows
        raise EvidenceUnavailable(error)

    observed = scan()
    if len(observed) > 100 and scan() != observed:
        raise EvidenceUnavailable("check_inventory_changed_during_scan")
    return observed


def _check_rows(api: Any, sha: str) -> list[dict]:
    """Inventario latest completo; nunca tratar página 1 como universo."""
    return _check_inventory(api, sha, "latest")


def _snapshot_check_rows(api: Any, sha: str) -> list[dict]:
    """Reconstruye Validar CI si latest solo muestra el recovery sintético.

    El check de recuperación nunca se cuenta como el gate CI ni se toma
    por una aprobación. _already_restored() verifica fingerprint y generación
    después de evaluar los checks de verdad. La falta de historial falla cerrada.
    """
    latest = _check_rows(api, sha)
    recovered = []
    ids: set[int] = set()
    for item in latest:
        ident = item.get("id")
        if type(ident) is not int or ident <= 0 or ident in ids:
            raise EvidenceUnavailable("latest_check_identity_ambiguous")
        ids.add(ident)
        output = item.get("output")
        if (item.get("name") == "Validar" and isinstance(output, dict)
            and output.get("title") == "Contrato renovado: evidencia fresca"):
            app, external = item.get("app"), item.get("external_id")
            if (not isinstance(app, dict) or app.get("slug") != "github-actions"
                or item.get("head_sha") != sha
                or item.get("status") != "completed"
                or item.get("conclusion") != "success"
                or not isinstance(external, str)
                or _PIN.fullmatch(external) is None
                or _time(item.get("completed_at")) is None):
                raise EvidenceUnavailable("untrusted_recovery_check")
            recovered.append(item)
    if not recovered:
        return latest
    if len(recovered) != 1:
        raise EvidenceUnavailable("ambiguous_recovery_check_latest")
    rows = _check_inventory(api, sha, "all")
    historical: dict[int, dict] = {}
    for item in rows:
        ident = item.get("id")
        if type(ident) is not int or ident <= 0 or ident in historical:
            raise EvidenceUnavailable("recovery_history_duplicate_id")
        historical[ident] = item
    for item in latest:
        old = historical.get(item["id"])
        if (old is None or any(old.get(k) != item.get(k)
            for k in ("id", "name", "head_sha", "status", "conclusion",
                      "external_id", "completed_at", "details_url"))):
            raise EvidenceUnavailable("latest_check_history_drift")
    cleaned = [item for item in latest if item["id"] != recovered[0]["id"]]
    if not any(
        item.get("name") == "Validar"
        and item.get("head_sha") == sha
        and isinstance(item.get("details_url"), str)
        and _ACTIONS_URL.fullmatch(item["details_url"]) for item in cleaned
    ):
        eligible = [
            item for item in rows
            if item.get("name") == "Validar"
            and item.get("head_sha") == sha
            and isinstance(item.get("app"), dict)
            and item["app"].get("slug") == "github-actions"
            and isinstance(item.get("details_url"), str)
            and _ACTIONS_URL.fullmatch(item["details_url"])
            and item.get("status") == "completed"
            and (not isinstance(item.get("output"), dict)
                 or item["output"].get("title") != "Contrato renovado: evidencia fresca")
        ]
        if not eligible:
            raise EvidenceUnavailable("original_ci_validar_missing")
        timed = [(_time(item.get("completed_at")), item) for item in eligible]
        if any(when is None for when, _ in timed):
            raise EvidenceUnavailable("original_ci_validar_time_invalid")
        timed.sort(key=lambda pair: pair[0], reverse=True)
        if len(timed) > 1 and timed[0][0] == timed[1][0]:
            raise EvidenceUnavailable("original_ci_validar_ambiguous")
        cleaned.append(timed[0][1])
    return cleaned


def _normalized_check(api: Any, row: dict, sha: str) -> dict:
    """Une el check a su job/run real; no confiar en timestamps de check aislados."""
    app = row.get("app")
    slug = app.get("slug") if isinstance(app, dict) else None
    name = row.get("name")
    ident = row.get("id")
    if (type(ident) is not int or ident <= 0 or not isinstance(name, str)
        or not isinstance(slug, str) or row.get("head_sha") != sha):
        raise EvidenceUnavailable("check_identity_invalid")
    status, conclusion = row.get("status"), row.get("conclusion")
    if status not in ("queued", "in_progress", "completed"):
        raise EvidenceUnavailable("check_status_invalid")
    normalized = {
        "id": ident, "name": name, "app": slug, "head_sha": sha,
        "status": status, "conclusion": conclusion,
        "completed_at": row.get("completed_at"),
        "title": (row.get("output") or {}).get("title")
            if isinstance(row.get("output"), dict) else None,
    }
    # Solo este fallo sintético bot ya publicado puede ser histórico.
    if (name == "Validar"
        and normalized["title"] == "Renovación explícita del contrato"
        and conclusion == "failure"):
        if slug != "github-actions" or status != "completed":
            raise EvidenceUnavailable("invalid_renewal_veto")
        return normalized

    if slug == "github-actions" and name in _PROFILES[api.repo.lower()]:
        match = _ACTIONS_URL.fullmatch(str(row.get("details_url") or ""))
        if match is None or match.group(1).lower() != api.repo.lower():
            raise EvidenceUnavailable("check_has_no_trusted_workflow_job")
        run_id, job_id = int(match.group(2)), int(match.group(3))
        run = api.request("GET", f"/repos/{api.repo}/actions/runs/{run_id}")
        job = api.request("GET", f"/repos/{api.repo}/actions/jobs/{job_id}")
        if (not isinstance(run, dict) or not isinstance(job, dict)
            or run.get("id") != run_id or job.get("id") != job_id
            or job.get("run_id") != run_id or run.get("head_sha") != sha
            or run.get("event") != "pull_request"
            or (api.repo.lower() == "pl0n3r/factory"
                and name in _FACTORY_WORKFLOW_PATHS
                and str(run.get("path") or "").split("@", 1)[0]
                    != _FACTORY_WORKFLOW_PATHS[name])
            or not isinstance(run.get("repository"), dict)
            or run["repository"].get("full_name", "").lower() != api.repo.lower()
            or job.get("name") != name
            or job.get("conclusion") != conclusion
            or job.get("status") != status
            or str(job.get("check_run_url") or "").lower() != (
                f"https://api.github.com/repos/{api.repo}/check-runs/{ident}".lower())):
            raise EvidenceUnavailable("workflow_job_identity_mismatch")
        normalized["run_id"] = run_id
        normalized["run_created_at"] = run.get("created_at")
        normalized["run_attempt"] = run.get("run_attempt")
    elif slug in ("sonarqubecloud", "github-advanced-security"):
        # Proveedores identificados por app instalada. Sin Actions run_id.
        normalized["run_created_at"] = row.get("started_at")
        normalized["run_attempt"] = 1
    else:
        # Los nombres exigidos por el perfil deben pertenecer a SU app exacta.
        if name in _PROFILES[api.repo.lower()]:
            raise EvidenceUnavailable("required_check_wrong_app")
        normalized["run_created_at"] = row.get("started_at")
        normalized["run_attempt"] = 1
    return normalized




def _verified_statuses(api: Any, sha: str) -> list[dict]:
    """Cruza dos inventarios REST autenticados: totalidad y autor de cada status.

    /status incluye el estado combinado y total_count, pero omite creator.
    /statuses preserva creator y el ID. Exigir igualdad exacta por ID evita
    tratar una primera página, una carrera o un emisor anónimo como revisión.
    """
    payload = api.request("GET", f"/repos/{api.repo}/commits/{sha}/status?per_page=100")
    if not isinstance(payload, dict):
        raise EvidenceUnavailable("combined_status_invalid")
    rows, count = payload.get("statuses"), payload.get("total_count")
    if (payload.get("sha") not in (None, sha) or payload.get("state") != "success"
        or type(count) is not int or count <= 0 or count >= 100
        or not isinstance(rows, list) or len(rows) != count):
        raise EvidenceUnavailable("combined_status_partial_or_red")

    individual = api.request(
        "GET", f"/repos/{api.repo}/commits/{sha}/statuses?per_page=100")
    # /status muestra un único estado vigente por contexto; /statuses incluye
    # versiones históricas que no deben sustituirlo.
    if not isinstance(individual, list) or not count <= len(individual) < 100:
        raise EvidenceUnavailable("individual_statuses_incomplete")
    by_id = {}
    newest_by_context = {}
    for item in individual:
        if not isinstance(item, dict):
            raise EvidenceUnavailable("individual_status_unreadable")
        ident, creator = item.get("id"), item.get("creator")
        if (type(ident) is not int or ident <= 0 or ident in by_id
            or not isinstance(creator, dict)
            or not isinstance(creator.get("login"), str)
            or not creator["login"].strip()):
            raise EvidenceUnavailable("individual_status_identity_untrusted")
        context = item.get("context")
        if not isinstance(context, str) or not context.strip():
            raise EvidenceUnavailable("individual_status_context_untrusted")
        by_id[ident] = item
        # GitHub REST ordena el historial del más reciente al más antiguo.
        newest_by_context.setdefault(context, item)
    if len(newest_by_context) != count:
        raise EvidenceUnavailable("individual_status_context_mismatch")

    normalized = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceUnavailable("external_status_row_invalid")
        ident = row.get("id")
        detail = newest_by_context.get(row.get("context"))
        if type(ident) is not int or detail is None or detail.get("id") != ident:
            raise EvidenceUnavailable("external_status_not_latest")
        fields = ("id", "context", "state", "description", "created_at",
                  "updated_at", "target_url")
        if (detail is None
            or any(row.get(field) != detail.get(field) for field in fields)):
            raise EvidenceUnavailable("external_status_identity_changed")
        context = row.get("context")
        if not isinstance(context, str) or not context.strip():
            raise EvidenceUnavailable("external_status_context_invalid")
        if context in seen:
            continue
        seen.add(context)
        normalized.append({
            "context": context,
            "state": row.get("state"),
            "created_at": row.get("created_at"),
            "description": row.get("description"),
            "creator": detail["creator"]["login"],
        })
    if len(seen) != count:
        raise EvidenceUnavailable("external_status_duplicate_context")
    if any(row["state"] != "success" for row in normalized):
        raise EvidenceUnavailable("external_status_red")
    return normalized


def _review_threads(api: Any, pr_number: int) -> list[dict]:
    """GraphQL autenticado; sin páginas truncadas, permiso insuficiente o errors.

    No realizar checkout/ejecutar contenido de los hilos. La respuesta GraphQL
    se usa exclusivamente como veto a revisiones que siguen abiertas.
    """
    owner, name = api.repo.split("/", 1)
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){"
        "reviewThreads(first:100){"
        "nodes{id isResolved isOutdated}"
        "pageInfo{hasNextPage endCursor}"
        "}}}}"
    )
    result = api.request(
        "POST", "/graphql",
        {"query": query, "variables": {
            "owner": owner, "name": name, "number": pr_number}},
    )
    if not isinstance(result, dict) or result.get("errors"):
        raise EvidenceUnavailable("review_threads_graphql_error")
    data = result.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    pull = repository.get("pullRequest") if isinstance(repository, dict) else None
    connection = pull.get("reviewThreads") if isinstance(pull, dict) else None
    if not isinstance(connection, dict):
        raise EvidenceUnavailable("review_threads_unreadable")
    rows, page = connection.get("nodes"), connection.get("pageInfo")
    if (not isinstance(rows, list) or len(rows) >= 100
        or not isinstance(page, dict) or page.get("hasNextPage") is not False
        or any(not isinstance(row, dict)
               or not isinstance(row.get("id"), str)
               or type(row.get("isResolved")) is not bool
               for row in rows)):
        raise EvidenceUnavailable("review_threads_partial_or_invalid")
    if len({row["id"] for row in rows}) != len(rows):
        raise EvidenceUnavailable("duplicate_review_thread")
    return [{"id": row["id"], "isResolved": row["isResolved"]}
            for row in rows]

def _canonical_issue_status(issue: object) -> str:
    """Conjunto completo y exclusivo de estados, no subconjunto permisivo."""
    from scripts.coordinar_trabajo import STATUS_LABELS
    if not isinstance(issue, dict):
        raise EvidenceUnavailable("issue_unreadable")
    labels = issue.get("labels")
    if not isinstance(labels, list):
        raise EvidenceUnavailable("issue_labels_unreadable")
    states = []
    for entry in labels:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise EvidenceUnavailable("issue_label_malformed")
        name = entry["name"]
        if name in STATUS_LABELS:
            states.append(name)
        elif name.casefold().startswith(("estado:", "status:")):
            raise EvidenceUnavailable("unknown_status_label")
    if (len(states) != 1
        or states[0] not in ("estado: reservado", "estado: en revisión")):
        raise EvidenceUnavailable("issue_status_ambiguous_or_blocked")
    return states[0]


def _trusted_reviewer_permissions(api: Any, reviews: list[dict]) -> dict[str, str]:
    """Verifica aprobaciones con permisos reales desde GitHub autenticado.

    No deriva autoridad de actor, author_association, PR body ni etiquetas.
    Si falta autorización de lectura, deniega sin conceder permisos.
    """
    actors = set()
    for review in reviews:
        if not isinstance(review, dict):
            raise EvidenceUnavailable("review_history_unreadable")
        if review.get("state") == "APPROVED":
            login = (review.get("user") or {}).get("login")
            if (not isinstance(login, str)
                or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login) is None):
                raise EvidenceUnavailable("review_authority_invalid_actor")
            actors.add(login.lower())
    permissions = {}
    for actor in sorted(actors):
        try:
            data = api.request(
                "GET", f"/repos/{api.repo}/collaborators/{actor}/permission")
        except Exception as exc:
            raise EvidenceUnavailable("review_authority_unverified") from exc
        user = data.get("user") if isinstance(data, dict) else None
        permission = data.get("permission") if isinstance(data, dict) else None
        if (not isinstance(user, dict)
            or not isinstance(user.get("login"), str)
            or user["login"].lower() != actor
            or permission not in ("none", "read", "triage", "write",
                                  "maintain", "admin")):
            raise EvidenceUnavailable("review_authority_unverified")
        permissions[actor] = permission
    return permissions


def _verified_lease_assignee(issue: object, owner: object) -> str:
    """Exige un solo asignado autenticado igual al titular de la lease V3."""
    if not isinstance(issue, dict) or not isinstance(owner, str):
        raise EvidenceUnavailable("lease_assignee_authority_invalid")
    assigned = issue.get("assignees")
    if not isinstance(assigned, list) or len(assigned) != 1:
        raise EvidenceUnavailable("lease_assignee_authority_invalid")
    actor = assigned[0]
    login = actor.get("login") if isinstance(actor, dict) else None
    if (not isinstance(login, str)
        or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login) is None
        or login.lower() != owner.lower()):
        raise EvidenceUnavailable("lease_assignee_authority_invalid")
    # REST puede exponer también un asignado singular; si está presente
    # debe coincidir con la lista completa verificada, nunca divergir.
    if "assignee" in issue:
        primary = issue.get("assignee")
        if (not isinstance(primary, dict)
            or not isinstance(primary.get("login"), str)
            or primary["login"].lower() != login.lower()):
            raise EvidenceUnavailable("lease_assignee_authority_invalid")
    return login.lower()


def collect_snapshot(api: Any, pr_number: int) -> dict:
    """Obtiene evidencia autenticada, con relectura final, sin mutaciones.

    Solo rutas canónicas en repos soportados. Este lector no decide la fusión,
    no publica check-runs y no acepta material JSON suministrado por el autor.
    """
    if (not isinstance(getattr(api, "repo", None), str)
        or api.repo.lower() not in _PROFILES or type(pr_number) is not int
        or pr_number <= 0):
        raise EvidenceUnavailable("unsupported_repo_or_pr")

    from scripts.aceptacion_kit import contract_fingerprint
    from scripts.coordinar_trabajo import (
        latest_reservation, reservation_from_pr_body, issue_from_branch,
    )

    pr = api.pull(pr_number)
    if not isinstance(pr, dict):
        raise EvidenceUnavailable("pr_unreadable")
    head, base = pr.get("head"), pr.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise EvidenceUnavailable("pr_ref_unreadable")
    sha, branch = head.get("sha"), head.get("ref")
    base_sha = base.get("sha")
    num = issue_from_branch(branch) if isinstance(branch, str) else None
    if (not isinstance(base_sha, str) or _SHA.fullmatch(base_sha) is None
        or not isinstance(sha, str) or _SHA.fullmatch(sha) is None or num is None
        or pr.get("state") != "open" or pr.get("draft") is not False
        or base.get("ref") != "main"
        or (head.get("repo") or {}).get("full_name", "").lower() != api.repo.lower()):
        raise EvidenceUnavailable("pr_not_eligible")

    issue = api.issue(num)
    comments = api.issue_comments(num)
    lease = latest_reservation(comments)
    if (not isinstance(issue, dict) or not isinstance(lease, dict)
        or issue.get("number") != num or issue.get("state") != "open"
        or lease.get("active") is not True or lease.get("version") != 3
        or lease.get("branch") != branch
        or lease.get("reason") not in ("renovar-contrato", "recuperacion-inactividad")
        or lease.get("reservation_id") != reservation_from_pr_body(pr.get("body") or "")
        or lease.get("acceptance_sha256") != contract_fingerprint(issue.get("body") or "")):
        raise EvidenceUnavailable("active_renewed_lease_mismatch")

    # Read-only staging: an authenticated recovery succession is necessary,
    # but not sufficient for a fresh invalidation on the current HEAD.
    # Fail closed until the original generation and exact-SHA ancestry proof
    # are added; never publish a check from this branch alone.
    if lease.get("reason") == "recuperacion-inactividad":
        _trusted_renewal_lineage(comments, lease)
        raise EvidenceUnavailable("recovered_generation_pending_ancestry_proof")

    renewal = [
        c for c in comments
        if (isinstance(c, dict) and (c.get("user") or {}).get("login") == "github-actions[bot]"
            and str(c.get("body") or "").find('"reason":"renovar-contrato"') >= 0
            and str(c.get("body") or "").find(str(lease["reservation_id"])) >= 0)
    ]
    if len(renewal) != 1:
        raise EvidenceUnavailable("ambiguous_renewal_provenance")
    created_at = renewal[0].get("created_at")
    if _time(created_at) is None:
        raise EvidenceUnavailable("renewal_time_unavailable")
    status = _canonical_issue_status(issue)
    assignee = _verified_lease_assignee(issue, lease.get("owner"))

    identity = {"repo": api.repo, "issue": num,
                "uuid": lease["reservation_id"],
                "pin": lease["acceptance_sha256"],
                "head_sha": sha, "base_sha": base_sha, "branch": branch}
    reviews = _bounded_list(api, f"pulls/{pr_number}/reviews")
    normalized_reviews = [
        {"id": row.get("id"), "actor": (row.get("user") or {}).get("login"),
         "state": row.get("state"), "head_sha": row.get("commit_id"),
         "submitted_at": row.get("submitted_at")}
        for row in reviews
    ]
    reviewer_permissions = _trusted_reviewer_permissions(api, reviews)
    rows = _snapshot_check_rows(api, sha)
    checks = [_normalized_check(api, row, sha) for row in rows]
    # Los dos inventarios requieren completitud acreditada, nunca una página
    # default de 30 estados que puede ocultar un veto de seguridad.
    statuses = _verified_statuses(api, sha)
    threads = _review_threads(api, pr_number)

    # Las fuentes pueden cambiar mientras se recolectan: doble lectura.
    after_pr, after_issue = api.pull(pr_number), api.issue(num)
    # El ref/SHA no certifica el repositorio de origen: una segunda lectura
    # inconsistente o un fork distinto invalida el snapshot completo.
    after_head = after_pr.get("head") if isinstance(after_pr, dict) else None
    after_repo = after_head.get("repo") if isinstance(after_head, dict) else None
    after_status = _canonical_issue_status(after_issue)
    after_lease = latest_reservation(api.issue_comments(num))
    after_assignee = _verified_lease_assignee(after_issue, lease.get("owner"))
    if (not isinstance(after_pr, dict) or not isinstance(after_issue, dict)
        or not isinstance(after_repo, dict)
        or not isinstance(after_repo.get("full_name"), str)
        or after_repo["full_name"].lower() != api.repo.lower()
        or not isinstance(after_lease, dict) or after_lease != lease
        or (after_pr.get("head") or {}).get("sha") != sha
        or (after_pr.get("head") or {}).get("ref") != branch
        or (after_pr.get("base") or {}).get("ref") != "main"
        or (after_pr.get("base") or {}).get("sha") != base_sha
        or after_pr.get("state") != "open" or after_pr.get("draft") is not False
        or after_issue.get("state") != "open"
        or after_status != status
        or after_assignee != assignee
        or after_issue.get("assignees") != issue.get("assignees")
        or after_issue.get("assignee") != issue.get("assignee")
        or contract_fingerprint(after_issue.get("body") or "") != identity["pin"]):
        raise EvidenceUnavailable("identity_changed_during_snapshot")
    # Releer autoridad y reviews: una revocación durante el snapshot veta.
    if (_bounded_list(api, f"pulls/{pr_number}/reviews") != reviews
        or _trusted_reviewer_permissions(api, reviews) != reviewer_permissions):
        raise EvidenceUnavailable("review_authority_changed_during_snapshot")
    # Un hilo abierto/resuelto tras la primera lectura cambia el veto de
    # revisión, incluso si los approvals y el HEAD permanecen iguales.
    if _review_threads(api, pr_number) != threads:
        raise EvidenceUnavailable("review_threads_changed_during_snapshot")
    return {
        "repo": api.repo, "issue": {"number": num, "owner": lease["owner"],
            "state": "open", "status": status, "active": lease["active"],
            "version": 3, "branch": branch, "reservation_id": identity["uuid"],
            "acceptance_sha256": identity["pin"]},
        "pr": {"state": "open", "draft": False, "repo": api.repo,
               "branch": branch, "head_sha": sha, "base_sha": base_sha},
        "before": identity, "after": dict(identity),
        "renewal": {"user": "github-actions[bot]", "reason": "renovar-contrato",
                    "uuid": identity["uuid"], "pin": identity["pin"],
                    "created_at": created_at},
        "checks": checks, "reviews": normalized_reviews,
        "reviewer_permissions": reviewer_permissions, "statuses": statuses,
        "review_threads": threads, "reviewer_required": True,
    }



def _trusted_renewal_lineage(comments: list[dict], current: dict) -> dict:
    """Verifica sucesión V3 renovación -> recuperación/transferencia, read-only.

    La prueba de procedencia NO autoriza por sí sola restaurar Validar.
    La invalidación, HEAD, locks, reviews y bootstrap siguen gates separados.
    """
    from scripts.coordinar_trabajo import reservation_from_text

    if not isinstance(comments, list) or not isinstance(current, dict):
        raise EvidenceUnavailable("renewal_lineage_invalid")
    chain: list[tuple[dict, datetime]] = []
    for comment in comments:
        if not isinstance(comment, dict):
            raise EvidenceUnavailable("renewal_lineage_invalid")
        actor = comment.get("user")
        body = comment.get("body")
        if not isinstance(actor, dict) or actor.get("login") != "github-actions[bot]":
            continue
        if not isinstance(body, str) or "<!-- condor-reserva" not in body:
            continue
        marker = reservation_from_text(body)
        created = _time(comment.get("created_at"))
        updated = _time(comment.get("updated_at"))
        if (actor.get("type") != "Bot" or body.count("<!-- condor-reserva") != 1
            or not isinstance(marker, dict) or marker.get("version") != 3
            or created is None or updated != created):
            raise EvidenceUnavailable("renewal_lineage_untrusted_marker")
        chain.append((marker, created))
    if not chain or chain[-1][0] != current:
        raise EvidenceUnavailable("renewal_lineage_current_lease_mismatch")
    renewal_indices = [
        idx for idx, (marker, _) in enumerate(chain)
        if marker.get("reason") == "renovar-contrato"
    ]
    if not renewal_indices:
        raise EvidenceUnavailable("renewal_lineage_original_missing")
    start = renewal_indices[-1]
    original, started = chain[start]
    unchanged = (
        "owner", "branch", "acceptance_sha256",
        "task_marker_sha256", "task_paths", "task_depends_on",
    )
    ident = original.get("reservation_id")
    if (original.get("active") is not True or original.get("owner") != "pl0n3r"
        or not isinstance(ident, str) or _UUID.fullmatch(ident) is None
        or not isinstance(original.get("acceptance_sha256"), str)
        or _PIN.fullmatch(original["acceptance_sha256"]) is None
        or not isinstance(original.get("task_marker_sha256"), str)
        or _PIN.fullmatch(original["task_marker_sha256"]) is None
        or not isinstance(original.get("task_paths"), list)
        or not original["task_paths"]
        or not isinstance(original.get("task_depends_on"), list)):
        raise EvidenceUnavailable("renewal_lineage_original_invalid")
    seen = {ident}
    previous = started
    for marker, stamp in chain[start + 1:]:
        successor_id = marker.get("reservation_id")
        if (marker.get("reason") not in ("recuperacion-inactividad", "transferir")
            or marker.get("active") is not True
            or not isinstance(successor_id, str)
            or _UUID.fullmatch(successor_id) is None
            or successor_id in seen or stamp <= previous
            or any(marker.get(field) != original.get(field) for field in unchanged)):
            raise EvidenceUnavailable("renewal_lineage_successor_invalid")
        previous = stamp
        seen.add(successor_id)
    return {
        "renewal_uuid": ident,
        "current_uuid": current["reservation_id"],
        "acceptance_sha256": original["acceptance_sha256"],
        "renewed_at": started.isoformat(),
        "recovery_count": sum(1 for marker, _ in chain[start + 1:]
                              if marker["reason"] == "recuperacion-inactividad"),
        "transfer_count": sum(1 for marker, _ in chain[start + 1:]
                              if marker["reason"] == "transferir"),
    }


def _invalidation_present(api: Any, sha: str, before: datetime, issue_number: int,
                          reservation_id: str, acceptance_pin: str) -> bool:
    """Acepta solo la invalidación auténtica de ESTA reserva y contrato V3."""
    if (not isinstance(reservation_id, str) or _UUID.fullmatch(reservation_id) is None
        or not isinstance(acceptance_pin, str) or _PIN.fullmatch(acceptance_pin) is None):
        raise EvidenceUnavailable("invalidation_generation_invalid")
    expected_summary = (
        f"Issue #{issue_number}: contrato renovado explícitamente; "
        f"reserva V3 {reservation_id}; aceptación SHA-256 {acceptance_pin}; "
        "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
    )
    rows = _check_inventory(api, sha, "all")
    valid = []
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceUnavailable("historical_check_invalid")
        app = row.get("app")
        output = row.get("output")
        if (row.get("name") == "Validar"
            and isinstance(app, dict) and app.get("slug") == "github-actions"
            and isinstance(output, dict)
            and output.get("title") == "Renovación explícita del contrato"
            and row.get("status") == "completed"
            and row.get("conclusion") == "failure"
            and row.get("head_sha") == sha):
            timestamp = _time(row.get("completed_at"))
            # La invalidación se publica ANTES del marker nuevo de la lease.
            if (timestamp is None
                or not 0 <= (before - timestamp).total_seconds() <= 300
                or output.get("summary") != expected_summary):
                continue
            valid.append(row.get("id"))
    return len(valid) == 1 and type(valid[0]) is int


def _already_restored(api: Any, sha: str, fingerprint: str,
                      renewed_at: datetime) -> bool:
    """Idempotencia de una generación V3 exacta, no de un título histórico.

    Exige toda la historia: éxitos anteriores al marker no acreditan la
    generación actual. Una recuperación ajena actual veta la operación.
    """
    if (_SHA.fullmatch(sha) is None or _PIN.fullmatch(fingerprint) is None
        or not isinstance(renewed_at, datetime) or renewed_at.tzinfo is None):
        raise EvidenceUnavailable("recovery_identity_invalid")
    rows = _check_inventory(api, sha, "all")

    recovered = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceUnavailable("restore_inventory_row_invalid")
        if (row.get("name") != "Validar"
            or not isinstance(row.get("output"), dict)
            or row["output"].get("title") != "Contrato renovado: evidencia fresca"):
            continue
        ident, external = row.get("id"), row.get("external_id")
        app = row.get("app")
        completed = _time(row.get("completed_at"))
        if (type(ident) is not int or ident in seen or ident <= 0
            or not isinstance(app, dict) or app.get("slug") != "github-actions"
            or row.get("head_sha") != sha
            or row.get("status") != "completed" or row.get("conclusion") != "success"
            or not isinstance(external, str) or _PIN.fullmatch(external) is None
            or completed is None):
            raise EvidenceUnavailable("restore_check_untrusted_or_incomplete")
        seen.add(ident)
        if completed > renewed_at:
            if external != fingerprint:
                raise EvidenceUnavailable("different_renewal_recovery_detected")
            recovered.append(ident)
    if len(recovered) > 1:
        raise EvidenceUnavailable("duplicate_current_generation_recovery")
    return len(recovered) == 1

def reconcile_from_workflow_run(api: Any, run_id: int) -> str:
    """Publica un check nuevo y auditable exclusivamente tras preflight completo.

    El evento no transfiere autoridad; su run/PR se verifican por REST canónico.
    Serializar llamadas en el workflow, nunca emitir desde inputs del PR.
    """
    if (getattr(api, "repo", "").lower() != "pl0n3r/factory"
        or type(run_id) is not int or run_id < 1):
        raise EvidenceUnavailable("workflow_trigger_not_canonical")
    from scripts.coordinar_trabajo import require_sweep_running
    require_sweep_running(api)
    run = api.request("GET", f"/repos/{api.repo}/actions/runs/{run_id}")
    if not isinstance(run, dict):
        raise EvidenceUnavailable("workflow_run_unreadable")
    pulls = run.get("pull_requests")
    if (run.get("id") != run_id or run.get("name") != "CI factory"
        or run.get("event") != "pull_request"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("run_attempt") != 1
        or str(run.get("path") or "").split("@")[0]
            != ".github/workflows/factory-ci.yml"
        or not isinstance(run.get("head_sha"), str)
        or (run.get("head_repository") or {}).get("full_name", "").lower()
            != api.repo.lower()
        or not isinstance(pulls, list) or len(pulls) != 1
        or type(pulls[0].get("number")) is not int):
        raise EvidenceUnavailable("workflow_run_not_eligible")
    pr_number = pulls[0]["number"]
    sha = run["head_sha"]
    first = collect_snapshot(api, pr_number)
    if first["pr"]["head_sha"] != sha:
        raise EvidenceUnavailable("trigger_head_mismatch")
    renewal_time = _time(first["renewal"]["created_at"])
    if renewal_time is None or _time(run.get("created_at")) is None:
        raise EvidenceUnavailable("renewal_or_run_timestamp_missing")
    if _time(run["created_at"]) <= renewal_time:
        raise EvidenceUnavailable("workflow_started_before_renewal")
    # Al menos las suites decisivas deben proceder del run recién completado.
    for name in ("Tests de scripts", "Validar", "Criterios de aceptación"):
        evidence = [x for x in first["checks"] if x["name"] == name
                    and x.get("run_id") == run_id]
        if len(evidence) != 1:
            raise EvidenceUnavailable("required_ci_run_not_triggering_run")
    if not _invalidation_present(
        api, sha, renewal_time, first["issue"]["number"],
        first["issue"]["reservation_id"], first["issue"]["acceptance_sha256"],
    ):
        raise EvidenceUnavailable("original_renewal_failure_not_proven")
    first_decision = evaluate(first)
    if not first_decision.ready:
        return "blocked:" + first_decision.reason
    if _already_restored(api, sha, first_decision.fingerprint, renewal_time):
        return "already_restored"

    # La comprobación está acotada a PRs aún no integrados en main exacto.
    compare = api.request(
        "GET", f"/repos/{api.repo}/compare/main...{sha}",
    )
    if (not isinstance(compare, dict)
        or compare.get("behind_by") != 0
        or type(compare.get("ahead_by")) is not int
        or compare["ahead_by"] <= 0):
        raise EvidenceUnavailable("main_not_reconciled")

    second = collect_snapshot(api, pr_number)
    second_decision = evaluate(second)
    if second["pr"]["base_sha"] != first["pr"]["base_sha"]:
        raise EvidenceUnavailable("main_base_changed_during_revalidation")
    second_compare = api.request("GET", f"/repos/{api.repo}/compare/main...{sha}")
    if (not isinstance(second_compare, dict)
        or second_compare.get("behind_by") != 0
        or type(second_compare.get("ahead_by")) is not int
        or second_compare["ahead_by"] <= 0):
        raise EvidenceUnavailable("main_moved_during_revalidation")
    if (not second_decision.ready
        or second_decision.fingerprint != first_decision.fingerprint):
        raise EvidenceUnavailable("recovery_state_changed_during_preflight")
    require_sweep_running(api)
    if _already_restored(api, sha, second_decision.fingerprint, renewal_time):
        return "already_restored"
    # No existe exclusión mutua CAS con /renovar-contrato. La bandera
    # ambiental por sí sola NO acredita lock, política, revisión ni permiso.
    # La ruta mutante permanece imposible incluso con opt-in accidental.
    import os
    if os.getenv("FACTORY_RENEWAL_CHECK_WRITER_ENABLED") != "1":
        return "disabled_pending_cas_and_review_threads"
    raise EvidenceUnavailable("shared_v3_cas_not_implemented")



def main(argv: list[str] | None = None) -> int:
    """Solo CLI canónico; EvidenceUnavailable nunca publica un check falso."""
    import argparse
    from scripts.coordinar_trabajo import GitHub

    parser = argparse.ArgumentParser(description="Reconciliar contrato renovado")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        outcome = reconcile_from_workflow_run(GitHub(args.repo), args.run_id)
    except EvidenceUnavailable as exc:
        print("No elegible para recuperación: " + str(exc))
        return 0
    print("Reconciliación: " + outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
