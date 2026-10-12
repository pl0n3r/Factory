"""Pruebas independientes del criterio de fusión en construcción D-069.

Las pruebas de Policy compartidas por otros PR permanecen sin modificaciones.
"""
import json
import unittest

from scripts import politica_kit as policy
from scripts.politica_kit import PolicyError


HEAD = "a" * 40


def check(*, check_id, name, conclusion="success", status="completed",
          head_sha=HEAD, completed_at="2026-10-04T05:00:00Z"):
    return json.dumps({
        "id": check_id,
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
    })


def green_gate_checks(*, head_sha=HEAD):
    names = (
        "validate", "SonarCloud Code Analysis", "CodeQL", "tests",
        "validar-pr / Validar coordinación", "privacidad / Privacidad como código",
    )
    return [
        check(check_id=index, name=name, head_sha=head_sha)
        for index, name in enumerate(names, start=10)
    ]


class ConstructionMergePolicyTests(unittest.TestCase):
    def test_construction_merge_policy_preserves_restricted_gates(self):
        """Eximir la segunda cuenta no habilita checks rojos o ajenos al HEAD."""
        policy.validate_other_gates_green(green_gate_checks(), head_sha=HEAD)

        failed = green_gate_checks() + [
            check(check_id=90, name="SonarCloud Code Analysis",
                  conclusion="failure", completed_at="2026-10-04T05:03:00Z"),
        ]
        with self.assertRaisesRegex(PolicyError, "Check no verde"):
            policy.validate_other_gates_green(failed, head_sha=HEAD)

        pending = green_gate_checks() + [
            check(check_id=91, name="CodeQL", status="in_progress",
                  conclusion=None, completed_at="2026-10-04T05:03:00Z"),
        ]
        with self.assertRaisesRegex(PolicyError, "Check pendiente"):
            policy.validate_other_gates_green(pending, head_sha=HEAD)

        with self.assertRaisesRegex(PolicyError, "HEAD distinto"):
            policy.validate_other_gates_green(
                green_gate_checks(head_sha="b" * 40), head_sha=HEAD,
            )

        missing = [
            row for row in green_gate_checks()
            if json.loads(row)["name"] != "tests"
        ]
        with self.assertRaisesRegex(PolicyError, "tests"):
            policy.validate_other_gates_green(missing, head_sha=HEAD)


if __name__ == "__main__":
    unittest.main()
