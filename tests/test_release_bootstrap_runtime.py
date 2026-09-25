#!/usr/bin/env python3
import unittest

from scripts.release_bootstrap import ReleaseBootstrapError, validate_payload

SHA = "a" * 40
OTHER = "b" * 40
GATE_FIRST = (
    '<!-- factory-human-gate '
    '{"category":"release-1.0.0","context":"Publicar Factory v1.0.0.",'
    '"options":[{"id":"A","label":"Publicar"},{"id":"B","label":"No publicar"}],'
    '"recommendation":"B","safe_default":"B"} -->'
)
GATE_MAINTENANCE = (
    '<!-- factory-human-gate '
    '{"category":"factory-release","context":"Publicar mantenimiento Factory v1.x.",'
    '"options":[{"id":"A","label":"Publicar"},{"id":"B","label":"No publicar"}],'
    '"recommendation":"B","safe_default":"B"} -->'
)


def valid_payload(*, gate_body=GATE_FIRST, v1_0_0_exists=False):
    return {
        "repository": "pl0n3r/factory", "repository_owner": "pl0n3r",
        "actor": "pl0n3r", "event_name": "workflow_dispatch",
        "ref": "refs/heads/main", "default_branch": "main",
        "expected_sha": SHA, "current_sha": SHA,
        "default_branch_sha": SHA, "v1_sha": SHA,
        "v1_0_0_exists": v1_0_0_exists,
        "issues": {**{str(n): {"state": "closed"} for n in range(1, 15)}, "54": {"state": "closed"}, "83": {"state": "closed"}},
        "gate": {
            "state": "closed", "author_association": "OWNER", "closed_by": "pl0n3r",
            "body": gate_body,
            "comments": [{"author_association": "OWNER", "user": {"login": "pl0n3r"},
                          "body": f'<!-- factory-release-approval {{"sha":"{SHA}"}} -->'}],
        },
    }


class ReleaseBootstrapRuntimeTests(unittest.TestCase):
    def test_valid_first_release_candidate(self):
        self.assertEqual(validate_payload(valid_payload()), {"status": "ready", "sha": SHA})

    def test_valid_maintenance_release_candidate(self):
        payload = valid_payload(gate_body=GATE_MAINTENANCE, v1_0_0_exists=True)
        self.assertEqual(validate_payload(payload), {"status": "ready", "sha": SHA})

    def test_release_gate_lifecycle_is_fail_closed(self):
        with self.assertRaisesRegex(ReleaseBootstrapError, "factory-release"):
            validate_payload(valid_payload(v1_0_0_exists=True))
        with self.assertRaisesRegex(ReleaseBootstrapError, "release-1.0.0"):
            validate_payload(valid_payload(gate_body=GATE_MAINTENANCE))

    def test_fail_closed_cases(self):
        mutations = {
            "wrong-current": lambda p: p.__setitem__("current_sha", OTHER),
            "stale-main": lambda p: p.__setitem__("default_branch_sha", OTHER),
            "wrong-v1": lambda p: p.__setitem__("v1_sha", OTHER),
            "wrong-actor": lambda p: p.__setitem__("actor", "otro"),
            "wrong-repo": lambda p: p.__setitem__("repository", "pl0n3r/otro"),
            "wrong-event": lambda p: p.__setitem__("event_name", "push"),
            "wrong-ref": lambda p: p.__setitem__("ref", "refs/heads/otra"),
            "invalid-release-state": lambda p: p.__setitem__("v1_0_0_exists", "yes"),
            "open-core": lambda p: p["issues"]["7"].__setitem__("state", "open"),
            "open-privacy": lambda p: p["issues"]["54"].__setitem__("state", "open"),
            "open-trust-root": lambda p: p["issues"]["83"].__setitem__("state", "open"),
            "open-gate": lambda p: p["gate"].__setitem__("state", "open"),
            "untrusted-gate": lambda p: p["gate"].__setitem__("author_association", "NONE"),
            "wrong-closer": lambda p: p["gate"].__setitem__("closed_by", "otro"),
            "wrong-category": lambda p: p["gate"].__setitem__("body", GATE_FIRST.replace('"release-1.0.0"', '"money"')),
            "missing-approval": lambda p: p["gate"].__setitem__("comments", []),
            "wrong-approval": lambda p: p["gate"]["comments"][0].__setitem__(
                "body", f'<!-- factory-release-approval {{"sha":"{OTHER}"}} -->'
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                payload = valid_payload()
                mutate(payload)
                with self.assertRaises(ReleaseBootstrapError):
                    validate_payload(payload)


if __name__ == "__main__":
    unittest.main()
