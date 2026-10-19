"""Ensamblaje de diagnóstico V3: colector autenticado -> Snapshot -> decisor.

No implementa un escritor ni certifica ausencia de actividad. El decisor
existente y el executor conservan todas sus puertas. Hasta que exista una
fuente integral de inactividad, esta superficie solo ofrece un preview
fail-closed, sin credenciales ni transporte de escritura propios.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from scripts.lease_activity_collector import collect_activity
from scripts.lease_auto_release import Decision
from scripts.lease_auto_release_run import decision_from_snapshot
from scripts.lease_release_executor import Snapshot, _trusted

UTC_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
ACTIVE = frozenset({"estado: reservado", "estado: en revisión",
                    "estado: requiere recuperación"})
FACTORY_REPO_ROUTE = "/repos/pl0n3r/Factory"


def _allowed_unparameterized_get(route: str) -> bool:
    """Only endpoints needed for the V3 GET observer, not all repo resources."""
    if route in (
        "/rate_limit", FACTORY_REPO_ROUTE,
        FACTORY_REPO_ROUTE + "/issues/767",
        FACTORY_REPO_ROUTE + "/contents/datos.yml",
    ):
        return True
    base = re.escape(FACTORY_REPO_ROUTE)
    return (
        re.fullmatch(rf"{base}/issues/[1-9][0-9]*", route) is not None
        or re.fullmatch(
            rf"{base}/git/ref/heads/trabajo/issue-[1-9][0-9]*", route
        ) is not None
    )


@dataclass(frozen=True)
class IntegrationPreview:
    """No lleva UUID/SHA ni permite elevar resultados a autorización."""
    issue: int
    state: str
    action: str
    reason: str
    activity_age_minutes: int | None = None
    activity_source: str | None = None

    @property
    def summary_line(self) -> str:
        """Resumir sólo datos tipados; jamás imprimir comentarios o identidades."""
        issue = self.issue if type(self.issue) is int and self.issue > 0 else 0
        action = (self.action if self.action in
                  ("wait", "mark_recovery", "release", "unknown") else "unknown")
        reason = (self.reason if type(self.reason) is str
                  and re.fullmatch(r"[a-z0-9_]{1,96}", self.reason)
                  else "untrusted_reason")
        minutes = (str(self.activity_age_minutes)
                   if type(self.activity_age_minutes) is int
                   and 0 <= self.activity_age_minutes <= 525600
                   else "UNKNOWN")
        source = (self.activity_source
                  if self.activity_source in ("reservation_marker", "workflow_push")
                  else "UNKNOWN")
        # Sólo acredita el marker del bot o un workflow push exact-SHA;
        # no inferir actividad del titular por login compartido ni por
        # reviews/checks sin testigo temporal autenticado.
        return (f"- Issue #{issue}: `{action}`; inactividad={minutes} min; "
                f"fuente={source}; veto/razón={reason}; autoridad=NO.\n")

    @property
    def release_authorized(self) -> bool:
        return False

    @property
    def lock_verified(self) -> bool:
        """El preview no demuestra posesión de exclusión distribuida."""
        return False

    @property
    def cas_verified(self) -> bool:
        """El preview no demuestra CAS atómico sobre metadata de Issues."""
        return False


def _unknown(issue: int, reason: str) -> IntegrationPreview:
    return IntegrationPreview(issue, "UNKNOWN", "unknown", reason)


class _GhReadOnlyAPI:
    """Puente GH CLI autenticado con allowlist estricta de GET; nunca muta."""
    repo = "pl0n3r/Factory"
    authenticated = True

    def request(self, method: str, path: str) -> Any:
        import json
        import re
        import subprocess

        # La ruta y la query son superficies distintas: solo los valores de
        # query pueden usar escapes canónicos (%2F para rama, %3A para UTC).
        route, sep, query = path.partition("?") if type(path) is str else ("", "", "")
        if (method != "GET" or type(path) is not str
                or not (route == "/rate_limit"
                        or route == FACTORY_REPO_ROUTE
                        or route.startswith(FACTORY_REPO_ROUTE + "/"))
                or (not sep and not _allowed_unparameterized_get(route))
                or "://" in path or "#" in path or ".." in path
                or "%" in route or "\\" in path
                or any(ord(ch) < 32 for ch in path)
                or re.search(r"[\s;|$<>]", path)):
            raise PermissionError("read_only_transport")
        if sep:
            from urllib.parse import quote, unquote

            repo = FACTORY_REPO_ROUTE
            if route == f"{repo}/commits":
                allowed = {"sha", "since", "per_page", "page"}
            elif route == f"{repo}/actions/runs":
                allowed = {"branch", "per_page", "page"}
            elif route == f"{repo}/pulls":
                allowed = {"state", "head", "per_page", "page"}
            elif re.fullmatch(
                    rf"{re.escape(repo)}/issues/[1-9][0-9]*/events", route):
                allowed = {"per_page", "page"}
            elif re.fullmatch(
                    rf"{re.escape(repo)}/(?:issues/[1-9][0-9]*/comments"
                    rf"|pulls/[1-9][0-9]*/reviews"
                    rf"|commits/[a-f0-9]{{40}}/check-runs)", route):
                allowed = {"per_page", "page"}
            else:
                raise PermissionError("read_only_transport")
            parts = query.split("&")
            seen = set()
            if not query or len(query) > 512 or len(parts) > 4:
                raise PermissionError("read_only_transport")
            for part in parts:
                key, equal, value = part.partition("=")
                decoded = unquote(value)
                if (equal != "=" or key not in allowed or key in seen
                        or not decoded.isascii() or "%" in decoded
                        or quote(decoded, safe="") != value):
                    raise PermissionError("read_only_transport")
                seen.add(key)
                if key in ("sha", "branch") and not re.fullmatch(
                        r"(?:main|trabajo/issue-[1-9][0-9]*)", decoded):
                    raise PermissionError("read_only_transport")
                if key == "head" and not re.fullmatch(
                        r"pl0n3r:(?:main|trabajo/issue-[1-9][0-9]*)", decoded):
                    raise PermissionError("read_only_transport")
                if key == "since" and not UTC_STAMP.fullmatch(decoded):
                    raise PermissionError("read_only_transport")
                if key == "state" and decoded != "open":
                    raise PermissionError("read_only_transport")
                if key == "per_page" and decoded != "100":
                    raise PermissionError("read_only_transport")
                if key == "page" and not re.fullmatch(r"(?:[1-9]|10)", decoded):
                    raise PermissionError("read_only_transport")
        try:
            result = subprocess.run(
                ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                check=True, capture_output=True, text=True, timeout=20,
            )
            return json.loads(result.stdout)
        except Exception:
            # No propagar stderr, URL ni fragmentos de payload a logs.
            raise RuntimeError("authenticated_get_failed") from None


def observe_issue_cli(issue: int) -> IntegrationPreview:
    """Ejecuta solo lecturas reales. UNKNOWN es un resultado válido y seguro."""
    import os
    from datetime import datetime, timezone
    from scripts.lease_github_port import LeaseGithubPort

    if os.environ.get("GITHUB_REPOSITORY") != _GhReadOnlyAPI.repo:
        return _unknown(issue if type(issue) is int and issue > 0 else 0,
                        "repository_not_authorized")
    api = _GhReadOnlyAPI()
    now = datetime.now(timezone.utc)
    try:
        identity = api.request("GET", FACTORY_REPO_ROUTE)
        repository_id = identity.get("id") if type(identity) is dict else None
        if (type(repository_id) is not int or repository_id <= 0
                or identity.get("full_name") != _GhReadOnlyAPI.repo):
            return _unknown(issue if type(issue) is int and issue > 0 else 0,
                            "repository_identity_unknown")
    except Exception:
        return _unknown(issue if type(issue) is int and issue > 0 else 0,
                        "repository_identity_unknown")
    # Mantener el grupo canónico sin armar el Port: aun si cambia
    # accidentalmente el transporte GET-only, no hay permiso de mutación.
    try:
        port = LeaseGithubPort(
            api, armed=False,
            concurrency_group=f"factory-coordination-{repository_id}",
            clock=lambda: now,
        )
        return preview_integrated_activity(api, port, issue, now=now)
    except Exception:
        # El adaptador read-only devuelve UNKNOWN aun si Port o preview
        # rompe su contrato. No exponer URL, payload ni secretos al caller.
        return _unknown(issue if type(issue) is int and issue > 0 else 0,
                        "observer_failed")



def _verified_review_veto(api: Any, snapshot: Snapshot, now: datetime,
                          remaining: int, limit: int) -> bool | None:
    """Prueba REST read-only de reviews vigentes en PR local exact-SHA.

    True: CHANGES_REQUESTED sigue vigente. False: inventario íntegro sin
    bloqueo actual. None: identidad/páginas/estado/cuota/carrera desconocidos.
    Ningún resultado de esta función prueba ausencia de pushes.
    """
    try:
        repo = getattr(api, "repo", None)
        if (type(repo) is not str
                or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None
                or type(remaining) is not int or type(limit) is not int
                or limit <= 0 or remaining < 0 or remaining > limit):
            return None
        used = 0

        def get(path: str) -> Any:
            nonlocal used
            used += 1
            if used > 16 or (remaining - used) * 5 < limit:
                raise ValueError("review_budget")
            return api.request("GET", path)

        def pages(path: str) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            seen: set[int] = set()
            for index in range(1, 5):
                joiner = "&" if "?" in path else "?"
                items = get(f"{path}{joiner}per_page=100&page={index}")
                if type(items) is not list or len(items) > 100:
                    raise ValueError("invalid_page")
                for item in items:
                    number = item.get("id") if type(item) is dict else None
                    if type(number) is not int or number <= 0 or number in seen:
                        raise ValueError("duplicate_or_invalid_id")
                    seen.add(number)
                    rows.append(item)
                if len(items) < 100:
                    sentinel = get(
                        f"{path}{joiner}per_page=100&page={index + 1}"
                    )
                    if type(sentinel) is not list or sentinel:
                        raise ValueError("truncated_page")
                    return rows
            raise ValueError("page_cap")

        branch = snapshot.branch
        pulls_path = f"/repos/{repo}/pulls?state=open"
        def current_pull() -> dict[str, Any] | None:
            matches: list[dict[str, Any]] = []
            for pull in pages(pulls_path):
                head = pull.get("head")
                if type(head) is not dict or head.get("ref") != branch:
                    continue
                origin = head.get("repo")
                if type(origin) is not dict:
                    raise ValueError("unknown_head_origin")
                origin_name, origin_id = (
                    origin.get("full_name"), origin.get("id"),
                )
                if (type(origin_name) is not str
                        or re.fullmatch(
                            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
                            origin_name,
                        ) is None
                        or type(origin_id) is not int or origin_id <= 0):
                    raise ValueError("unknown_head_origin")
                if origin_name != repo:
                    if origin_id == snapshot.repository_id:
                        raise ValueError("mismatched_repo")
                    continue
                # Asociar review al PR que cierra ESTE Issue y declara
                # exactamente la sesión V3 vigente. Compartir head.ref y
                # SHA no basta para atribuir reviews a la lease.
                body = pull.get("body")
                if type(body) is not str:
                    raise ValueError("pr_contract_missing")
                target = re.findall(
                    r"(?im)^\s*(?:Closes|Fixes|Resolves)\s+#(\d+)\b",
                    body,
                )
                reservations = re.findall(
                    r"<!--\s*condor-reserva-id:\s*"
                    r"([0-9a-fA-F-]{36})\s*-->",
                    body,
                )
                if (len(target) != 1 or type(snapshot.issue) is not int
                        or int(target[0]) != snapshot.issue
                        or len(reservations) != 1
                        or reservations[0].lower() != snapshot.reservation_id):
                    raise ValueError("pr_contract_mismatch")
                base = pull.get("base")
                if (origin_id != snapshot.repository_id
                        or head.get("sha") != snapshot.branch_sha
                        or pull.get("state") != "open"
                        or type(base) is not dict
                        or base.get("ref") != "main"
                        or type(pull.get("number")) is not int
                        or pull["number"] <= 0):
                    raise ValueError("untrusted_canonical_pr")
                matches.append(pull)
            if len(matches) > 1:
                raise ValueError("ambiguous_canonical_pr")
            if not matches:
                if snapshot.status == "estado: en revisión":
                    raise ValueError("missing_review_pr")
                return None
            return matches[0]

        def current_reviews(pull: dict[str, Any] | None) -> tuple[bool, list[dict[str, Any]]]:
            if pull is None:
                return False, []
            reviews = pages(
                f"/repos/{repo}/pulls/{pull['number']}/reviews"
            )
            # GitHub diferencia ID de creación y fecha de envío. Un
            # APPROVED con ID mayor pero enviado antes NO levanta el veto.
            latest: dict[str, tuple[datetime, str]] = {}
            highest_id = 0
            for review in reviews:
                author = review.get("user")
                state = review.get("state")
                timestamp = review.get("submitted_at")
                if (type(author) is not dict
                        or type(author.get("login")) is not str
                        or not author["login"]
                        or state not in (
                            "PENDING", "COMMENTED", "APPROVED",
                            "DISMISSED", "CHANGES_REQUESTED",
                        )
                        # bool y float son comparables con enteros en Python:
                        # solo un ID REST int estricto autentica la secuencia.
                        or type(review.get("id")) is not int
                        or review["id"] <= highest_id):
                    raise ValueError("unknown_review_state")
                highest_id = review["id"]
                if state != "PENDING":
                    if type(timestamp) is not str or not UTC_STAMP.fullmatch(timestamp):
                        raise ValueError("review_timestamp")
                    stamp = datetime.fromisoformat(
                        timestamp.replace("Z", "+00:00")
                    )
                    if stamp > now.astimezone(timezone.utc):
                        raise ValueError("future_review")
                    # COMMENTED y DISMISSED son neutros para OTRAS
                    # reviews: GitHub actualiza la revisión original si
                    # realmente se descartó. Usar submitted_at, nunca ID,
                    # para decidir el orden entre veto y aprobación.
                    if state in ("CHANGES_REQUESTED", "APPROVED"):
                        previous = latest.get(author["login"])
                        if (previous is not None and stamp == previous[0]
                                and state != previous[1]):
                            raise ValueError("ambiguous_review_submission")
                        if previous is None or stamp > previous[0]:
                            latest[author["login"]] = (stamp, state)
            return any(
                state == "CHANGES_REQUESTED"
                for _, state in latest.values()
            ), reviews

        before = current_pull()
        veto, reviews = current_reviews(before)
        # Cerrar ventanas de cambios de review/PR sin confiar en un
        # updated_at de resolución de segundos ni en una sola paginación.
        after = current_pull()
        after_veto, after_reviews = current_reviews(after)
        if before != after or reviews != after_reviews or veto != after_veto:
            return None
        return veto
    except Exception:
        return None


def preview_integrated_activity(api: Any, port: Any, issue: Any,
                                *, now: Any) -> IntegrationPreview:
    """Cruza dos lecturas completas sin inferir inactividad ni escribir.

    collect_activity sólo acredita presencia reciente; una ausencia de push
    no es prueba de inactividad. Port.read autentica adicionalmente #767,
    fase, reviews, cuota y marker V3 en su propia frontera. Exigimos exacta
    coincidencia de las identidades en ambas superficies; el preview jamás
    autoriza mark_recovery, release o transiciones de Coordinación.
    """
    if type(issue) is not int or issue <= 0:
        return _unknown(0, "invalid_issue")
    if type(now) is not datetime or now.tzinfo is None:
        return _unknown(issue, "invalid_clock")
    try:
        if now.utcoffset() is None:
            return _unknown(issue, "invalid_clock")
        observation_reader = getattr(type(port), "read_observation", None)
        report = collect_activity(
            api, issue, now=now,
            allow_ci_veto_only=callable(observation_reader),
        )
        if (type(report) is not dict
                or report.get("evidence_complete") is not True
                or report.get("issue_number") != issue
                or report.get("status") not in ACTIVE
                or type(report.get("ci_running")) is not bool
                or type(report.get("ci_veto_only")) is not bool
                or (report["ci_veto_only"] and (
                    not callable(observation_reader)
                    or report["ci_running"] is not True))
                or type(report.get("last_activity_at")) is not str
                or UTC_STAMP.fullmatch(report["last_activity_at"]) is None
                or report.get("activity_source") not in (
                    "reservation_marker", "workflow_push")):
            return _unknown(issue, "collector_unknown")
        last = datetime.fromisoformat(
            report["last_activity_at"].replace("Z", "+00:00"))
        if last > now.astimezone(timezone.utc):
            return _unknown(issue, "future_activity")
        # La vista de diagnóstico no altera Port.read estricto del executor.
        snapshot = (port.read_observation(issue) if callable(observation_reader)
                    else port.read(issue))
        observation_trusted = (
            type(snapshot) is Snapshot and type(snapshot.ci_running) is bool
            and (_trusted(snapshot) or (callable(observation_reader)
                 and snapshot.ci_running is True
                 and _trusted(replace(snapshot, ci_running=False))))
        )
        if (not observation_trusted or snapshot.marker.get("active") is not True
                or snapshot.issue != issue
                or snapshot.now.astimezone(timezone.utc) != now.astimezone(timezone.utc)
                or report.get("repo") != getattr(api, "repo", None)
                or snapshot.repository_id != report.get("repository_id")
                or snapshot.owner != report.get("owner")
                or snapshot.reservation_id != report.get("lease_id")
                or snapshot.branch != report.get("branch")
                or snapshot.branch_sha != report.get("branch_sha")
                or snapshot.status != report.get("status")
                or snapshot.last_activity_at.astimezone(timezone.utc) != last
                or snapshot.ci_running != report["ci_running"]
                or type(report.get("rate_remaining")) is not int
                or type(report.get("rate_limit")) is not int
                or snapshot.rate_limit != report["rate_limit"]
                or snapshot.rate_remaining > report["rate_remaining"]):
            return _unknown(issue, "inconsistent_authenticated_sources")
        veto = _verified_review_veto(
            api, snapshot, now, min(snapshot.rate_remaining,
                                    report["rate_remaining"]),
            report["rate_limit"],
        )
        if veto is None:
            return _unknown(issue, "review_evidence_unknown")
        if veto or snapshot.changes_requested:
            return _unknown(issue, "changes_requested_veto")
        decision: Decision = decision_from_snapshot(snapshot)
        # Un preview no es autoridad: aunque ambos lectores devuelvan
        # datos positivos, nunca expone una acción que pueda liberar V3.
        if type(decision) is not Decision:
            return _unknown(issue, "invalid_decision")
        if decision.action not in ("unknown", "wait"):
            return _unknown(issue, "inactivity_not_proven")
        age = int((now.astimezone(timezone.utc) - last).total_seconds() // 60)
        if age < 0:
            return _unknown(issue, "future_activity")
        return IntegrationPreview(
            issue, "read_only", decision.action, decision.reason,
            # No atribuir inactividad a un marker antiguo cuando solo
            # tenemos un veto CI autenticado, no una auditoría de pushes.
            age if decision.action == "wait"
            and report["ci_veto_only"] is False else None,
            report["activity_source"] if decision.action == "wait" else None,
        )
    except Exception:
        # Sin nombres de usuario, payloads, headers ni tokens en errores.
        return _unknown(issue, "unverifiable_integration")


if __name__ == "__main__":
    import json
    import sys

    try:
        if len(sys.argv) != 2 or not sys.argv[1].isdecimal():
            raise ValueError("invalid_issue_argument")
        issue_number = int(sys.argv[1])
        result = observe_issue_cli(issue_number)
        print(json.dumps({
            "issue": result.issue,
            "state": result.state,
            "action": result.action,
            "reason": result.reason,
            "activity_age_minutes": result.activity_age_minutes,
            "activity_source": result.activity_source,
            "release_authorized": False,
            "lock_verified": False,
            "cas_verified": False,
            "mutations": 0,
        }, sort_keys=True))
        import os
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as report:
                report.write(result.summary_line)
        # UNKNOWN nunca acredita un ciclo. Las decisiones hipotéticas
        # tipadas son terminales para QA, pero este CLI no ejecuta escrituras.
        if (result.state != "read_only"
                or result.action not in ("wait", "mark_recovery", "release")
                or result.release_authorized or result.lock_verified
                or result.cas_verified):
            raise SystemExit(1)
    except Exception:
        # No registrar excepciones ni datos privados; señalizar fallo real
        # a Actions para impedir que UNKNOWN se confunda con observación OK.
        print(json.dumps({
            "state": "UNKNOWN", "action": "unknown",
            "reason": "observer_failed", "release_authorized": False,
            "lock_verified": False, "cas_verified": False,
            "mutations": 0,
        }, sort_keys=True))
        raise SystemExit(1)
