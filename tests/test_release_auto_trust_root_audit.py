"""Regresiones offline para la hoja #2100 de Factory #1080."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_auto_trust_root_audit import evaluate_trust_root  # noqa: E402


APP_ID = 820201  # Solo fixture sintética; NO es una identidad instalada.


def example() -> dict:
    return {
        "app": {"id": APP_ID, "slug": "factory-release-dedicated", "purpose": "factory-release-only"},
        "installation": {
            "app_id": APP_ID,
            "repository_selection": "selected",
            "repositories": ["pl0n3r/Factory"],
            "permissions": {"contents": "write", "metadata": "read"},
            "suspended_at": None,
        },
        "ruleset": {
            "id": 23958613,
            "target": "tag", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/tags/v1"], "exclude": []}},
            "rules": [{"type": item} for item in ("creation", "update", "deletion")],
            "bypass_actors": [
                {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                {"actor_id": APP_ID, "actor_type": "Integration", "bypass_mode": "always"},
            ],
        },
    }


class ReleaseAutoTrustRootAuditTests(unittest.TestCase):
    def assert_blocked(self, data: object) -> None:
        decision = evaluate_trust_root(data)
        self.assertEqual(decision["state"], "BLOCKED", decision)
        self.assertFalse(decision["authorizes_release"])

    def test_role_only_and_generic_actions_app_block(self) -> None:
        data = example()
        data["ruleset"]["bypass_actors"].pop()
        self.assert_blocked(data)  # Estado real: solo bypass humano.
        data = example()
        data["app"]["id"] = 15368
        data["installation"]["app_id"] = 15368
        data["ruleset"]["bypass_actors"][1]["actor_id"] = 15368
        self.assert_blocked(data)  # GitHub Actions genérica nunca obtiene permiso.

    def test_dedicated_app_is_review_only_and_nonminimal_permissions_block(self) -> None:
        self.assertEqual(evaluate_trust_root(example())["state"], "REVIEW_ONLY")
        for mutate in (
            lambda x: x["installation"].update(repository_selection="all"),
            lambda x: x["installation"]["repositories"].append("pl0n3r/Condor"),
            lambda x: x["installation"]["permissions"].update(actions="write"),
            lambda x: x["installation"].update(suspended_at="2026-01-01T00:00:00Z"),
            lambda x: x["ruleset"]["bypass_actors"].append(
                {"actor_id": 15368, "actor_type": "Integration", "bypass_mode": "always"}),
        ):
            with self.subTest(mutate=mutate):
                data = example()
                mutate(data)
                self.assert_blocked(data)

    def test_incomplete_or_ambiguous_snapshots_block(self) -> None:
        self.assert_blocked(None)
        self.assert_blocked({})
        for mutate in (
            lambda x: x.pop("app"),
            lambda x: x["app"].update(id=True),
            lambda x: x["installation"].update(app_id=1),
            lambda x: x["ruleset"].update(enforcement="disabled"),
            lambda x: x["ruleset"]["conditions"]["ref_name"]["include"].append("~ALL"),
            lambda x: x["ruleset"]["rules"].pop(),
            lambda x: x["ruleset"]["rules"].append({"type": "creation"}),
            lambda x: x["ruleset"]["bypass_actors"].append(
                deepcopy(x["ruleset"]["bypass_actors"][1])),
            lambda x: x["ruleset"].update(unknown_authority=True),
            lambda x: x["ruleset"]["bypass_actors"][1].update(actor_type=[]),
        ):
            data = example()
            mutate(data)
            self.assert_blocked(data)

    def test_never_authorizes_release_or_uses_io(self) -> None:
        data = example()
        before = deepcopy(data)
        for payload in (data, None, {}, {"ruleset": {}}, example()):
            decision = evaluate_trust_root(payload)
            self.assertFalse(decision["authorizes_release"])
            for key in ("mutations", "network_calls", "tag_writes", "release_writes"):
                self.assertEqual(decision[key], 0)
        self.assertEqual(data, before)
        tree = ast.parse((ROOT / "scripts/release_auto_trust_root_audit.py").read_text())
        self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom))
                             and any(name in ast.unparse(n) for name in (
                                 "subprocess", "requests", "socket", "urllib", "httpx", "os"))
                             for n in ast.walk(tree)))
        runbook = (ROOT / "docs/release-auto-trust-root-audit.md").read_text()
        self.assertIn("sin autorización", runbook)
        self.assertIn("#2075/A", runbook)


if __name__ == "__main__":
    unittest.main()
