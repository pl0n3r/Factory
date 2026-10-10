#!/usr/bin/env python3
"""Valida decisiones, rondas y evidencia reviewer-bot anclada al HEAD exacto."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__:
    from scripts.safe_io import SafeIOError, read_repo_text
else:
    from safe_io import SafeIOError, read_repo_text

ID_RE = re.compile(r"^D-[0-9]{3,}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BOT_LOGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,99}(?:\[bot\])?$")
COMMENT_COVERAGE_RE = re.compile(
    r"<!--\s*final_review_risk_coverage:(\{.*?\})\s*-->",
    re.DOTALL,
)
POLICY_FILE = Path("decisiones.yml")
MAX_POLICY_BYTES = 256 * 1024
MAX_REVIEWER_POLICY_BYTES = 4096
MAX_REVIEWS_BYTES = 2_000_000
MAX_COMMENTS_BYTES = 2_000_000
MAX_CHECKS_BYTES = 2_000_000
MAX_THREADS_BYTES = 2_000_000
MAX_TIMELINE_BYTES = 2_000_000
MAX_TIMELINE_EVENTS = 500
MAX_RATE_LIMIT_REPLY_SECONDS = 120
MAX_PHASE_BYTES = 512 * 1024
MAX_EVIDENCE_ITEM_BYTES = 100_000
RATE_LIMIT_TEXTS = ("Review rate limited", "Review limit reached")
POLICY_CHECK_NAME = "Factory policy / Validar decisiones y límite de revisión"
ACCEPTANCE_CHECK_NAME = "acceptance / Criterios de aceptación"
ALLOWED_GATE_CONCLUSIONS = {"success", "neutral", "skipped"}


class PolicyError(ValueError):
    pass


def _validate_run_attempt(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise PolicyError("GITHUB_RUN_ATTEMPT debe ser un entero positivo.")
    return value


def _run_attempt_from_env() -> int:
    raw = os.environ.get("GITHUB_RUN_ATTEMPT")
    if raw is None:
        return 1
    if re.fullmatch(r"[1-9][0-9]*", raw) is None:
        raise PolicyError("GITHUB_RUN_ATTEMPT inválido.")
    return _validate_run_attempt(int(raw))


def _resolve_temp_input(path: Path, *, noun: str) -> Path:
    """Resuelve un input temporal sin permitir escapes ni symlinks."""
    try:
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
        candidate = Path(path)
        if candidate.is_symlink():
            raise PolicyError(f"{noun} no puede ser un enlace simbólico.")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(temp_root)
    except PolicyError:
        raise
    except (OSError, ValueError) as exc:
        raise PolicyError(
            f"{noun} debe pertenecer al directorio temporal."
        ) from exc
    if not resolved.is_file():
        raise PolicyError(f"{noun} debe ser un archivo regular.")
    try:
        if resolved.stat().st_nlink != 1:
            raise PolicyError(f"{noun} no puede tener enlaces adicionales.")
    except OSError as exc:
        raise PolicyError(f"No se pudo inspeccionar {noun}.") from exc
    return resolved


def load_policy(path: Path = POLICY_FILE, *, root: Path | None = None) -> dict[str, Any]:
    try:
        raw = json.loads(read_repo_text(path, root=root, max_bytes=MAX_POLICY_BYTES))
    except (SafeIOError, json.JSONDecodeError) as exc:
        raise PolicyError("decisiones.yml inválido.") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "review_round_limit", "decisions"}:
        raise PolicyError("Esquema inválido.")
    if raw["version"] != 1 or raw["review_round_limit"] != 3:
        raise PolicyError("version=1 y review_round_limit=3 son obligatorios.")
    decisions = raw["decisions"]
    if not isinstance(decisions, list) or len(decisions) > 200:
        raise PolicyError("decisions debe ser una lista acotada.")
    seen: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) != {"id", "status", "text"}:
            raise PolicyError("Decisión inválida.")
        decision_id = item["id"]
        text = item["text"]
        if not isinstance(decision_id, str) or not ID_RE.fullmatch(decision_id) or decision_id in seen:
            raise PolicyError("ID inválido o duplicado.")
        seen.add(decision_id)
        if item["status"] not in {"active", "superseded"} or not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            raise PolicyError("Decisión inválida.")
    return raw


def parse_reviewer_policy(payload: str | None) -> str:
    if payload is None:
        return ""
    if len(payload.encode("utf-8")) > MAX_REVIEWER_POLICY_BYTES:
        raise PolicyError("factory-policy.json excede el tamaño permitido.")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PolicyError("factory-policy.json inválido.") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "required_review_bot"}:
        raise PolicyError("Schema de factory-policy.json inválido.")
    if raw["version"] != 1:
        raise PolicyError("factory-policy.json requiere version=1.")
    required = raw["required_review_bot"]
    if required is None:
        return ""
    if not isinstance(required, str) or not BOT_LOGIN_RE.fullmatch(required):
        raise PolicyError("Reviewer-bot base inválido.")
    return required


def load_reviewer_policy(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = _resolve_temp_input(path, noun="factory-policy.json base")
    try:
        payload = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyError("No se pudo leer factory-policy.json base.") from exc
    return parse_reviewer_policy(payload)


def resolve_required_review_bot(base_required: str, caller_required: str) -> str:
    if base_required and not BOT_LOGIN_RE.fullmatch(base_required):
        raise PolicyError("Reviewer-bot base inválido.")
    if caller_required and not BOT_LOGIN_RE.fullmatch(caller_required):
        raise PolicyError("Reviewer-bot requerido inválido.")
    if base_required:
        if caller_required not in {"", base_required}:
            raise PolicyError("Caller no puede cambiar el reviewer-bot exigido por BASE.")
        return base_required
    return caller_required


def _parse_ndjson(lines: list[str], *, noun: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for line in lines:
        if not line.strip():
            continue
        if len(line.encode("utf-8")) > MAX_EVIDENCE_ITEM_BYTES:
            raise PolicyError(f"{noun} excede el tamaño permitido.")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyError(f"{noun}s contienen NDJSON inválido.") from exc
        if not isinstance(item, dict):
            raise PolicyError(f"{noun} inválido.")
        item_id = item.get("id")
        if isinstance(item_id, int) and not isinstance(item_id, bool):
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
        items.append(item)
    return items


def parse_reviews(lines: list[str]) -> list[dict[str, Any]]:
    return _parse_ndjson(lines, noun="Review")


def parse_comments(lines: list[str]) -> list[dict[str, Any]]:
    return _parse_ndjson(lines, noun="Comentario")


def parse_checks(lines: list[str]) -> list[dict[str, Any]]:
    return _parse_ndjson(lines, noun="Check")


def parse_threads(lines: list[str]) -> list[dict[str, Any]]:
    return _parse_ndjson(lines, noun="Thread")


def review_counts_as_round(review: dict[str, Any]) -> bool:
    state = review.get("state")
    if state in {"APPROVED", "CHANGES_REQUESTED"}:
        return True
    body = review.get("body")
    return state == "COMMENTED" and isinstance(body, str) and bool(body.strip())


def count_review_rounds(lines: list[str]) -> int:
    counts: Counter[str] = Counter()
    for review in parse_reviews(lines):
        user = review.get("user")
        if (
            isinstance(user, dict)
            and user.get("type") == "Bot"
            and isinstance(user.get("login"), str)
            and review_counts_as_round(review)
        ):
            login = user["login"]
            if not 1 <= len(login) <= 100:
                raise PolicyError("Identidad de bot inválida.")
            counts[login] += 1
    return max(counts.values(), default=0)


def _comment_has_exact_head_coverage(
    comment: dict[str, Any],
    *,
    required_review_bot: str,
    head_sha: str,
) -> bool:
    user = comment.get("user")
    body = comment.get("body")
    if not (
        isinstance(user, dict)
        and user.get("type") == "Bot"
        and user.get("login") == required_review_bot
        and isinstance(body, str)
    ):
        return False
    if _is_rate_limit_body(body):
        return False
    matches = list(COMMENT_COVERAGE_RE.finditer(body))
    if len(matches) != 1:
        return False
    try:
        marker = json.loads(matches[0].group(1))
    except json.JSONDecodeError:
        return False
    if not isinstance(marker, dict) or set(marker) != {
        "sourceCommitId",
        "coveredCommitId",
        "kind",
    }:
        return False
    source_sha = marker["sourceCommitId"]
    covered_sha = marker["coveredCommitId"]
    return bool(
        isinstance(source_sha, str)
        and SHA_RE.fullmatch(source_sha)
        and isinstance(covered_sha, str)
        and SHA_RE.fullmatch(covered_sha)
        and marker["kind"] == "reviewed"
        and covered_sha == head_sha
    )


def _required_bot_review_satisfied(
    lines: list[str],
    required_review_bot: str,
    head_sha: str,
    *,
    comment_lines: list[str] | None = None,
) -> bool:
    if not BOT_LOGIN_RE.fullmatch(required_review_bot):
        raise PolicyError("Reviewer-bot requerido inválido.")
    if not SHA_RE.fullmatch(head_sha):
        raise PolicyError("HEAD requerido inválido.")
    reviews = parse_reviews(lines)
    # Un CHANGES_REQUESTED exact-HEAD del bot exigido veta toda la cobertura,
    # incluso si otras reviews o comentarios de ese bot son sustantivos.
    for review in reviews:
        user = review.get("user")
        if (
            isinstance(user, dict)
            and user.get("type") == "Bot"
            and user.get("login") == required_review_bot
            and review.get("commit_id") == head_sha
            and review.get("state") == "CHANGES_REQUESTED"
        ):
            raise PolicyError(
                "Existe CHANGES_REQUESTED bloqueante del reviewer sobre el HEAD exacto."
            )
    for review in reviews:
        user = review.get("user")
        if (
            isinstance(user, dict)
            and user.get("type") == "Bot"
            and user.get("login") == required_review_bot
            and review.get("commit_id") == head_sha
            and review.get("state") != "CHANGES_REQUESTED"
            and review_counts_as_round(review)
            and not (
                review.get("state") == "COMMENTED"
                and isinstance(review.get("body"), str)
                and _is_rate_limit_body(review["body"])
            )
        ):
            return True
    for comment in parse_comments(comment_lines or []):
        if _comment_has_exact_head_coverage(
            comment,
            required_review_bot=required_review_bot,
            head_sha=head_sha,
        ):
            return True
    return False


def validate_required_bot_review(
    lines: list[str],
    required_review_bot: str = "",
    head_sha: str = "",
    *,
    comment_lines: list[str] | None = None,
) -> None:
    if required_review_bot == "":
        return
    if _required_bot_review_satisfied(
        lines,
        required_review_bot,
        head_sha,
        comment_lines=comment_lines,
    ):
        return
    raise PolicyError(
        "Falta review o cobertura terminal/sustantiva del reviewer-bot requerido sobre el HEAD exacto."
    )


def _parse_iso_timestamp(value: object, *, noun: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise PolicyError(f"{noun} inválido.")
    return value


def _normalized_bot_login(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.removesuffix("[bot]").lower()


def parse_phase_payload(payload: str) -> str:
    if len(payload.encode("utf-8")) > MAX_PHASE_BYTES:
        raise PolicyError("datos.yml excede el tamaño permitido.")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PolicyError("datos.yml inválido.") from exc
    if not isinstance(raw, dict):
        raise PolicyError("datos.yml inválido.")
    phase = raw.get("phase")
    if phase not in {"construccion", "live"}:
        raise PolicyError("Fase de datos.yml ausente o inválida.")
    return phase


def load_phase(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = _resolve_temp_input(path, noun="datos.yml base")
    try:
        payload = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyError("No se pudo leer datos.yml base.") from exc
    return parse_phase_payload(payload)


def _latest_checks_by_name(
    lines: list[str],
    *,
    head_sha: str,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for check in parse_checks(lines):
        name = check.get("name")
        check_head = check.get("head_sha")
        check_id = check.get("id")
        if not isinstance(name, str) or not name.strip():
            raise PolicyError("Check sin nombre.")
        if check_head != head_sha:
            raise PolicyError("Check observado sobre HEAD distinto.")
        if type(check_id) is not int or check_id <= 0:
            raise PolicyError("Check sin id válido.")
        current = latest.get(name)
        if current is None or check_id > current["id"]:
            latest[name] = check
    return latest


def validate_other_gates_green(
    lines: list[str],
    *,
    head_sha: str,
) -> None:
    latest = _latest_checks_by_name(lines, head_sha=head_sha)
    if not latest:
        raise PolicyError("No hay evidencia de checks exact-HEAD.")

    successful_names: list[str] = []
    for name, check in latest.items():
        if name in {POLICY_CHECK_NAME, ACCEPTANCE_CHECK_NAME, "Validar"}:
            continue
        status = check.get("status")
        conclusion = check.get("conclusion")
        if status != "completed":
            raise PolicyError(f"Check pendiente: {name}.")
        if conclusion not in ALLOWED_GATE_CONCLUSIONS:
            raise PolicyError(f"Check no verde: {name}={conclusion}.")
        if conclusion == "success":
            successful_names.append(name.lower())

    categories = {
        "ci": lambda name: (
            name == "validate"
            or "factory ci reusable / validar" in name
            or name.startswith("ci ")
            or " ci / validate" in name
        ),
        "sonar": lambda name: "sonar" in name,
        "codeql": lambda name: "codeql" in name or name.startswith("analyze ("),
        "tests": lambda name: (
            name == "tests"
            or "test" in name
            or "acceptance" in name
            or "criterios de aceptación" in name
        ),
        "coordinacion": lambda name: (
            "coordinación" in name or "coordinacion" in name
        ),
        "privacidad": lambda name: "privacidad" in name or "privacy" in name,
    }
    missing = [
        category
        for category, predicate in categories.items()
        if not any(predicate(name) for name in successful_names)
    ]
    if missing:
        raise PolicyError(
            "Faltan gates obligatorios verdes: " + ", ".join(missing) + "."
        )


def _has_open_blocking_finding(
    lines: list[str],
    *,
    required_review_bot: str,
) -> bool:
    target = _normalized_bot_login(required_review_bot)
    for thread in parse_threads(lines):
        resolved = thread.get("isResolved")
        comments = thread.get("comments")
        if not isinstance(resolved, bool) or not isinstance(comments, dict):
            raise PolicyError("Thread de review inválido.")
        page_info = comments.get("pageInfo")
        if not isinstance(page_info, dict) or type(page_info.get("hasNextPage")) is not bool:
            raise PolicyError("Paginación de thread inválida.")
        if page_info["hasNextPage"]:
            raise PolicyError("Thread de review excede el límite evaluable.")
        nodes = comments.get("nodes")
        if not isinstance(nodes, list):
            raise PolicyError("Thread de review inválido.")
        if resolved:
            continue
        for item in nodes:
            if not isinstance(item, dict):
                raise PolicyError("Comentario de thread inválido.")
            author = item.get("author")
            if (
                isinstance(author, dict)
                and _normalized_bot_login(author.get("login")) == target
            ):
                return True
    return False


def _is_rate_limit_body(body: str) -> bool:
    return any(text in body for text in RATE_LIMIT_TEXTS)


def _rate_limit_comment_identity(
    item: dict[str, object],
    *,
    required_review_bot: str,
) -> tuple[str, int] | None:
    user = item.get("user")
    body = item.get("body")
    comment_id = item.get("id")
    if not (
        isinstance(user, dict)
        and user.get("type") == "Bot"
        and user.get("login") == required_review_bot
        and isinstance(body, str)
        and _is_rate_limit_body(body)
    ):
        return None
    if type(comment_id) is not int or comment_id <= 0:
        raise PolicyError("Comentario rate-limit sin id válido.")
    return body, comment_id


def _rate_limit_comments(
    lines: list[str],
    *,
    required_review_bot: str,
    not_before: str,
) -> list[tuple[str, int]]:
    evidence: list[tuple[str, int]] = []
    for item in parse_comments(lines):
        identity = _rate_limit_comment_identity(
            item, required_review_bot=required_review_bot
        )
        if identity is None:
            continue
        _body, comment_id = identity
        created_at = _parse_iso_timestamp(
            item.get("created_at"), noun="Timestamp de comentario rate-limit"
        )
        if created_at < not_before:
            continue
        evidence.append((created_at, comment_id))
    return sorted(evidence)


def _owner_review_retry_comments(
    lines: list[str],
    *,
    required_review_bot: str,
    not_before: str,
) -> list[tuple[str, int]]:
    mention = _normalized_bot_login(required_review_bot)
    expected = f"@{mention} review"
    evidence: list[tuple[str, int]] = []
    for item in parse_comments(lines):
        body = item.get("body")
        comment_id = item.get("id")
        if not (
            isinstance(body, str)
            and body.strip().lower() == expected
            and item.get("author_association") == "OWNER"
        ):
            continue
        if type(comment_id) is not int or comment_id <= 0:
            raise PolicyError("Comentario de reintento owner sin id válido.")
        created_at = _parse_iso_timestamp(
            item.get("created_at"), noun="Timestamp de reintento owner"
        )
        if created_at < not_before:
            continue
        if item.get("updated_at") != item.get("created_at"):
            raise PolicyError("Trigger OWNER editado o sin timestamp de integridad.")
        evidence.append((created_at, comment_id))
    return sorted(evidence)


def _exact_head_rate_limit_evidence(
    lines: list[str],
    *,
    required_review_bot: str,
    head_sha: str,
    not_before: str,
    require_update: bool,
) -> list[tuple[str, int]]:
    evidence: list[tuple[str, int]] = []
    for item in parse_comments(lines):
        identity = _rate_limit_comment_identity(
            item, required_review_bot=required_review_bot
        )
        if identity is None:
            continue
        body, comment_id = identity
        if re.search(rf"(?<![0-9a-fA-F]){re.escape(head_sha)}(?![0-9a-fA-F])", body, flags=re.IGNORECASE) is None:
            # Una cadena hexadecimal mayor no es el token del HEAD exacto.
            continue
        created_at = _parse_iso_timestamp(
            item.get("created_at"), noun="Timestamp original de comentario rate-limit"
        )
        updated_raw = item.get("updated_at")
        if require_update:
            observed_at = _parse_iso_timestamp(
                updated_raw, noun="Timestamp actualizado de comentario rate-limit"
            )
        elif updated_raw is None:
            observed_at = created_at
        else:
            observed_at = _parse_iso_timestamp(
                updated_raw, noun="Timestamp actualizado de comentario rate-limit"
            )
        if observed_at < created_at:
            raise PolicyError("Comentario rate-limit actualizado tiene timestamps incoherentes.")
        if observed_at <= not_before:
            continue
        evidence.append((observed_at, comment_id))
    return sorted(evidence)


def _in_place_rate_limit_updates(
    lines: list[str],
    *,
    required_review_bot: str,
    head_sha: str,
    not_before: str,
) -> list[tuple[str, int]]:
    return _exact_head_rate_limit_evidence(
        lines,
        required_review_bot=required_review_bot,
        head_sha=head_sha,
        not_before=not_before,
        require_update=True,
    )


def _exact_head_rate_limit_events(
    lines: list[str],
    *,
    required_review_bot: str,
    head_sha: str,
    not_before: str,
) -> list[tuple[str, int]]:
    return _exact_head_rate_limit_evidence(
        lines,
        required_review_bot=required_review_bot,
        head_sha=head_sha,
        not_before=not_before,
        require_update=False,
    )


def _sha_less_timeline_retry(
    *,
    timeline_lines: list[str],
    comment_lines: list[str],
    required_review_bot: str,
    head_sha: str,
    head_committed_at: str,
    policy_failure_times: list[str],
) -> tuple[int, str]:
    """Acredita un retry con timeline REST autenticada, nunca solo con texto del PR."""
    if not SHA_RE.fullmatch(head_sha):
        raise PolicyError("HEAD inválido para timeline autenticada.")
    if not timeline_lines or len(timeline_lines) > MAX_TIMELINE_EVENTS:
        raise PolicyError("Timeline ausente o excede el límite verificable.")
    timeline = _parse_ndjson(timeline_lines, noun="Timeline")
    if not timeline or len(timeline) != len(timeline_lines):
        raise PolicyError("Timeline incompleta o contiene elementos vacíos.")
    comments = parse_comments(comment_lines)
    comment_by_id: dict[int, dict[str, Any]] = {}
    for item in comments:
        item_id = item.get("id")
        if type(item_id) is int and item_id > 0:
            if item_id in comment_by_id:
                raise PolicyError("Comentarios con IDs repetidos.")
            comment_by_id[item_id] = item

    last_commit: str | None = None
    last_commit_index = -1
    seen_event_ids: set[int] = set()
    witnessed: list[tuple[int, dict[str, Any]]] = []
    for index, event in enumerate(timeline):
        event_type = event.get("event")
        if not isinstance(event_type, str) or not event_type:
            raise PolicyError("Evento de timeline inválido.")
        if event_type == "committed":
            commit_sha = event.get("sha")
            if not isinstance(commit_sha, str) or not SHA_RE.fullmatch(commit_sha):
                raise PolicyError("Commit de timeline sin SHA verificable.")
            last_commit = commit_sha
            last_commit_index = index
        elif event_type in {
            "head_ref_force_pushed", "head_ref_deleted", "head_ref_restored",
            "synchronize", "force_pushed",
        }:
            # No podemos reconstruir una referencia reescrita sin evidencia adicional.
            raise PolicyError("Timeline con mutación de HEAD no correlacionable.")
        elif event_type == "commented":
            event_id = event.get("id")
            if type(event_id) is not int or event_id <= 0 or event_id in seen_event_ids:
                raise PolicyError("Timeline con ID de comentario inválido o duplicado.")
            seen_event_ids.add(event_id)
            user = event.get("user")
            actor = event.get("actor")
            if not (
                isinstance(user, dict) and isinstance(actor, dict)
                and isinstance(user.get("login"), str)
                and user.get("login") == actor.get("login")
                and user.get("type") in {"User", "Bot"}
            ):
                raise PolicyError("Identidad de comentario de timeline inválida.")
            timestamp = _parse_iso_timestamp(
                event.get("created_at"), noun="Timestamp de timeline"
            )
            observed = comment_by_id.get(event_id)
            if observed is None or any(
                observed.get(field, "NONE" if field == "author_association" else None)
                != event.get(field, "NONE" if field == "author_association" else None)
                for field in ("body", "created_at", "author_association")
            ):
                raise PolicyError("Comentario no coincide con timeline autenticada.")
            observed_user = observed.get("user")
            if not (
                isinstance(observed_user, dict)
                and observed_user.get("login") == user["login"]
                and observed_user.get("type") == user["type"]
            ):
                raise PolicyError("Identidad de comentario no coincide con timeline.")
            witnessed.append((index, event))

    if last_commit != head_sha or last_commit_index < 0:
        raise PolicyError("Timeline no prueba el último commit del HEAD exacto.")

    previous_rate_limits: list[tuple[int, dict[str, Any]]] = []
    owner_requests: list[tuple[int, dict[str, Any]]] = []
    for index, event in witnessed:
        if index <= last_commit_index:
            continue
        user = event["user"]
        body = event.get("body")
        timestamp = event["created_at"]
        if timestamp <= head_committed_at:
            continue
        if (
            user["type"] == "Bot"
            and user["login"] == required_review_bot
            and isinstance(body, str) and _is_rate_limit_body(body)
        ):
            previous_rate_limits.append((index, event))
        if (
            user["type"] == "User"
            and event.get("author_association") == "OWNER"
            and isinstance(body, str)
            and body.strip().lower() == f"@{_normalized_bot_login(required_review_bot)} review"
        ):
            owner_requests.append((index, event))

    if len(owner_requests) != 1:
        raise PolicyError("Timeline requiere exactamente un reintento OWNER del HEAD.")
    owner_index, owner_event = owner_requests[0]
    owner_at = owner_event["created_at"]
    owner_observed = comment_by_id[owner_event["id"]]
    if owner_observed.get("updated_at") != owner_observed.get("created_at"):
        raise PolicyError("Trigger OWNER editado o sin timestamp de integridad.")
    initial = [
        (i, e) for i, e in previous_rate_limits
        if i < owner_index and e["created_at"] < owner_at
    ]
    replies = [
        (i, e) for i, e in previous_rate_limits
        if i > owner_index and e["created_at"] > owner_at
    ]
    if not initial:
        raise PolicyError("Falta rate-limit inicial previo al reintento OWNER.")
    if any(
        comment_by_id[event["id"]].get("updated_at") != event["created_at"]
        for _index, event in initial
    ):
        raise PolicyError("Rate-limit inicial editado o sin timestamp de integridad.")
    if not any(
        first["created_at"] <= failed_at < owner_at
        for _initial_index, first in initial
        for failed_at in policy_failure_times
    ):
        raise PolicyError("Falta FAILURE previo de Policy entre rate-limit y retry OWNER.")
    if len(replies) != 1:
        raise PolicyError("Se exige una única respuesta rate-limit tras el reintento.")
    bot_index, bot_event = replies[0]
    bot_observed = comment_by_id[bot_event["id"]]
    if bot_observed.get("updated_at") != bot_observed.get("created_at"):
        raise PolicyError("Respuesta de CodeRabbit editada o sin timestamp íntegro.")
    bot_handle = _normalized_bot_login(required_review_bot)
    review_commands = {
        f"@{bot_handle} review",
        f"@{bot_handle} full review",
    }
    if any(
        owner_index < index < bot_index
        and event["user"]["type"] == "User"
        and isinstance(event.get("body"), str)
        and event["body"].strip().lower() in review_commands
        for index, event in witnessed
    ):
        raise PolicyError("Solicitud competidora impide atribuir respuesta CodeRabbit.")
    seconds = (
        datetime.fromisoformat(bot_event["created_at"].replace("Z", "+00:00"))
        - datetime.fromisoformat(owner_at.replace("Z", "+00:00"))
    ).total_seconds()
    if not 0 < seconds <= MAX_RATE_LIMIT_REPLY_SECONDS:
        raise PolicyError("Respuesta bot fuera de ventana temporal.")
    if any(
        e.get("event") in {"committed", "head_ref_force_pushed", "synchronize"}
        for e in timeline[owner_index + 1:bot_index]
    ):
        raise PolicyError("Mutación de HEAD entre reintento y respuesta.")
    # REST autentica eventos, no el vínculo causal entre el trigger OWNER,
    # la respuesta del bot y la historia íntegra de refs. Dos causas distintas
    # pueden producir exactamente el mismo snapshot: nunca promoverlo a review.
    raise PolicyError(
        "Timeline SHA-less no vincula causalmente el rate-limit al trigger OWNER "
        "ni demuestra integridad histórica del HEAD exacto."
    )


def validate_rate_limit_fallback(
    *,
    required_review_bot: str,
    head_sha: str,
    head_committed_at: str,
    phase: str,
    review_lines: list[str],
    comment_lines: list[str],
    check_lines: list[str],
    thread_lines: list[str],
    timeline_lines: list[str] | None = None,
    run_attempt: int = 1,
) -> tuple[int, str]:
    run_attempt = _validate_run_attempt(run_attempt)
    if phase != "construccion":
        raise PolicyError("Fallback de reviewer solo permitido en construccion.")
    committed_at = _parse_iso_timestamp(
        head_committed_at, noun="Timestamp del HEAD exacto"
    )
    for review in parse_reviews(review_lines):
        user = review.get("user")
        if (
            isinstance(user, dict)
            and user.get("type") == "Bot"
            and user.get("login") == required_review_bot
            and review.get("commit_id") == head_sha
            and review.get("state") == "CHANGES_REQUESTED"
        ):
            raise PolicyError(
                "Existe CHANGES_REQUESTED bloqueante del reviewer sobre el HEAD exacto."
            )
    if _has_open_blocking_finding(
        thread_lines,
        required_review_bot=required_review_bot,
    ):
        raise PolicyError("Existe finding bloqueante abierto del reviewer requerido.")

    validate_other_gates_green(check_lines, head_sha=head_sha)

    failed_policy_checks: list[str] = []
    for check in parse_checks(check_lines):
        if (
            check.get("name") == POLICY_CHECK_NAME
            and check.get("head_sha") == head_sha
            and check.get("status") == "completed"
            and check.get("conclusion") == "failure"
        ):
            failed_policy_checks.append(
                _parse_iso_timestamp(
                    check.get("completed_at"),
                    noun="Timestamp de policy failure",
                )
            )

    if run_attempt > 1:
        if not failed_policy_checks:
            raise PolicyError("Rerun sin FAILURE previo de Policy sobre el HEAD exacto.")
        owner_retries = _owner_review_retry_comments(
            comment_lines,
            required_review_bot=required_review_bot,
            not_before=committed_at,
        )
        for retry_at, _retry_id in owner_retries:
            if retry_at <= committed_at or not any(
                failed_at < retry_at for failed_at in failed_policy_checks
            ):
                continue
            rate_limit_events = _exact_head_rate_limit_events(
                comment_lines,
                required_review_bot=required_review_bot,
                head_sha=head_sha,
                not_before=retry_at,
            )
            if rate_limit_events:
                # Un SHA en texto y una hora posterior no prueban a qué
                # solicitud respondió el bot (ni la integridad del ref).
                raise PolicyError(
                    "Rate-limit con SHA sin vínculo causal autenticado bot→OWNER→HEAD."
                )
        if timeline_lines:
            return _sha_less_timeline_retry(
                timeline_lines=timeline_lines,
                comment_lines=comment_lines,
                required_review_bot=required_review_bot,
                head_sha=head_sha,
                head_committed_at=committed_at,
                policy_failure_times=failed_policy_checks,
            )
        raise PolicyError(
            "Rerun sin reintento OWNER y rate-limit exact-HEAD posteriores verificables."
        )

    rate_limits = _rate_limit_comments(
        comment_lines,
        required_review_bot=required_review_bot,
        not_before=committed_at,
    )
    # Dos mensajes del bot (incluso separados por un FAILURE de Policy)
    # no vinculan causalmente el retry OWNER ni la respuesta al HEAD exacto.
    # Solo la ruta con trigger OWNER y SHA explícito de abajo puede permitirlo.

    for failed_at in sorted(failed_policy_checks):
        owner_retries = _owner_review_retry_comments(
            comment_lines,
            required_review_bot=required_review_bot,
            not_before=failed_at,
        )
        for retry_at, _retry_id in owner_retries:
            if retry_at <= failed_at:
                continue
            updates = _in_place_rate_limit_updates(
                comment_lines,
                required_review_bot=required_review_bot,
                head_sha=head_sha,
                not_before=retry_at,
            )
            if updates:
                # updated_at solo describe el comentario actual; no revela
                # qué contenido cambió ni qué trigger provocó esa edición.
                raise PolicyError(
                    "Rate-limit con SHA sin vínculo causal autenticado bot→OWNER→HEAD."
                )

    if len(rate_limits) < 2:
        raise PolicyError(
            "Un único rate limit no habilita fallback sin reintento OWNER verificable."
        )
    raise PolicyError(
        "Dos rate limits no prueban reintento OWNER ni vínculo causal exact-HEAD."
    )


def validate_required_bot_review_or_fallback(
    lines: list[str],
    required_review_bot: str,
    head_sha: str,
    *,
    head_committed_at: str = "",
    comment_lines: list[str],
    check_lines: list[str],
    thread_lines: list[str],
    phase_file: Path | None,
    timeline_lines: list[str] | None = None,
    run_attempt: int = 1,
) -> dict[str, Any]:
    run_attempt = _validate_run_attempt(run_attempt)
    if required_review_bot == "":
        return {"review_fallback": False}
    if _required_bot_review_satisfied(
        lines,
        required_review_bot,
        head_sha,
        comment_lines=comment_lines,
    ):
        return {"review_fallback": False}

    phase = load_phase(phase_file)
    retry_id, retry_at = validate_rate_limit_fallback(
        required_review_bot=required_review_bot,
        head_sha=head_sha,
        head_committed_at=head_committed_at,
        phase=phase,
        review_lines=lines,
        comment_lines=comment_lines,
        check_lines=check_lines,
        thread_lines=thread_lines,
        timeline_lines=timeline_lines,
        run_attempt=run_attempt,
    )
    return {
        "review_fallback": True,
        "rate_limit_comment_id": retry_id,
        "rate_limit_created_at": retry_at,
        "phase": phase,
    }


def validate_rounds(rounds: int, limit: int) -> None:
    if rounds > limit:
        raise PolicyError(f"Rondas automáticas={rounds} supera límite {limit}.")


def _read_bounded_lines(path: Path, *, max_bytes: int, noun: str) -> list[str]:
    resolved = _resolve_temp_input(path, noun=noun)
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            payload = handle.read(max_bytes + 1)
    except (OSError, UnicodeError) as exc:
        raise PolicyError(f"No se pudo leer {noun}.") from exc
    if len(payload.encode("utf-8")) > max_bytes:
        raise PolicyError(f"{noun} exceden el tamaño permitido.")
    return payload.splitlines()


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required-review-bot", default="")
    parser.add_argument("--base-policy-file", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--head-committed-at", default="")
    parser.add_argument("--comments-file", default="")
    parser.add_argument("--checks-file", default="")
    parser.add_argument("--threads-file", default="")
    parser.add_argument("--timeline-file", default="")
    parser.add_argument("--phase-file", default="")
    return parser.parse_args()


def main() -> int:
    options = args()
    review_payload = sys.stdin.read(MAX_REVIEWS_BYTES + 1)
    if len(review_payload.encode("utf-8")) > MAX_REVIEWS_BYTES:
        print("ERROR: reviews exceden el tamaño permitido.", file=sys.stderr)
        return 1
    lines = review_payload.splitlines()
    try:
        run_attempt = _run_attempt_from_env()
        policy = load_policy()
        base_required = load_reviewer_policy(
            Path(options.base_policy_file) if options.base_policy_file else None
        )
        effective_required = resolve_required_review_bot(
            base_required, options.required_review_bot
        )
        comment_lines = (
            _read_bounded_lines(
                Path(options.comments_file),
                max_bytes=MAX_COMMENTS_BYTES,
                noun="comentarios",
            )
            if options.comments_file
            else []
        )
        check_lines = (
            _read_bounded_lines(
                Path(options.checks_file),
                max_bytes=MAX_CHECKS_BYTES,
                noun="checks",
            )
            if options.checks_file
            else []
        )
        thread_lines = (
            _read_bounded_lines(
                Path(options.threads_file),
                max_bytes=MAX_THREADS_BYTES,
                noun="threads",
            )
            if options.threads_file
            else []
        )
        timeline_lines = (
            _read_bounded_lines(
                Path(options.timeline_file),
                max_bytes=MAX_TIMELINE_BYTES,
                noun="timeline",
            )
            if getattr(options, "timeline_file", "")
            else None
        )
        rounds = count_review_rounds(lines)
        validate_rounds(rounds, policy["review_round_limit"])
        review_result = validate_required_bot_review_or_fallback(
            lines,
            effective_required,
            options.head_sha,
            head_committed_at=options.head_committed_at,
            comment_lines=comment_lines,
            check_lines=check_lines,
            thread_lines=thread_lines,
            phase_file=Path(options.phase_file) if options.phase_file else None,
            run_attempt=run_attempt,
            timeline_lines=timeline_lines,
        )
    except PolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "decisions": len(policy["decisions"]),
        "review_rounds": rounds,
        "required_review_bot": effective_required or None,
        **review_result,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())