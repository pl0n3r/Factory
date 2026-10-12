#!/usr/bin/env python3
"""Evidencia REST de actividad de una reserva V3: solo GET y UNKNOWN fail-closed."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from scripts.coordinar_trabajo import reservation_from_text

SHA = re.compile(r"[0-9a-f]{40}")
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
STATES = {"estado: reservado", "estado: en revisión", "estado: requiere recuperación"}
BOT = "github-actions[bot]"


class IncompleteEvidence(Exception):
    """Una sola página, identidad o cuota dudosa invalida todo el snapshot."""


def _time(value: Any, now: datetime) -> datetime:
    if type(value) is not str or STAMP.fullmatch(value) is None:
        raise IncompleteEvidence()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed > now:
            raise IncompleteEvidence()
        return parsed
    except (ValueError, OverflowError) as exc:
        raise IncompleteEvidence() from exc


def collect_activity(api: Any, issue_number: int, *, now: datetime,
                     max_requests: int = 32) -> dict[str, Any]:
    """Observa una hoja sin mutar GitHub ni decidir liberaciones.

    api.request debe ser el transporte REST autenticado. El resultado es
    serializable; un futuro adaptador del decisor validará los restantes
    gates (fase, lock, recuperación y kill switch) independientemente.
    """
    unknown = {"status": "UNKNOWN", "evidence_complete": False}
    try:
        repo = getattr(api, "repo", None)
        if (type(issue_number) is not int or issue_number <= 0
                or type(repo) is not str
                or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None
                or type(max_requests) is not int or not 1 <= max_requests <= 40
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            return unknown
        now = now.astimezone(timezone.utc)
        used = 0
        pagination: dict[str, dict[str, int]] = {}

        def get(path: str) -> Any:
            nonlocal used
            used += 1
            if used > max_requests:
                raise IncompleteEvidence()
            return api.request("GET", path)

        base = f"/repos/{repo}"
        budget = get("/rate_limit")
        core = budget.get("resources", {}).get("core", {}) if isinstance(budget, dict) else {}
        limit, remaining = core.get("limit"), core.get("remaining")
        if (type(limit) is not int or type(remaining) is not int
                or limit <= 0 or remaining < 0 or remaining > limit
                or remaining * 5 < limit):
            raise IncompleteEvidence()
        identity = get(base)
        if (not isinstance(identity, dict) or identity.get("full_name") != repo
                or type(identity.get("id")) is not int or identity["id"] <= 0):
            raise IncompleteEvidence()
        repo_id = identity["id"]

        def pages(path: str, *, name: str, expected: int | None = None,
                  checks: bool = False, commits: bool = False,
                  runs: bool = False) -> list[dict[str, Any]]:
            output: list[dict[str, Any]] = []
            seen: set[int | str] = set()
            for page in range(1, 6):
                suffix = "&" if "?" in path else "?"
                raw = get(f"{path}{suffix}per_page=100&page={page}")
                if checks or runs:
                    if (not isinstance(raw, dict)
                            or type(raw.get("total_count")) is not int
                            or raw["total_count"] < 0):
                        raise IncompleteEvidence()
                    count = raw["total_count"]
                    if expected is None:
                        expected = count
                    if count != expected:
                        raise IncompleteEvidence()
                    rows = raw.get("check_runs" if checks else "workflow_runs")
                else:
                    rows = raw
                if not isinstance(rows, list) or len(rows) > 100:
                    raise IncompleteEvidence()
                for item in rows:
                    if not isinstance(item, dict):
                        raise IncompleteEvidence()
                    ident = item.get("sha") if commits else item.get("id")
                    if commits:
                        if type(ident) is not str or SHA.fullmatch(ident) is None:
                            raise IncompleteEvidence()
                    elif type(ident) is not int or ident <= 0:
                        raise IncompleteEvidence()
                    if ident in seen:
                        raise IncompleteEvidence()
                    seen.add(ident)
                    output.append(item)
                if expected is not None and len(output) > expected:
                    raise IncompleteEvidence()
                if len(rows) < 100:
                    if expected is not None and len(output) != expected:
                        raise IncompleteEvidence()
                    # Cuerpos sin Link: una página corta no acredita por sí
                    # sola el cierre; exigir página centinela vacía.
                    probes = 0
                    if expected is None:
                        sentinel = get(f"{path}{suffix}per_page=100&page={page + 1}")
                        if not isinstance(sentinel, list) or sentinel:
                            raise IncompleteEvidence()
                        probes = 1
                    pagination[name] = {"pages": page + probes, "items": len(output)}
                    return output
            raise IncompleteEvidence()  # jamás tratar el prefijo como inventario íntegro

        path = f"{base}/issues/{issue_number}"
        issue = get(path)
        if (not isinstance(issue, dict) or issue.get("state") != "open"
                or type(issue.get("number")) is not int
                or issue["number"] != issue_number):
            raise IncompleteEvidence()
        labels = issue.get("labels")
        if not isinstance(labels, list) or not all(
                isinstance(v, dict) and type(v.get("name")) is str for v in labels):
            raise IncompleteEvidence()
        state_labels = [v["name"] for v in labels
                        if v["name"].casefold().startswith("estado:")]
        total = issue.get("comments")
        if (len(state_labels) != 1 or state_labels[0] not in STATES
                or type(total) is not int
                or not 1 <= total <= 500):
            raise IncompleteEvidence()
        comments = pages(f"{path}/comments", name="comments", expected=total)
        trusted: list[tuple[int, dict[str, Any], datetime]] = []
        for c in comments:
            user = c.get("user")
            if (not isinstance(user, dict) or type(user.get("login")) is not str
                    or not user["login"]):
                raise IncompleteEvidence()
            body = c.get("body")
            if user["login"] == BOT:
                if user.get("type") != "Bot":
                    raise IncompleteEvidence()
                if type(body) is str and "<!-- condor-reserva " in body:
                    marker = reservation_from_text(body)
                    if marker is None:
                        raise IncompleteEvidence()
                    created = _time(c.get("created_at"), now)
                    edited = c.get("updated_at")
                    updated = _time(edited, now) if edited is not None else created
                    if updated < created:
                        raise IncompleteEvidence()
                    trusted.append((c["id"], marker, updated))
        if not trusted:
            raise IncompleteEvidence()
        trusted.sort(key=lambda x: x[0])
        _, lease, since = trusted[-1]
        owner = lease.get("owner")
        branch = f"trabajo/issue-{issue_number}"
        if (lease.get("version") != 3 or lease.get("active") is not True
                or lease.get("branch") != branch
                or type(owner) is not str or not owner
                or type(lease.get("reservation_id")) is not str):
            raise IncompleteEvidence()

        # Un marker V3 solo no acredita autoridad: el Issue debe tener
        # exactamente un asignado, idéntico al titular autenticado del bot.
        assignees = issue.get("assignees")
        if (not isinstance(assignees, list) or len(assignees) != 1
                or not isinstance(assignees[0], dict)
                or type(assignees[0].get("login")) is not str
                or assignees[0]["login"] != owner):
            raise IncompleteEvidence()

        refpath = f"{base}/git/ref/heads/{branch}"
        def branch_sha() -> str:
            value = get(refpath)
            obj = value.get("object") if isinstance(value, dict) else None
            sha = obj.get("sha") if isinstance(obj, dict) else None
            if type(sha) is not str or SHA.fullmatch(sha) is None:
                raise IncompleteEvidence()
            return sha

        sha = branch_sha()
        latest = since
        for c in comments:
            if c.get("user", {}).get("login") == owner:
                when = _time(c.get("created_at"), now)
                if when >= since:
                    # login compartido entre agentes: sin credencial de
                    # sesión, no certificar actividad ni ausencia de ella.
                    raise IncompleteEvidence()

        since_param = quote(since.isoformat().replace("+00:00", "Z"), safe="")
        commits = pages(f"{base}/commits?sha={quote(branch, safe='')}&since={since_param}",
                        name="commits", commits=True)
        for commit in commits:
            author = commit.get("author")
            if (not isinstance(author, dict) or type(author.get("login")) is not str
                    or not author["login"]):
                raise IncompleteEvidence()
            if author["login"] == owner:
                details = commit.get("commit")
                actor = details.get("author") if isinstance(details, dict) else None
                when = _time(actor.get("date") if isinstance(actor, dict) else None, now)
                if when >= since:
                    latest = max(latest, when)

        pulls = pages(f"{base}/pulls?state=open", name="pulls")
        matching = []
        for pull in pulls:
            h = pull.get("head")
            if isinstance(h, dict) and h.get("ref") == branch:
                source = h.get("repo")
                if (not isinstance(source, dict)
                        or type(source.get("id")) is not int
                        or type(source.get("full_name")) is not str):
                    raise IncompleteEvidence()
                if source["id"] != repo_id:
                    if source["full_name"] == repo:
                        raise IncompleteEvidence()
                    continue  # fork con nombre de rama coincidente
                if source["full_name"] != repo or h.get("sha") != sha:
                    raise IncompleteEvidence()
                matching.append(pull)
        if len(matching) > 1:
            raise IncompleteEvidence()
        if matching:
            reviews = pages(f"{base}/pulls/{matching[0]['number']}/reviews", name="reviews")
            for review in reviews:
                author = review.get("user")
                if (not isinstance(author, dict) or type(author.get("login")) is not str
                        or not author["login"]):
                    raise IncompleteEvidence()
                # Any authenticated reviewer may veto the PR.  A missing or
                # unknown state cannot prove that no review gate is pending.
                review_state = review.get("state")
                if review_state not in (
                        "PENDING", "COMMENTED", "APPROVED", "DISMISSED",
                        "CHANGES_REQUESTED"):
                    raise IncompleteEvidence()
                if review_state == "CHANGES_REQUESTED":
                    raise IncompleteEvidence()
                if author["login"] == owner and review_state != "PENDING":
                    when = _time(review.get("submitted_at"), now)
                    if when >= since:
                        # La review pertenece al login, no a la sesión V3.
                        raise IncompleteEvidence()

        checks = pages(f"{base}/commits/{sha}/check-runs", name="checks", checks=True)
        running = False
        for check in checks:
            if check.get("head_sha") != sha:
                raise IncompleteEvidence()
            status = check.get("status")
            if status not in (
                    "queued", "in_progress", "requested",
                    "waiting", "pending", "completed"):
                raise IncompleteEvidence()
            if status != "completed":
                running = True

        # Los checks del HEAD no prueban que un run de un SHA anterior
        # haya terminado. Auditar todas las ejecuciones de esta rama.
        workflow_runs = pages(
            f"{base}/actions/runs?branch={quote(branch, safe='')}",
            name="runs", runs=True,
        )
        for run in workflow_runs:
            source = run.get("head_repository")
            run_sha = run.get("head_sha")
            if (run.get("head_branch") != branch
                    or not isinstance(source, dict)
                    or source.get("id") != repo_id
                    or source.get("full_name") != repo
                    or type(run_sha) is not str or SHA.fullmatch(run_sha) is None):
                raise IncompleteEvidence()
            status = run.get("status")
            if status not in (
                    "completed", "queued", "in_progress",
                    "pending", "requested", "waiting"):
                raise IncompleteEvidence()
            if status != "completed":
                running = True

        verify = get(path)
        if (not isinstance(verify, dict)
                or any(verify.get(k) != issue.get(k)
                       for k in ("state", "number", "comments", "updated_at", "labels", "assignees"))
                or branch_sha() != sha):
            raise IncompleteEvidence()
        # GitHub puede lanzar/rerun CI sin cambiar Issue ni ref.
        # La segunda lectura descarta snapshots con runs/checks cambiantes.
        checked_again = pages(
            f"{base}/commits/{sha}/check-runs",
            name="checks_recheck", checks=True,
        )
        runs_again = pages(
            f"{base}/actions/runs?branch={quote(branch, safe='')}",
            name="runs_recheck", runs=True,
        )
        if checked_again != checks or runs_again != workflow_runs:
            raise IncompleteEvidence()
        effective_remaining = remaining - used
        if effective_remaining < 0 or effective_remaining * 5 < limit:
            raise IncompleteEvidence()
        return {
            "status": state_labels[0], "evidence_complete": True,
            "repo": repo, "repository_id": repo_id, "issue_number": issue_number,
            "owner": owner, "lease_id": lease["reservation_id"],
            "branch": branch, "branch_sha": sha, "pagination": pagination,
            "last_activity_at": latest.isoformat().replace("+00:00", "Z"),
            "ci_running": running, "rate_limit": limit,
            "rate_remaining": effective_remaining, "api_requests": used,
        }
    except Exception:
        # No incluir tokens, rutas remotas ni payload privado en diagnósticos.
        return unknown
