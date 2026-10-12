"""Pruebas offline del futuro Port GitHub: observación != autoridad de release."""
import unittest

from scripts.lease_auto_release_run import run_cycle
from scripts.lease_github_port import (
    GLOBAL_SWITCH, RECENT, UNKNOWN, LeaseGithubPort, PortNotArmed,
)
from scripts.unattended_kill_switch import (
    CANONICAL_REPOSITORY_URL, CANONICAL_SOURCE_URL,
)
from test_lease_activity_collector import API as ActivityAPI, NOW, SHA


class FakeAPI(ActivityAPI):
    """Solo GET; el switch global es siempre una URL absoluta fija."""

    def __init__(self):
        super().__init__()
        self.switch_body = (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
        )
        self.switch_reads = 0
        self.pause_on_second = False
        self.fail_switch = False

    def request(self, method, path):
        assert method == "GET", "no autorizado a escribir"
        if path == GLOBAL_SWITCH:
            self.calls.append(path)
            self.switch_reads += 1
            if self.fail_switch:
                raise RuntimeError("secret-cannot-be-logged")
            if self.pause_on_second and self.switch_reads == 2:
                body = self.switch_body.replace("RUNNING", "PAUSED")
            else:
                body = self.switch_body
            return {
                "number": 767,
                "url": CANONICAL_SOURCE_URL,
                "repository_url": CANONICAL_REPOSITORY_URL,
                "user": {"login": "pl0n3r"},
                "body": body,
            }
        result = super().request(method, path)
        if "/actions/runs?branch=" in path and isinstance(result, dict):
            for run in result.get("workflow_runs", []):
                if run["id"] == 8:
                    run["event"] = "push"
                    run["created_at"] = "2026-10-11T09:55:00Z"
        return result


class LeaseGithubPortTests(unittest.TestCase):
    def test_canonical_switch_and_recent_activity_never_authorize_release(self):
        api = FakeAPI()
        port = LeaseGithubPort(api)
        result = port.inspect(21, now=NOW)
        self.assertEqual(result.state, RECENT)
        self.assertFalse(result.release_authorized)
        self.assertEqual(result.issue, 21)
        self.assertEqual(result.lease_id,
                         "e33f1859-0304-4fa8-8ce3-776de22c9707")
        self.assertEqual(result.branch_sha, SHA)
        self.assertEqual(result.last_activity_at, "2026-10-11T09:55:00Z")
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(api.calls[0], GLOBAL_SWITCH)
        self.assertEqual(api.calls[-1], GLOBAL_SWITCH)
        self.assertTrue(all(p == "/rate_limit" or
                            p.startswith("/repos/") for p in api.calls))

        # Incluso una habilitación errónea desde el caller no consigue escribir:
        # falta la prueba de AUSENCIA de actividad + CAS compartido auténtico.
        report = run_cycle(
            [21], port, feature_enabled=True, dry_run=False,
            mutations_authorized=True,
        )
        self.assertEqual(report.results[0][1].action, UNKNOWN.lower())
        self.assertFalse(report.results[0][1].wrote)
        self.assertEqual(report.results[0][1].write_state, "unknown")
        self.assertTrue(all(p == "/rate_limit" or
                            p.startswith("/repos/") for p in api.calls))

    def test_global_pause_invalid_json_and_recheck_race_fail_closed(self):
        for marker in (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","state":"RUNNING",'
            '"owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"RUNNING","owner":"other",'
            '"owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch invalid -->',
            "",
        ):
            with self.subTest(marker=marker[:30]):
                api = FakeAPI()
                api.switch_body = marker
                result = LeaseGithubPort(api).inspect(21, now=NOW)
                self.assertEqual(result.state, UNKNOWN)
                self.assertFalse(result.release_authorized)
                self.assertEqual(api.switch_reads, 1)
        api = FakeAPI()
        api.pause_on_second = True
        self.assertEqual(LeaseGithubPort(api).inspect(21, now=NOW).state,
                         UNKNOWN)
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(LeaseGithubPort(FakeAPI()).inspect(True, now=NOW).state,
                         UNKNOWN)

    def test_partial_pages_403_429_and_ref_race_fail_closed(self):
        cases = []
        a = FakeAPI(); a.fail_switch = True; cases.append(a)
        a = FakeAPI(); a.block = "/issues/21/comments"; cases.append(a)
        a = FakeAPI(); a.remaining = 19; cases.append(a)
        a = FakeAPI(); a.issue["comments"] = 500; cases.append(a)
        a = FakeAPI(); a.runs_count_override = 2; cases.append(a)
        a = FakeAPI(); a.race = True; cases.append(a)
        a = FakeAPI(); a.repo_id = None; cases.append(a)
        a = FakeAPI(); a.comments[0]["user"]["type"] = "User"; cases.append(a)
        a = FakeAPI(); a.checks[0]["head_sha"] = "b" * 40; cases.append(a)
        for index, api in enumerate(cases):
            with self.subTest(case=index):
                observed = LeaseGithubPort(api).inspect(21, now=NOW)
                self.assertEqual(observed.state, UNKNOWN)
                self.assertFalse(observed.release_authorized)
                self.assertIsNone(observed.lease_id)
                self.assertTrue(all(p == "/rate_limit" or
                                    p.startswith("/repos/") for p in api.calls))
                self.assertNotIn("secret-cannot-be-logged", str(observed))

    def test_mutating_port_surface_denied_even_with_fake_evidence(self):
        api = FakeAPI()
        port = LeaseGithubPort(api)
        blocked_calls = [
            lambda: port.read(21),
            lambda: port.lock("factory-coordination-123"),
            lambda: port.append(21, "synthetic", None),
            lambda: port.status(21, "estado: disponible", None),
            lambda: port.recovery_note(21, None),
            lambda: port.recovery_label(21, None),
        ]
        for call in blocked_calls:
            with self.subTest(action=blocked_calls.index(call)):
                with self.assertRaises(PortNotArmed):
                    call()
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
