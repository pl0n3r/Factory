#!/usr/bin/env python3
"""Entrega diaria GitHub-native del resumen 4C para el dueño de Factory."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from scripts.unattended_kill_switch import evaluate_unattended_kill_switch
from scripts.unattended_watchdog import DailySummary, WatchdogDecision
from scripts.unattended_watchdog_runtime import (
    CANONICAL_REPOSITORY,
    GitHubIssueClient,
    RuntimeValidationError,
    collect_github_input,
    evaluate_runtime,
    load_config,
)

SUMMARY_ISSUE = 768
BOGOTA = ZoneInfo("America/Bogota")
MARKER_START_RE = re.compile(r"<!--\s*factory-unattended-daily-summary")
MARKER_RE = re.compile(
    r"<!--\s*factory-unattended-daily-summary\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
NIGHT_MARKER_START_RE = re.compile(r"<!--\s*factory-unattended-night-report")
NIGHT_MARKER_RE = re.compile(
    r"<!--\s*factory-unattended-night-report\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
MAX_CONTEXT_PAGES = 5
DECISION_LABELS = frozenset({"decisión: dueño", "decision: owner"})
BLOCKED_LABELS = frozenset({"estado: bloqueado", "status: blocked"})
COMPLETED_LABELS = frozenset({"estado: completado", "status: completed"})
ACTIONS_BOT_LOGIN = "github-actions[bot]"
CONDOR_D043_COMMENTS_URL = "https://api.github.com/repos/pl0n3r/Condor/issues/1/comments"
CONDOR_D043_SOURCE = "Condor#1 public GitHub"
CONDOR_D043_USER_AGENT = "Factory-unattended-daily-summary/1"
CONDOR_D043_TIMEOUT_SECONDS = 3
MAX_CONDOR_D043_PAGES = 3
CONDOR_D043_MARKER_START_RE = re.compile(r"<!--\s*condor-d043-validation-card")
CONDOR_D043_MARKER_RE = re.compile(
    r'<!--\s*condor-d043-validation-card\s+(\{[^}]*\})\s*-->',
    re.DOTALL,
)
CONDOR_D043_VISIBLE_VERSION_RE = re.compile(
    r"^- Versión:\s*\x60V(\d+\.\d+\.\d+)\x60\s*$",
    re.MULTILINE,
)
CONDOR_D043_VISIBLE_SHA_RE = re.compile(
    r"^- SHA exacto:\s*\x60([0-9a-f]{40})\x60\s*$",
    re.MULTILINE,
)
CONDOR_D043_VALIDATED_RE = re.compile(
    r"^✅ VALIDATED_IN_PRODUCTION automático:\s*producción sirve V\s*"
    r"(\d+\.\d+\.\d+)\s*\(([0-9a-f]{40})\)(?:\s|$)",
    re.MULTILINE,
)


class DailySummaryError(ValueError):
    """La entrega diaria no puede continuar de forma segura."""


@dataclass(frozen=True)
class Fact:
    text: str
    source: str
    age_minutes: int | None
    freshness: str


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DailySummaryError("duplicate_json_key")
        result[key] = value
    return result


def _marker(local_date: str) -> str:
    payload = json.dumps(
        {"local_date": local_date, "version": 1},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"<!-- factory-unattended-daily-summary {payload} -->"


def _night_marker(local_date: str) -> str:
    payload = json.dumps(
        {"local_date": local_date, "version": 1},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"<!-- factory-unattended-night-report {payload} -->"


def _parse_owned_marker(
    comment: object,
    *,
    start_re: re.Pattern[str],
    marker_re: re.Pattern[str],
    ambiguous_reason: str,
    invalid_reason: str,
) -> str | None:
    if not isinstance(comment, dict):
        return None
    user = comment.get("user")
    body = comment.get("body")
    if (
        not isinstance(user, dict)
        or user.get("login") != ACTIONS_BOT_LOGIN
        or not isinstance(body, str)
    ):
        return None
    starts = start_re.findall(body)
    if not starts:
        return None
    markers = marker_re.findall(body)
    if len(starts) != 1 or len(markers) != 1:
        raise DailySummaryError(ambiguous_reason)
    try:
        payload = json.loads(markers[0], object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, DailySummaryError) as exc:
        raise DailySummaryError(invalid_reason) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"local_date", "version"}
        or type(payload["version"]) is not int
        or payload["version"] != 1
        or not isinstance(payload["local_date"], str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", payload["local_date"]) is None
    ):
        raise DailySummaryError(invalid_reason)
    return payload["local_date"]


def parse_night_marker(comment: object) -> str | None:
    return _parse_owned_marker(
        comment,
        start_re=NIGHT_MARKER_START_RE,
        marker_re=NIGHT_MARKER_RE,
        ambiguous_reason="ambiguous_night_report_marker",
        invalid_reason="invalid_night_report_marker",
    )


def parse_daily_marker(comment: object) -> str | None:
    return _parse_owned_marker(
        comment,
        start_re=MARKER_START_RE,
        marker_re=MARKER_RE,
        ambiguous_reason="ambiguous_daily_summary_marker",
        invalid_reason="invalid_daily_summary_marker",
    )


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _age_minutes(now: datetime, observed_at: object) -> int | None:
    observed = _parse_time(observed_at)
    if observed is None:
        return None
    seconds = (now - observed).total_seconds()
    if seconds < 0:
        return None
    return int(seconds // 60)


def _condor_version_key(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise DailySummaryError("condor_d043_version_invalid")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _parse_condor_d043_card(comment: object) -> tuple[str, str, object] | None:
    if not isinstance(comment, dict):
        return None
    user = comment.get("user")
    body = comment.get("body")
    if (
        not isinstance(user, dict)
        or user.get("login") != ACTIONS_BOT_LOGIN
        or not isinstance(body, str)
    ):
        return None
    starts = CONDOR_D043_MARKER_START_RE.findall(body)
    if not starts:
        return None
    markers = CONDOR_D043_MARKER_RE.findall(body)
    if len(starts) != 1 or len(markers) != 1:
        raise DailySummaryError("condor_d043_card_ambiguous")
    try:
        payload = json.loads(markers[0], object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, DailySummaryError) as exc:
        raise DailySummaryError("condor_d043_card_invalid") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"sha", "version"}
        or payload.get("version") != 1
        or not isinstance(payload.get("sha"), str)
        or re.fullmatch(r"[0-9a-f]{40}", payload["sha"]) is None
    ):
        raise DailySummaryError("condor_d043_card_invalid")

    versions = CONDOR_D043_VISIBLE_VERSION_RE.findall(body)
    shas = CONDOR_D043_VISIBLE_SHA_RE.findall(body)
    if len(versions) != 1 or len(shas) != 1 or shas[0] != payload["sha"]:
        raise DailySummaryError("condor_d043_card_identity_mismatch")
    version = versions[0]
    command_prefix = (
        "gh workflow run observar-release.yml --repo pl0n3r/Condor "
        f"-f version={version} -f sha={payload['sha']}"
    )
    if body.count(command_prefix) != 1:
        raise DailySummaryError("condor_d043_card_command_mismatch")
    _condor_version_key(version)
    return version, payload["sha"], comment.get("created_at")


def _parse_condor_d043_validation(comment: object) -> tuple[str, str] | None:
    if not isinstance(comment, dict):
        return None
    user = comment.get("user")
    body = comment.get("body")
    if (
        not isinstance(user, dict)
        or user.get("login") != ACTIONS_BOT_LOGIN
        or not isinstance(body, str)
    ):
        return None
    matches = CONDOR_D043_VALIDATED_RE.findall(body)
    if not matches:
        return None
    if len(matches) != 1:
        raise DailySummaryError("condor_d043_validation_ambiguous")
    version, sha = matches[0]
    _condor_version_key(version)
    return version, sha


def _public_condor_comments(opener=None) -> list[dict[str, object]]:
    open_url = urlopen if opener is None else opener
    comments: list[dict[str, object]] = []
    for page in range(1, MAX_CONDOR_D043_PAGES + 1):
        url = f"{CONDOR_D043_COMMENTS_URL}?{urlencode({'per_page': 100, 'page': page})}"
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": CONDOR_D043_USER_AGENT,
            },
            method="GET",
        )
        try:
            with open_url(request, timeout=CONDOR_D043_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            raise DailySummaryError("condor_d043_public_api_unavailable") from exc
        if not isinstance(payload, list):
            raise DailySummaryError("condor_d043_public_api_invalid")
        if any(not isinstance(item, dict) for item in payload):
            raise DailySummaryError("condor_d043_public_api_invalid")
        comments.extend(payload)
        if len(payload) < 100:
            return comments
    raise DailySummaryError("condor_d043_public_api_truncated")


def collect_condor_d043_gate(now: datetime, *, opener=None) -> Fact:
    try:
        comments = _public_condor_comments(opener=opener)
        cards: dict[tuple[str, str], object] = {}
        validations: set[tuple[str, str]] = set()
        for comment in comments:
            card = _parse_condor_d043_card(comment)
            if card is not None:
                version, sha, created_at = card
                cards[(version, sha)] = created_at
            validated = _parse_condor_d043_validation(comment)
            if validated is not None:
                validations.add(validated)

        pending = [
            (version, sha, created_at)
            for (version, sha), created_at in cards.items()
            if (version, sha) not in validations
        ]
        if not pending:
            return Fact(
                text="Condor D-043: ninguna tarjeta pendiente demostrada.",
                source=CONDOR_D043_SOURCE,
                age_minutes=0,
                freshness="fresh",
            )

        pending.sort(key=lambda item: (_condor_version_key(item[0]), item[1]))
        version, _sha, created_at = pending[-1]
        age = _age_minutes(now, created_at)
        older = len(pending) - 1
        suffix = f" (+{older} anteriores pendientes)" if older else ""
        freshness = "unknown"
        if age is not None:
            freshness = "fresh" if age < 1440 else "stale"
        return Fact(
            text=f"Condor V{version} espera tu validación D-043{suffix}",
            source=CONDOR_D043_SOURCE,
            age_minutes=age,
            freshness=freshness,
        )
    except (TypeError, ValueError, KeyError):
        return Fact(
            text="UNKNOWN: puerta D-043 de Condor no verificable.",
            source=CONDOR_D043_SOURCE,
            age_minutes=None,
            freshness="stale",
        )


def _labels(issue: dict[str, object]) -> set[str]:
    raw = issue.get("labels")
    if not isinstance(raw, list):
        return set()
    return {
        label["name"]
        for label in raw
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    }


def _fact_from_issue(issue: dict[str, object], now: datetime) -> Fact | None:
    number = issue.get("number")
    title = issue.get("title")
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or not isinstance(title, str)
        or not title.strip()
    ):
        return None
    age = _age_minutes(now, issue.get("updated_at"))
    return Fact(
        text=f"#{number} {title.strip()}",
        source="GitHub Issues",
        age_minutes=age,
        freshness=(
            "unknown"
            if age is None
            else ("fresh" if age < 1440 else "stale")
        ),
    )


def _decision_options(body: object) -> tuple[str, str]:
    if not isinstance(body, str):
        return "UNKNOWN", "UNKNOWN"
    prefix = "<!-- factory-human-gate "
    if body.count(prefix) != 1:
        return "UNKNOWN", "UNKNOWN"
    start = body.index(prefix) + len(prefix)
    end = body.find(" -->", start)
    if end < 0:
        return "UNKNOWN", "UNKNOWN"
    try:
        payload = json.loads(body[start:end], object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, DailySummaryError):
        return "UNKNOWN", "UNKNOWN"
    if not isinstance(payload, dict):
        return "UNKNOWN", "UNKNOWN"
    recommendation = payload.get("recommendation")
    safe_default = payload.get("safe_default")
    return (
        recommendation if isinstance(recommendation, str) else "UNKNOWN",
        safe_default if isinstance(safe_default, str) else "UNKNOWN",
    )


def _list_issues(
    client: GitHubIssueClient,
    *,
    state: str,
    since: str | None = None,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for page in range(1, MAX_CONTEXT_PAGES + 1):
        query_data: dict[str, object] = {
            "state": state,
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }
        if since is not None:
            query_data["since"] = since
        payload = client._request(
            "GET",
            f"/repos/pl0n3r/Factory/issues?{urlencode(query_data)}",
        )
        if not isinstance(payload, list):
            raise DailySummaryError("github_issues_invalid")
        rows = [
            issue
            for issue in payload
            if isinstance(issue, dict) and "pull_request" not in issue
        ]
        result.extend(rows)
        if len(payload) < 100:
            return result
    raise DailySummaryError("github_issue_context_truncated")


def collect_issue_context(
    client: GitHubIssueClient,
    now: datetime,
) -> dict[str, tuple[Fact, ...]]:
    open_issues = _list_issues(client, state="open")
    since_dt = now - timedelta(hours=24)
    since = since_dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    closed_issues = _list_issues(client, state="closed", since=since)

    decisions: list[Fact] = []
    blockers: list[Fact] = []
    advances: list[Fact] = []
    for issue in open_issues:
        fact = _fact_from_issue(issue, now)
        if fact is None:
            continue
        names = _labels(issue)
        if names & DECISION_LABELS:
            recommendation, safe_default = _decision_options(issue.get("body"))
            decisions.append(Fact(
                text=(
                    f"{fact.text} · recomendación={recommendation} "
                    f"· seguro={safe_default}"
                ),
                source=fact.source,
                age_minutes=fact.age_minutes,
                freshness=fact.freshness,
            ))
        if names & BLOCKED_LABELS:
            blockers.append(Fact(
                text=f"causa: {fact.text}",
                source=fact.source,
                age_minutes=fact.age_minutes,
                freshness=fact.freshness,
            ))
    for issue in closed_issues:
        if not (_labels(issue) & COMPLETED_LABELS):
            continue
        closed_at = _parse_time(issue.get("closed_at"))
        if closed_at is None or closed_at < since_dt:
            continue
        fact = _fact_from_issue(issue, now)
        if fact is not None:
            advances.append(fact)

    key = lambda item: item.text
    return {
        "decisions": tuple(sorted(decisions, key=key)),
        "blockers": tuple(sorted(blockers, key=key)),
        "advances": tuple(sorted(advances, key=key)),
    }


def _state_source(runtime_input: object, decision: WatchdogDecision, now: datetime) -> Fact:
    evidence = runtime_input.get("evidence") if isinstance(runtime_input, dict) else None
    state = evidence.get("state") if isinstance(evidence, dict) else None
    presence = evidence.get("presence") if isinstance(evidence, dict) else None
    updated_at = state.get("updated_at") if isinstance(state, dict) else None
    source = presence.get("source") if isinstance(presence, dict) else None
    age = _age_minutes(now, updated_at)
    return Fact(
        text="STATE/Presence",
        source=source if isinstance(source, str) and source else "4C:UNKNOWN",
        age_minutes=age,
        freshness=decision.daily_summary.state_freshness,
    )


def _fact_suffix(fact: Fact) -> str:
    age = "UNKNOWN" if fact.age_minutes is None else f"{fact.age_minutes}m"
    return f"source={fact.source} · age={age} · {fact.freshness}"


def _render_facts(items: Iterable[Fact], empty: str) -> str:
    rows = tuple(items)
    if not rows:
        return f"- {empty}"
    return "\n".join(f"- {item.text} — {_fact_suffix(item)}" for item in rows)


def immediate_incidents(incidents: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            item
            for item in incidents
            if isinstance(item, str) and (item.startswith("S1:") or item.startswith("S2:"))
        )
    )


def render_summary(
    decision: WatchdogDecision,
    runtime_input: object,
    issue_context: dict[str, tuple[Fact, ...]],
    now: datetime,
) -> str:
    local_date = now.astimezone(BOGOTA).date().isoformat()
    summary: DailySummary = decision.daily_summary
    source_fact = _state_source(runtime_input, decision, now)

    state_age = source_fact.age_minutes
    four_c_facts = lambda values: tuple(
        Fact(str(value), "4C daily_summary", state_age, summary.state_freshness)
        for value in values
    )

    condor_gate = tuple(issue_context.get("condor_d043", ()))
    decisions = tuple(issue_context.get("decisions", ())) + four_c_facts(summary.human_gates)
    blockers = tuple(issue_context.get("blockers", ())) + four_c_facts(summary.blockers)
    advances = tuple(issue_context.get("advances", ())) + four_c_facts(summary.integrated)
    if not advances:
        advances = four_c_facts(summary.active_fronts)

    incidents = four_c_facts(summary.incidents)
    immediate = immediate_incidents(summary.incidents)
    next_actions = four_c_facts(summary.next_actions)

    quota_facts = (
        Fact("CI: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
        Fact("GitHub API: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
        Fact("Cuentas ChatGPT: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
    )

    immediate_text = (
        "\n".join(f"- {item}" for item in immediate)
        if immediate
        else "- Ninguna. Solo S1/S2 interrumpen fuera de este resumen."
    )

    return (
        f"{_marker(local_date)}\n"
        f"## Resumen diario Factory · {local_date}\n\n"
        "### Puerta D-043 Condor\n"
        f"{_render_facts(condor_gate, 'UNKNOWN: puerta D-043 de Condor no observada.')}\n\n"
        "### Decisiones pendientes\n"
        f"{_render_facts(decisions, 'Ninguna demostrada.')}\n\n"
        "### Bloqueos\n"
        f"{_render_facts(blockers, 'Ninguno demostrado.')}\n\n"
        "### Avances\n"
        f"{_render_facts(advances, 'UNKNOWN: no hay avance demostrable en la evidencia disponible.')}\n\n"
        "### Alertas\n"
        f"{_render_facts(incidents, 'Ninguna incidencia demostrada.')}\n\n"
        "Alerta inmediata aparte:\n"
        f"{immediate_text}\n\n"
        "### Próximas acciones\n"
        f"{_render_facts(next_actions, 'UNKNOWN.')}\n\n"
        "### Cuotas\n"
        f"{_render_facts(quota_facts, 'UNKNOWN.')}\n\n"
        "### Fuente principal\n"
        f"- {source_fact.text} — {_fact_suffix(source_fact)}\n\n"
        f"Acción 4C: **{decision.action}** · autoridad: **{decision.authority}**. "
        "Los valores UNKNOWN/STALE se muestran como tales y no se completan por inferencia.\n"
    )


def render_night_report(
    decision: WatchdogDecision,
    issue_context: dict[str, tuple[Fact, ...]],
    now: datetime,
) -> str:
    """Resumen idempotente de la noche; no sustituye el resumen diario 4C."""

    local_date = now.astimezone(BOGOTA).date().isoformat()
    summary = decision.daily_summary
    advances = tuple(issue_context.get("advances", ()))
    if not advances:
        advances = tuple(
            Fact(str(value), "4C night_report", None, summary.state_freshness)
            for value in summary.integrated
        )
    decisions = tuple(issue_context.get("decisions", ()))
    blockers = tuple(issue_context.get("blockers", ()))
    incidents = tuple(
        Fact(str(value), "4C night_report", None, summary.state_freshness)
        for value in summary.incidents
    )
    quota_facts = (
        Fact("CI: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
        Fact("GitHub API: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
        Fact("Cuentas ChatGPT: UNKNOWN", "Factory#584:not-observed", None, "unknown"),
    )
    return (
        f"{_night_marker(local_date)}\n"
        f"## Informe de la noche Factory · {local_date}\n\n"
        "### Fusiones y avances\n"
        f"{_render_facts(advances, 'UNKNOWN: no hay avance nocturno demostrable.')}\n\n"
        "### PRs o puertas esperando al dueño\n"
        f"{_render_facts(decisions, 'Ninguno demostrado.')}\n\n"
        "### Bloqueos\n"
        f"{_render_facts(blockers, 'Ninguno demostrado.')}\n\n"
        "### Incidentes\n"
        f"{_render_facts(incidents, 'Ninguno demostrado.')}\n\n"
        "### Cuotas\n"
        f"{_render_facts(quota_facts, 'UNKNOWN.')}\n"
    )


def publish_night_report_once(
    client: GitHubIssueClient,
    *,
    local_date: str,
    body: str,
) -> bool:
    seen: set[str] = set()
    for comment in client.list_issue_comments(SUMMARY_ISSUE):
        parsed = parse_night_marker(comment)
        if parsed is not None:
            seen.add(parsed)
    if local_date in seen:
        return False
    client._request(
        "POST",
        f"/repos/pl0n3r/Factory/issues/{SUMMARY_ISSUE}/comments",
        {"body": body},
    )
    return True


def publish_once(
    client: GitHubIssueClient,
    *,
    local_date: str,
    body: str,
) -> bool:
    seen: set[str] = set()
    for comment in client.list_issue_comments(SUMMARY_ISSUE):
        parsed = parse_daily_marker(comment)
        if parsed is not None:
            seen.add(parsed)
    if local_date in seen:
        return False
    client._request(
        "POST",
        f"/repos/pl0n3r/Factory/issues/{SUMMARY_ISSUE}/comments",
        {"body": body},
    )
    return True


def main() -> int:
    token = os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    now = datetime.now(timezone.utc)
    local_date = now.astimezone(BOGOTA).date().isoformat()
    try:
        client = GitHubIssueClient(token, repository)
        config = load_config()
        open_alerts = client.list_owned_alerts()
        now_text = now.isoformat(timespec="seconds").replace("+00:00", "Z")
        runtime_input = collect_github_input(client, config, now_text)
        decision, _ = evaluate_runtime(
            config,
            runtime_input.get("guard"),
            runtime_input.get("evidence"),
            open_alerts,
        )
        context = collect_issue_context(client, now)
        context["condor_d043"] = (collect_condor_d043_gate(now),)
        body = render_summary(decision, runtime_input, context, now)
        night_body = render_night_report(decision, context, now)

        switch = evaluate_unattended_kill_switch(client.get_issue(767))
        if switch.global_pause:
            print(json.dumps({"published": False, "reason": f"kill_switch:{switch.reason}"}, sort_keys=True))
            return 1
        night_published = publish_night_report_once(
            client,
            local_date=local_date,
            body=night_body,
        )
        published = publish_once(client, local_date=local_date, body=body)
        print(
            json.dumps(
                {
                    "local_date": local_date,
                    "night_published": night_published,
                    "published": published,
                },
                sort_keys=True,
            )
        )
        return 0
    except (DailySummaryError, RuntimeValidationError, TypeError, ValueError, KeyError) as exc:
        print(json.dumps({"published": False, "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
