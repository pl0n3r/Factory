#!/usr/bin/env python3
"""Valida decisiones, rondas y evidencia reviewer-bot anclada al HEAD exacto."""
from __future__ import annotations

import argparse
import json
import re
import sys
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
MAX_EVIDENCE_ITEM_BYTES = 100_000


class PolicyError(ValueError):
    pass


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
    try:
        payload = path.read_text(encoding="utf-8")
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


def validate_required_bot_review(
    lines: list[str],
    required_review_bot: str = "",
    head_sha: str = "",
    *,
    comment_lines: list[str] | None = None,
) -> None:
    if required_review_bot == "":
        return
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
            return
    for comment in parse_comments(comment_lines or []):
        if _comment_has_exact_head_coverage(
            comment,
            required_review_bot=required_review_bot,
            head_sha=head_sha,
        ):
            return
    raise PolicyError(
        "Falta review o cobertura terminal/sustantiva del reviewer-bot requerido sobre el HEAD exacto."
    )


def validate_rounds(rounds: int, limit: int) -> None:
    if rounds > limit:
        raise PolicyError(f"Rondas automáticas={rounds} supera límite {limit}.")


def _read_bounded_lines(path: Path, *, max_bytes: int, noun: str) -> list[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
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
    parser.add_argument("--comments-file", default="")
    return parser.parse_args()


def main() -> int:
    options = args()
    review_payload = sys.stdin.read(MAX_REVIEWS_BYTES + 1)
    if len(review_payload.encode("utf-8")) > MAX_REVIEWS_BYTES:
        print("ERROR: reviews exceden el tamaño permitido.", file=sys.stderr)
        return 1
    lines = review_payload.splitlines()
    try:
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
        rounds = count_review_rounds(lines)
        validate_rounds(rounds, policy["review_round_limit"])
        validate_required_bot_review(
            lines,
            effective_required,
            options.head_sha,
            comment_lines=comment_lines,
        )
    except PolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "decisions": len(policy["decisions"]),
        "review_rounds": rounds,
        "required_review_bot": effective_required or None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
