#!/usr/bin/env python3
import hashlib
import json
import unittest
from pathlib import Path

from scripts.release_bootstrap import ReleaseBootstrapError, validate_payload
from seguridad.puertas_humanas import MARKER_RE, validate_gate

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
OTHER = "b" * 40
NOW = "2026-10-03T10:30:00Z"
WINDOW_OPEN = "2026-10-03T10:00:00Z"
WINDOW_CLOSE = "2026-10-03T11:00:00Z"
GATE_FIRST = (
    '<!-- factory-human-gate '
    '{"category":"release-1.0.0","context":"Publicar Factory v1.0.0.",'
    '"options":[{"id":"A","label":"Publicar"},{"id":"B","label":"No publicar"}],'
    '"recommendation":"B","safe_default":"B"} -->'
)
GATE_MAINTENANCE = (
    '<!-- factory-human-gate '
    f'{{"category":"factory-release","context":"Publicar mantenimiento Factory v1.x '
    f'exclusivamente para main@{SHA}.",'
    '"options":[{"id":"A","label":"Publicar Factory 1.0.15"},'
    '{"id":"B","label":"No publicar todavía"}],'
    '"recommendation":"A","safe_default":"B"} -->'
)


def rearmed_gate_body(
    *,
    sha: str = SHA,
    source_issue: int = 927,
    opened_at: str = WINDOW_OPEN,
    expires_at: str = WINDOW_CLOSE,
) -> str:
    window = json.dumps(
        {
            "expires_at": expires_at,
            "opened_at": opened_at,
            "sha": sha,
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    rearm = json.dumps(
        {
            "sha": sha,
            "source_issue": source_issue,
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        GATE_MAINTENANCE
        + f"\n<!-- factory-release-window {window} -->"
        + f"\n<!-- factory-release-rearm {rearm} -->"
    )


def owner_source_issue(
    *,
    number: int = 927,
    body: str = GATE_MAINTENANCE,
) -> dict[str, object]:
    return {
        "number": number,
        "state": "closed",
        "author_association": "OWNER",
        "created_at": "2026-10-03T09:50:00Z",
        "user": {"login": "pl0n3r"},
        "body": body,
    }


def bot_source_issue(
    *,
    number: int,
    source_issue: int,
    sha: str = SHA,
) -> dict[str, object]:
    return {
        "number": number,
        "state": "closed",
        "author_association": "NONE",
        "created_at": "2026-10-03T10:05:00Z",
        "user": {"login": "github-actions[bot]"},
        "body": rearmed_gate_body(
            sha=sha,
            source_issue=source_issue,
            opened_at="2026-10-03T10:00:00Z",
            expires_at="2026-10-03T10:20:00Z",
        ),
    }


def gate_fingerprint(body: str) -> str:
    matches = MARKER_RE.findall(body)
    if len(matches) != 1:
        raise AssertionError("fixture gate debe contener un único marker")
    gate = validate_gate(json.loads(matches[0]))
    canonical = json.dumps(
        gate,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_journal(body: str, *, option: str = "A") -> str:
    marker = json.dumps(
        {
            "gate_sha256": gate_fingerprint(body),
            "option": option,
            "version": 2,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"<!-- factory-human-decision {marker} -->\nDecisión materializada."


def valid_payload(*, gate_body=GATE_FIRST, v1_0_0_exists=False):
    return {
        "repository": "pl0n3r/factory",
        "repository_owner": "pl0n3r",
        "actor": "pl0n3r",
        "event_name": "workflow_dispatch",
        "ref": "refs/heads/main",
        "default_branch": "main",
        "expected_sha": SHA,
        "current_sha": SHA,
        "default_branch_sha": SHA,
        "v1_sha": SHA,
        "v1_0_0_exists": v1_0_0_exists,
        "now": NOW,
        "rearm_sources": [],
        "issues": {
            **{str(n): {"state": "closed"} for n in range(1, 15)},
            "54": {"state": "closed"},
            "83": {"state": "closed"},
        },
        "gate": {
            "state": "closed",
            "author_association": "OWNER",
            "created_at": "2026-10-03T10:05:00Z",
            "user": {"login": "pl0n3r"},
            "closed_by": "pl0n3r",
            "body": gate_body,
            "comments": [
                {
                    "author_association": "OWNER",
                    "user": {"login": "pl0n3r"},
                    "body": (
                        '<!-- factory-release-approval '
                        f'{{"sha":"{SHA}"}} -->'
                    ),
                }
            ],
        },
    }


def valid_v2_payload(*, gate_body=GATE_MAINTENANCE):
    payload = valid_payload(
        gate_body=gate_body,
        v1_0_0_exists=True,
    )
    payload["gate"]["closed_by"] = "github-actions[bot]"
    payload["gate"]["comments"] = [
        {
            "author_association": "OWNER",
            "user": {"login": "pl0n3r"},
            "body": "/decidir A",
        },
        {
            "author_association": "NONE",
            "user": {"login": "github-actions[bot]"},
            "body": decision_journal(gate_body),
        },
    ]
    return payload


def valid_rearmed_v2_payload(
    *,
    gate_body: str | None = None,
    sources: list[dict[str, object]] | None = None,
):
    body = gate_body or rearmed_gate_body()
    payload = valid_v2_payload(gate_body=body)
    payload["gate"]["author_association"] = "NONE"
    payload["gate"]["user"] = {"login": "github-actions[bot]"}
    payload["gate"]["created_at"] = "2026-10-03T10:05:00Z"
    payload["rearm_sources"] = (
        sources if sources is not None else [owner_source_issue()]
    )
    return payload


class ReleaseBootstrapRuntimeTests(unittest.TestCase):
    def test_owner_created_gate_remains_trusted(self):
        self.assertEqual(
            validate_payload(valid_v2_payload()),
            {"status": "ready", "sha": SHA},
        )

    def test_rearmed_bot_gate_with_owner_source_issue_is_trusted(self):
        self.assertEqual(
            validate_payload(valid_rearmed_v2_payload()),
            {"status": "ready", "sha": SHA},
        )

        chained = valid_rearmed_v2_payload(
            gate_body=rearmed_gate_body(source_issue=930),
            sources=[
                bot_source_issue(number=930, source_issue=927),
                owner_source_issue(),
            ],
        )
        self.assertEqual(
            validate_payload(chained),
            {"status": "ready", "sha": SHA},
        )

    def test_bot_gate_without_valid_rearm_origin_fails_closed(self):
        cases = {}

        missing_origin = valid_rearmed_v2_payload(
            gate_body=GATE_MAINTENANCE
        )
        cases["missing-origin"] = missing_origin

        wrong_sha = valid_rearmed_v2_payload(
            gate_body=rearmed_gate_body(sha=OTHER)
        )
        cases["wrong-sha"] = wrong_sha

        expired = valid_rearmed_v2_payload(
            gate_body=rearmed_gate_body(
                expires_at="2026-10-03T10:20:00Z"
            )
        )
        cases["expired-window"] = expired

        wrong_owner = valid_rearmed_v2_payload()
        wrong_owner["rearm_sources"][0]["user"]["login"] = "otro"
        cases["wrong-owner"] = wrong_owner

        wrong_source = valid_rearmed_v2_payload()
        wrong_source["rearm_sources"][0]["number"] = 999
        cases["wrong-source"] = wrong_source

        for name, payload in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ReleaseBootstrapError):
                    validate_payload(payload)

    def test_release_bootstrap_workflow_collects_rearm_provenance(self):
        workflow = (
            ROOT / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("/tmp/rearm-sources.json", workflow)
        self.assertIn("factory-release-rearm", workflow)
        self.assertIn("rearm_sources:$rearm_sources[0]", workflow)
        self.assertIn("created_at:$gate[0].created_at", workflow)
        self.assertIn("issues: read", workflow)

    def test_valid_first_release_candidate(self):
        self.assertEqual(
            validate_payload(valid_payload()),
            {"status": "ready", "sha": SHA},
        )

    def test_valid_maintenance_release_candidate(self):
        payload = valid_payload(
            gate_body=GATE_MAINTENANCE,
            v1_0_0_exists=True,
        )
        payload["repository"] = "pl0n3r/Factory"
        self.assertEqual(
            validate_payload(payload),
            {"status": "ready", "sha": SHA},
        )

    def test_valid_v2_maintenance_release_decision(self):
        self.assertEqual(
            validate_payload(valid_v2_payload()),
            {"status": "ready", "sha": SHA},
        )

    def test_maintenance_preflight_allows_previous_stable_v1(self):
        payload = valid_v2_payload()
        payload["v1_sha"] = OTHER
        self.assertEqual(
            validate_payload(payload),
            {"status": "ready", "sha": SHA},
        )

    def test_first_release_still_requires_v1_on_expected_sha(self):
        payload = valid_payload()
        payload["v1_sha"] = OTHER
        with self.assertRaisesRegex(
            ReleaseBootstrapError,
            "Primer bootstrap requiere v1 en el SHA exacto aprobado",
        ):
            validate_payload(payload)

    def test_v2_decision_is_bound_to_normalized_gate(self):
        payload = valid_v2_payload()
        payload["gate"]["body"] = payload["gate"]["body"].replace(
            "Publicar mantenimiento Factory v1.x",
            "Publicar Factory v1.0.15",
        )
        with self.assertRaisesRegex(
            ReleaseBootstrapError,
            "Journal v2 no corresponde al gate vigente",
        ):
            validate_payload(payload)

    def test_v2_release_target_must_match_expected_sha(self):
        stale_gate = GATE_MAINTENANCE.replace(
            f"main@{SHA}",
            f"main@{OTHER}",
        )
        with self.assertRaisesRegex(
            ReleaseBootstrapError,
            "único main@SHA",
        ):
            validate_payload(valid_v2_payload(gate_body=stale_gate))

        ambiguous_gate = GATE_MAINTENANCE.replace(
            f"main@{SHA}.",
            f"main@{SHA} y main@{OTHER}.",
        )
        with self.assertRaisesRegex(
            ReleaseBootstrapError,
            "único main@SHA",
        ):
            validate_payload(valid_v2_payload(gate_body=ambiguous_gate))

    def test_v2_negated_publish_label_fails_closed(self):
        for label in (
            "No publicar",
            "No publicar todavía",
            "Esperar para publicar",
            "No se debe publicar",
            "Republicar",
        ):
            with self.subTest(label=label):
                gate = GATE_MAINTENANCE.replace(
                    '"label":"Publicar Factory 1.0.15"',
                    f'"label":"{label}"',
                )
                with self.assertRaisesRegex(
                    ReleaseBootstrapError,
                    "inequívocamente publicación",
                ):
                    validate_payload(valid_v2_payload(gate_body=gate))

    def test_v2_release_decision_fails_closed(self):
        cases = {}

        option_b = valid_v2_payload()
        option_b["gate"]["comments"][0]["body"] = "/decidir B"
        cases["option-b"] = option_b

        unsafe_default_gate = GATE_MAINTENANCE.replace(
            '"safe_default":"B"',
            '"safe_default":"A"',
        )
        cases["unsafe-default"] = valid_v2_payload(
            gate_body=unsafe_default_gate
        )

        non_publish_gate = GATE_MAINTENANCE.replace(
            '"label":"Publicar Factory 1.0.15"',
            '"label":"Esperar"',
        )
        cases["non-publish-a"] = valid_v2_payload(
            gate_body=non_publish_gate
        )

        spoof = valid_v2_payload()
        spoof["gate"]["comments"][1]["user"]["login"] = "pl0n3r"
        spoof["gate"]["comments"][1]["author_association"] = "OWNER"
        cases["human-spoof"] = spoof

        malformed = valid_v2_payload()
        malformed["gate"]["comments"][1]["body"] = (
            '<!-- factory-human-decision {"option":"A"} -->'
        )
        cases["malformed-journal"] = malformed

        ambiguous = valid_v2_payload()
        ambiguous["gate"]["comments"].append(
            {
                "author_association": "NONE",
                "user": {"login": "github-actions[bot]"},
                "body": decision_journal(GATE_MAINTENANCE),
            }
        )
        cases["ambiguous-journal"] = ambiguous

        wrong_closer = valid_v2_payload()
        wrong_closer["gate"]["closed_by"] = "otro"
        cases["wrong-closer"] = wrong_closer

        for name, payload in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ReleaseBootstrapError):
                    validate_payload(payload)

    def test_v2_oversized_or_spoofed_evidence_fails_closed(self):
        oversized = valid_v2_payload()
        oversized["gate"]["comments"].insert(
            1,
            {
                "author_association": "OWNER",
                "user": {"login": "pl0n3r"},
                "body": "<!-- factory-human-decision " + ("x" * 21000),
            },
        )
        spoof = valid_v2_payload()
        spoof["gate"]["comments"][1]["user"]["login"] = "pl0n3r"
        spoof["gate"]["comments"][1]["author_association"] = "OWNER"
        for payload in (oversized, spoof):
            with self.assertRaises(ReleaseBootstrapError):
                validate_payload(payload)

    def test_v2_intent_cannot_fallback_to_legacy(self):
        payload = valid_payload(
            gate_body=GATE_MAINTENANCE,
            v1_0_0_exists=True,
        )
        payload["gate"]["comments"].append(
            {
                "author_association": "OWNER",
                "user": {"login": "pl0n3r"},
                "body": '<!-- factory-human-decision {"option":"A"} -->',
            }
        )
        with self.assertRaises(ReleaseBootstrapError):
            validate_payload(payload)

    def test_v2_repeated_owner_a_is_idempotent(self):
        payload = valid_v2_payload()
        payload["gate"]["comments"].insert(
            1,
            {
                "author_association": "OWNER",
                "user": {"login": "pl0n3r"},
                "body": "/decidir A",
            },
        )
        self.assertEqual(
            validate_payload(payload),
            {"status": "ready", "sha": SHA},
        )

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
            "invalid-release-state": lambda p: p.__setitem__(
                "v1_0_0_exists", "yes"
            ),
            "open-core": lambda p: p["issues"]["7"].__setitem__(
                "state", "open"
            ),
            "open-privacy": lambda p: p["issues"]["54"].__setitem__(
                "state", "open"
            ),
            "open-trust-root": lambda p: p["issues"]["83"].__setitem__(
                "state", "open"
            ),
            "open-gate": lambda p: p["gate"].__setitem__("state", "open"),
            "untrusted-gate": lambda p: p["gate"].__setitem__(
                "author_association", "NONE"
            ),
            "wrong-closer": lambda p: p["gate"].__setitem__(
                "closed_by", "otro"
            ),
            "wrong-category": lambda p: p["gate"].__setitem__(
                "body",
                GATE_FIRST.replace('"release-1.0.0"', '"money"'),
            ),
            "missing-approval": lambda p: p["gate"].__setitem__(
                "comments", []
            ),
            "wrong-approval": lambda p: p["gate"]["comments"][0].__setitem__(
                "body",
                (
                    '<!-- factory-release-approval '
                    f'{{"sha":"{OTHER}"}} -->'
                ),
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
