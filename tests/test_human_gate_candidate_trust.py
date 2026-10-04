#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "seguridad"
if str(SECURITY) not in sys.path:
    sys.path.insert(0, str(SECURITY))

import sincronizar_puerta as sync  # noqa: E402
from puertas_humanas import gate_target_identity_from_body  # noqa: E402


REPOSITORY = "pl0n3r/example"
GATE_BODY = """Trusted decision gate.

<!-- factory-human-gate {"category":"product-direction","context":"canonical target","options":[{"id":"A","label":"Proceed"},{"id":"B","label":"Do not proceed"}],"recommendation":"A","safe_default":"B"} -->
"""


def issue(
    number: int,
    association: str | None,
    *,
    body: str = GATE_BODY,
    state: str = "open",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "number": number,
        "state": state,
        "body": body,
        "labels": [],
    }
    if association is not None:
        payload["author_association"] = association
    return payload


class FakeApi:
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = {item["number"]: dict(item) for item in issues}
        self.mutations: list[tuple[str, str, Any]] = []

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        collection = f"repos/{REPOSITORY}/issues?state=all&per_page=100"
        if method == "GET" and path == collection:
            return [dict(self.issues[number]) for number in sorted(self.issues)]

        prefix = f"repos/{REPOSITORY}/issues/"
        if not path.startswith(prefix):
            raise AssertionError(f"Unexpected API path: {method} {path}")

        suffix = path[len(prefix):]
        number_text, *rest = suffix.split("/", 1)
        number = int(number_text)
        current = self.issues[number]

        if method == "GET" and not rest:
            return dict(current)
        if method == "GET" and rest == ["comments?per_page=100"]:
            return []
        if method == "GET" and rest == ["events?per_page=100"]:
            return []

        self.mutations.append((method, path, payload))
        raise AssertionError(
            f"Unexpected mutation while reconciling trusted gate: {method} {path}"
        )


class HumanGateCandidateTrustTests(unittest.TestCase):
    def target_identity(self) -> str:
        return gate_target_identity_from_body(GATE_BODY)

    def test_untrusted_or_missing_author_association_is_excluded_before_canonicalization(
        self,
    ) -> None:
        candidates = [
            issue(1, "NONE"),
            issue(2, None),
            issue(3, "CONTRIBUTOR"),
            issue(4, "OWNER"),
        ]
        api = FakeApi(candidates)

        equivalent = sync._target_issues(
            api,
            REPOSITORY,
            self.target_identity(),
        )

        self.assertEqual([item["number"] for item in equivalent], [4])

    def test_owner_member_and_collaborator_equivalent_candidates_remain_eligible(
        self,
    ) -> None:
        candidates = [
            issue(7, "COLLABORATOR"),
            issue(5, "OWNER"),
            issue(6, "MEMBER"),
        ]
        api = FakeApi(candidates)

        equivalent = sync._target_issues(
            api,
            REPOSITORY,
            self.target_identity(),
        )

        self.assertEqual(
            [(item["number"], item["author_association"]) for item in equivalent],
            [
                (5, "OWNER"),
                (6, "MEMBER"),
                (7, "COLLABORATOR"),
            ],
        )

    def test_lower_number_untrusted_issue_cannot_displace_or_close_trusted_gate(
        self,
    ) -> None:
        untrusted = issue(10, "NONE")
        trusted = issue(20, "OWNER")
        api = FakeApi([untrusted, trusted])

        canonical = sync.reconcile_gate(api, REPOSITORY, 20)

        self.assertTrue(canonical)
        self.assertEqual(api.mutations, [])
        self.assertEqual(api.issues[10]["state"], "open")
        self.assertEqual(api.issues[20]["state"], "open")


if __name__ == "__main__":
    unittest.main()
