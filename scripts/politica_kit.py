#!/usr/bin/env python3
"""Valida decisiones canónicas, rondas y reviewer-bot opcional sobre HEAD exacto."""
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
POLICY_FILE = Path("decisiones.yml")
MAX_POLICY_BYTES = 256 * 1024
MAX_REVIEWS_BYTES = 2_000_000

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

def parse_reviews(lines: list[str]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for line in lines:
        if not line.strip():
            continue
        if len(line) > 100_000:
            raise PolicyError("Review excede el tamaño permitido.")
        try:
            review = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyError("Reviews contienen NDJSON inválido.") from exc
        if not isinstance(review, dict):
            raise PolicyError("Review inválido.")
        review_id = review.get("id")
        if isinstance(review_id, int) and not isinstance(review_id, bool):
            if review_id in seen_ids:
                continue
            seen_ids.add(review_id)
        reviews.append(review)
    return reviews

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

def resolve_required_review_bot(
    caller_value: str = "",
    repository_value: str = "",
) -> str:
    """Resuelve configuración persistida sin permitir que el HEAD candidato la rebaje."""
    for value in (caller_value, repository_value):
        if value != "" and not BOT_LOGIN_RE.fullmatch(value):
            raise PolicyError("Reviewer-bot requerido inválido.")
    if repository_value:
        if caller_value and caller_value != repository_value:
            raise PolicyError("El input del caller contradice el reviewer-bot configurado.")
        return repository_value
    if caller_value:
        raise PolicyError(
            "required_review_bot no es autoritativo sin FACTORY_REQUIRED_REVIEW_BOT."
        )
    return ""


def validate_required_bot_review(lines: list[str], required_review_bot: str = "", head_sha: str = "") -> None:
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
    raise PolicyError("Falta review terminal/sustantiva del reviewer-bot requerido sobre el HEAD exacto.")

def validate_rounds(rounds: int, limit: int) -> None:
    if rounds > limit:
        raise PolicyError(f"Rondas automáticas={rounds} supera límite {limit}.")

def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required-review-bot", default="")
    parser.add_argument("--repository-required-review-bot", default="")
    parser.add_argument("--head-sha", default="")
    return parser.parse_args()

def main() -> int:
    options = args()
    review_payload = sys.stdin.read(MAX_REVIEWS_BYTES + 1)
    if len(review_payload) > MAX_REVIEWS_BYTES:
        print("ERROR: reviews exceden el tamaño permitido.", file=sys.stderr)
        return 1
    lines = review_payload.splitlines()
    try:
        policy = load_policy()
        rounds = count_review_rounds(lines)
        validate_rounds(rounds, policy["review_round_limit"])
        required_review_bot = resolve_required_review_bot(
            options.required_review_bot,
            options.repository_required_review_bot,
        )
        validate_required_bot_review(lines, required_review_bot, options.head_sha)
    except PolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "decisions": len(policy["decisions"]),
        "review_rounds": rounds,
        "required_review_bot": required_review_bot or None,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
