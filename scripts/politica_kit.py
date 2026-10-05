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
    for review in parse_reviews(lines):
        user = review.get("user")
        if (
            isinstance(user, dict)
            and user.get("type") == "Bot"
            and user.get("login") == required_review_bot
            and review.get("commit_id") == head_sha
            and review.get("state") != "CHANGES_REQUESTED"
            and review_counts_as_round(review)
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
        evidence.append((created_at, comment_id))
    return sorted(evidence)


def _in_place_rate_limit_updates(
    lines: list[str],
    *,
    required_review_bot: str,
    head_sha: str,
    not_before: str,
) -> list[tuple[str, int]]:
    evidence: list[tuple[str, int]] = []
    for item in parse_comments(lines):
        identity = _rate_limit_comment_identity(
            item, required_review_bot=required_review_bot
        )
        if identity is None:
            continue
        body, comment_id = identity
        if head_sha not in body:
            continue
        created_at = _parse_iso_timestamp(
            item.get("created_at"), noun="Timestamp original de comentario rate-limit"
        )
        updated_at = _parse_iso_timestamp(
            item.get("updated_at"), noun="Timestamp actualizado de comentario rate-limit"
        )
        if updated_at < created_at:
            raise PolicyError("Comentario rate-limit actualizado tiene timestamps incoherentes.")
        if updated_at <= not_before:
            continue
        evidence.append((updated_at, comment_id))
    return sorted(evidence)


def _exact_head_rate_limit_events(
    lines: list[str],
    *,
    required_review_bot: str,
    head_sha: str,
    not_before: str,
) -> list[tuple[str, int]]:
    evidence: list[tuple[str, int]] = []
    for item in parse_comments(lines):
        identity = _rate_limit_comment_identity(
            item, required_review_bot=required_review_bot
        )
        if identity is None:
            continue
        body, comment_id = identity
        if head_sha not in body:
            continue
        created_at = _parse_iso_timestamp(
            item.get("created_at"), noun="Timestamp original de comentario rate-limit"
        )
        observed_at = created_at
        updated_raw = item.get("updated_at")
        if updated_raw is not None:
            updated_at = _parse_iso_timestamp(
                updated_raw, noun="Timestamp actualizado de comentario rate-limit"
            )
            if updated_at < created_at:
                raise PolicyError(
                    "Comentario rate-limit actualizado tiene timestamps incoherentes."
                )
            observed_at = updated_at
        if observed_at <= not_before:
            continue
        evidence.append((observed_at, comment_id))
    return sorted(evidence)


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

    if run_attempt > 1:
        owner_retries = _owner_review_retry_comments(
            comment_lines,
            required_review_bot=required_review_bot,
            not_before=committed_at,
        )
        for retry_at, _retry_id in owner_retries:
            if retry_at <= committed_at:
                continue
            rate_limit_events = _exact_head_rate_limit_events(
                comment_lines,
                required_review_bot=required_review_bot,
                head_sha=head_sha,
                not_before=retry_at,
            )
            if rate_limit_events:
                return rate_limit_events[0][1], rate_limit_events[0][0]
        raise PolicyError(
            "Rerun sin reintento OWNER y rate-limit exact-HEAD posteriores verificables."
        )

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

    rate_limits = _rate_limit_comments(
        comment_lines,
        required_review_bot=required_review_bot,
        not_before=committed_at,
    )
    if len(rate_limits) >= 2:
        for first_at, _first_id in rate_limits:
            for failed_at in sorted(failed_policy_checks):
                if failed_at < first_at:
                    continue
                for retry_at, retry_id in rate_limits:
                    if retry_at > failed_at:
                        return retry_id, retry_at

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
                return updates[0][1], updates[0][0]

    if len(rate_limits) < 2:
        raise PolicyError(
            "Un único rate limit no habilita fallback sin reintento OWNER verificable."
        )
    raise PolicyError(
        "Falta un reintento rate-limited posterior a un fallo de policy sobre el HEAD exacto."
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