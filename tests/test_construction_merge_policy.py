"""Distingue el diagnóstico esencial #1295 del Policy versionado aún estricto.

El motor publicado en consumidores no se modifica mediante este PR.
"""
import json
import unittest

from scripts import politica_kit as policy
from scripts.politica_kit import PolicyError
from scripts.automerge_construccion import FIELDS


HEAD = "a" * 40


def check(*, check_id, name, conclusion="success", status="completed",
          head_sha=HEAD, completed_at="2026-10-04T05:00:00Z"):
    # Identidades reales verificadas de las GitHub Apps de checks.
    slug = ("sonarqubecloud" if name == "SonarCloud Code Analysis"
            else "github-advanced-security" if name == "CodeQL"
            else "github-actions")
    app_id = {
        "sonarqubecloud": 12526,
        "github-advanced-security": 57789,
        "github-actions": 15368,
    }[slug]
    return json.dumps({
        "id": check_id,
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
        "app": {"slug": slug, "id": app_id},
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
    def test_versioned_policy_keeps_existing_checks_until_separate_rollout(self):
        """Policy externo sigue estricto aunque el diagnóstico puro sea esencial."""
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

    def test_essential_diagnostic_has_complete_quality_and_hard_gate_evidence(self):
        self.assertTrue({"quality_evidence", "quality_findings", "hard_gates"}.issubset(FIELDS))


if __name__ == "__main__":
    unittest.main()
