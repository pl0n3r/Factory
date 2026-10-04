#!/usr/bin/env python3
import json
import unittest

from sincronizar_puerta import BOT, reconcile_gate


SHA = "44647624c9532b727a4cc4085e8c0e6d19898ec0"


def release_gate_body(*, sha: str = SHA, rearm_sha: str | None = None) -> str:
    gate = {
        "blocks": "Factory@v1 no cambia sin una decisión exact-SHA nueva.",
        "category": "factory-release",
        "context": (
            f"Autorizar Factory v1.0.27 exclusivamente para main@{sha}. "
            "Puerta rearmada desde #1004; la decisión anterior no se hereda."
        ),
        "options": [
            {
                "effect": "Autorizar exclusivamente el HEAD exacto.",
                "id": "A",
                "label": "Publicar Factory 1.0.27",
                "reversible": True,
                "risk": "medium",
            },
            {
                "effect": "Mantener Factory@v1 sin cambios.",
                "id": "B",
                "label": "No publicar todavía",
                "reversible": True,
                "risk": "low",
            },
        ],
        "recommendation": "A",
        "safe_default": "B",
        "summary_simple": "Factory 1.0.27 requiere una decisión nueva.",
        "title_simple": "Publicar Factory 1.0.27",
        "why_recommended": "El candidato debe revalidarse sobre el HEAD actual.",
    }
    marker = json.dumps(gate, separators=(",", ":"), sort_keys=True)
    rearm = json.dumps(
        {
            "sha": sha if rearm_sha is None else rearm_sha,
            "source_issue": 1004,
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"<!-- factory-human-gate {marker} -->\n"
        f"<!-- factory-release-rearm {rearm} -->"
    )


def bot_issue(body: str, *, number: int = 1008) -> dict:
    return {
        "number": number,
        "state": "open",
        "author_association": "NONE",
        "user": {"login": BOT, "type": "Bot"},
        "body": body,
        "labels": [{"name": "decisión: dueño"}],
    }


class FakeAPI:
    def __init__(self, issues: list[dict]):
        self.issues = {item["number"]: json.loads(json.dumps(item)) for item in issues}

    def __call__(self, method: str, path: str, payload=None):
        if method == "GET" and path.endswith("/issues?state=all&per_page=100"):
            return [json.loads(json.dumps(item)) for item in self.issues.values()]
        if method == "GET" and "/issues/" in path and path.endswith("/comments?per_page=100"):
            return []
        if method == "GET" and "/issues/" in path:
            number = int(path.rsplit("/", 1)[1])
            return json.loads(json.dumps(self.issues[number]))
        raise AssertionError(f"Unexpected API call: {method} {path} {payload}")


class ReleaseRearmGateSyncTests(unittest.TestCase):
    def test_actions_bot_release_rearm_gate_is_canonical(self) -> None:
        api = FakeAPI([bot_issue(release_gate_body())])
        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 1008))

    def test_arbitrary_bot_gate_without_valid_rearm_is_not_trusted(self) -> None:
        valid = release_gate_body()
        gate_only = valid.split("\n<!-- factory-release-rearm", 1)[0]

        malformed = valid.replace(
            '"source_issue":1004',
            '"source_issue":"1004"',
        )
        duplicate = valid + "\n" + valid.split("\n", 1)[1]

        for body in (gate_only, malformed, duplicate):
            with self.subTest(body=body):
                api = FakeAPI([bot_issue(body)])
                self.assertFalse(reconcile_gate(api, "pl0n3r/Factory", 1008))

    def test_rearm_sha_must_match_factory_release_target(self) -> None:
        api = FakeAPI([
            bot_issue(
                release_gate_body(
                    rearm_sha="1" * 40,
                )
            )
        ])
        self.assertFalse(reconcile_gate(api, "pl0n3r/Factory", 1008))


if __name__ == "__main__":
    unittest.main()
