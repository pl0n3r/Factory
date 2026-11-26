"""Deterministic offline fixtures; no GitHub access or publisher."""
import copy
import unittest
from unittest.mock import patch

from scripts.dispatch_observed_inventory import proposal_from_observation
from scripts.salud_cola_global_observar import fingerprint
from scripts.salud_cola_github import REPOSITORIES, require_stable_github_sweeps
from scripts.salud_cola_snapshot import STATES
from scripts.unattended_kill_switch import CANONICAL_SOURCE_URL, CANONICAL_REPOSITORY_URL

CHECKOUT, POLICY = "a" * 40, "b" * 64
START = "2026-01-01T00:00:00+00:00"
END = "2026-01-01T00:00:10+00:00"
NOW = "2026-01-01T00:00:20+00:00"


def fixture():
    obs = {"version": 1, "scope": list(REPOSITORIES), "policy_sha": CHECKOUT,
           "started_at": START, "finished_at": END, "writes": 0, "authority": "unchanged",
           "capacity": None, "counts": {}, "fingerprints": {}, "status": "OBSERVED_GLOBAL_ONLY",
           "reason": "capacity_not_observed", "open_total": 2, "available_total": 1,
           "blocked_causes": dict.fromkeys(("dependency", "claims", "human_gate", "planned", "unknown"), 0)}
    evidence = {"repositories": {}, "candidates": {}, "rate_limit": {"limit": 5000, "remaining": 4000},
                "seen_idempotency_keys": [], "kill_switch_observed_at": END, "kill_switch_issue": {
                    "number": 767, "url": CANONICAL_SOURCE_URL, "repository_url": CANONICAL_REPOSITORY_URL,
                    "state": "closed", "user": {"login": "pl0n3r"},
                    "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
                }}
    for identity, repo in enumerate(REPOSITORIES, 1):
        items = []
        counts = dict.fromkeys(STATES, 0)
        leases = {}
        if repo == "Factory":
            items = [{"number": 1, "state": "open", "labels": [{"name": "estado: disponible"}]},
                     {"number": 2, "state": "open", "labels": [{"name": "estado: reservado"}]}]
            counts.update(available=1, reserved=1)
            leases = {"Factory#2": {"claims": ["scripts/other.py"], "verified": True}}
        pages = [{"request_url": f"https://api.github.com/repos/pl0n3r/{repo}/issues?state=open&per_page=100&page=1",
                  "status_code": 200, "link_header": None, "payload": items}]
        digest = fingerprint([identity, require_stable_github_sweeps(repo, pages, pages)])
        obs["counts"][repo], obs["fingerprints"][repo] = counts, digest
        evidence["repositories"][repo] = {"identity": identity, "first": pages,
            "second": copy.deepcopy(pages), "leases": leases, "observed_at": END}
    row = {"key": "Factory#1", "repository_ref": "pl0n3r/Factory", "priority": "high",
           "dependencies_open": [], "incompatible_reservation": False, "pending_human_gate": False,
           "claims": ["scripts/work.py"], "active_claims": ["scripts/other.py"],
           "requires_extra_authority": False, "idempotency_key": "Factory#1-v1",
           "policy_verified": True, "evidence_verified": True}
    evidence["candidates"]["Factory#1"] = {
        "candidate": row, "task": {"key": "Factory#1", "repository_ref": "pl0n3r/Factory",
            "priority": "high", "claims": ["scripts/work.py"], "depends_on": ["Factory#3"]},
        "dependency_states": {"Factory#3": "completed"}, "observed_at": END,
        "policy_sha": POLICY, "checkout_sha": CHECKOUT, "fingerprint": obs["fingerprints"]["Factory"],
    }
    return obs, evidence


class ObservedInventoryTests(unittest.TestCase):
    def evaluate(self, obs, evidence, **kwargs):
        return proposal_from_observation(obs, evidence, **{
            "checkout_sha": CHECKOUT, "policy_sha": POLICY, "now": NOW, **kwargs
        })

    def assert_unknown(self, obs, evidence, **kwargs):
        result = self.evaluate(obs, evidence, **kwargs)
        self.assertEqual(result["decision"], "UNKNOWN")
        self.assertIsNone(result["order_proposal"])
        self.assertEqual(result["sent_count"], 0)
        self.assertEqual(result["execution"], "OFFLINE_ONLY")

    def test_proposal_and_replay_use_existing_selector(self):
        obs, evidence = fixture()
        from scripts.dispatch_inventory import offline_proposal_from_snapshot
        with patch("scripts.dispatch_observed_inventory.offline_proposal_from_snapshot",
                   wraps=offline_proposal_from_snapshot) as selector:
            result = self.evaluate(obs, evidence)
            selector.assert_called_once()
        self.assertEqual(result["decision"], "PROPOSED")
        order = result["order_proposal"]
        self.assertEqual(order["kind"], "OFFLINE_PROPOSAL")
        self.assertEqual(order["work_id"], "Factory#1")
        self.assertFalse(order["executed"])
        self.assertEqual(result["sent_count"], 0)
        self.assertEqual(result["authority"], "snapshot_only_not_verified_for_live")
        evidence["seen_idempotency_keys"] = [order["idempotency_key"]]
        replay = self.evaluate(obs, evidence)
        self.assertEqual(replay["decision"], "REPLAY")
        self.assertIsNone(replay["order_proposal"])

    def test_missing_stale_or_drifting_evidence(self):
        for case in ("missing_repo", "missing_candidate", "missing_lease", "drift",
                     "identity", "fingerprint", "counts", "policy", "paused", "unknown_switch",
                     "stale_candidate", "future_candidate", "quota", "unknown_census",
                     "stale_switch", "boolean_count", "duplicate_identity"):
            with self.subTest(case=case):
                obs, evidence = fixture()
                source = evidence["repositories"]["Factory"]
                item = evidence["candidates"]["Factory#1"]
                if case == "missing_repo":
                    del evidence["repositories"]["Condor"]
                elif case == "missing_candidate":
                    evidence["candidates"].clear()
                elif case == "missing_lease":
                    source["leases"].clear()
                elif case == "drift":
                    source["second"][0]["payload"][0]["number"] = 7
                elif case == "identity":
                    source["identity"] += 1
                elif case == "fingerprint":
                    item["fingerprint"] = "c" * 64
                elif case == "counts":
                    obs["counts"]["Factory"]["available"] = 2
                elif case == "policy":
                    item["policy_sha"] = "c" * 64
                elif case == "paused":
                    switch = evidence["kill_switch_issue"]
                    switch["body"] = switch["body"].replace("RUNNING", "PAUSED")
                elif case == "unknown_switch":
                    evidence["kill_switch_issue"]["state"] = "open"
                elif case == "stale_candidate":
                    item["observed_at"] = START
                elif case == "future_candidate":
                    item["observed_at"] = "2026-01-01T00:01:00+00:00"
                elif case == "stale_switch":
                    evidence["kill_switch_observed_at"] = START
                elif case == "boolean_count":
                    obs["counts"]["Factory"]["available"] = True
                elif case == "duplicate_identity":
                    other = evidence["repositories"]["Condor"]
                    other["identity"] = source["identity"]
                    obs["fingerprints"]["Condor"] = fingerprint([other["identity"],
                        require_stable_github_sweeps("Condor", other["first"], other["second"])])
                elif case == "quota":
                    evidence["rate_limit"]["remaining"] = 0
                else:
                    obs["status"] = "UNKNOWN"
                self.assert_unknown(obs, evidence)
        obs, evidence = fixture()
        self.assert_unknown(obs, evidence, now="2026-01-01T00:05:00+00:00")
        self.assert_unknown(obs, evidence, checkout_sha="d" * 40)

    def test_candidate_claims_dependencies_and_gates_fail_closed(self):
        for case in ("identity", "claims", "active_claims", "overlap", "dependency",
                     "dependency_missing", "dependency_contradiction", "human", "reservation",
                     "authority", "unverified", "malformed"):
            with self.subTest(case=case):
                obs, evidence = fixture()
                item = evidence["candidates"]["Factory#1"]
                row = item["candidate"]
                if case == "identity":
                    row["repository_ref"] = "pl0n3r/Condor"
                elif case == "claims":
                    row["claims"] = ["scripts/different.py"]
                elif case == "active_claims":
                    row["active_claims"] = []
                elif case == "overlap":
                    row["claims"] = item["task"]["claims"] = ["scripts/other.py"]
                elif case == "dependency":
                    item["task"]["depends_on"] = ["Factory#2"]
                    item["dependency_states"] = {"Factory#2": "open"}
                    row["dependencies_open"] = ["Factory#2"]
                elif case == "dependency_contradiction":
                    item["task"]["depends_on"] = ["Factory#2"]
                    item["dependency_states"] = {"Factory#2": "completed"}
                elif case == "dependency_missing":
                    item["dependency_states"].clear()
                elif case == "human":
                    row["pending_human_gate"] = True
                elif case == "reservation":
                    row["incompatible_reservation"] = True
                elif case == "authority":
                    row["requires_extra_authority"] = True
                elif case == "unverified":
                    row["evidence_verified"] = False
                else:
                    row["pending_human_gate"] = None
                self.assert_unknown(obs, evidence)


if __name__ == "__main__":
    unittest.main()
