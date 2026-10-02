#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.reusable_release_preflight as target
from scripts.reusable_release_preflight import CONSUMERS, PreflightError, collect_inventory, evaluate_inventory

CALLER = """name: Caller
jobs:
  call:
    permissions:
      contents: read
      issues: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
"""
CANDIDATE = """name: Reusable
on:
  workflow_call:
jobs:
  run:
    permissions:
      contents: read
      issues: write
    runs-on: ubuntu-latest
"""

def inventory(caller=CALLER):
    return [{
        "repository": repo, "repository_sha": f"{n:040x}",
        "workflows": [{
            "path": ".github/workflows/caller.yml",
            "blob_sha": f"{n + 20:040x}",
            "content": caller,
        }],
    } for n, repo in enumerate(CONSUMERS, 1)]


class FakeResponse:
    def __init__(self, status=200, payload=b"{}"):
        self.status = status
        self.payload = payload

    def read(self, amount=None):
        return self.payload if amount is None else self.payload[:amount]


class FakeConnection:
    instances = []
    response = FakeResponse()

    def __init__(self, host, timeout):
        self.host = host
        self.timeout = timeout
        self.closed = False
        self.request_args = None
        self.__class__.instances.append(self)

    def request(self, *args, **kwargs):
        self.request_args = (args, kwargs)

    def getresponse(self):
        return self.__class__.response

    def close(self):
        self.closed = True

class ReusableReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = self.root / ".github/workflows"
        path.mkdir(parents=True)
        (path / "coordinacion.yml").write_text(CANDIDATE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_six_consumer_callers_must_be_compatible_before_release(self):
        ok = evaluate_inventory(inventory(), "f" * 40, self.root)
        self.assertEqual((ok["compatible"], ok["consumer_count"], ok["caller_count"]), (True, 6, 6))
        self.assertEqual(
            {row["repository"] for row in ok["consumers"]},
            set(CONSUMERS),
        )
        self.assertTrue(all(row["callers"] == 1 for row in ok["consumers"]))
        broken = inventory()
        broken[0]["workflows"][0]["content"] = CALLER.replace("issues: write", "issues: read")
        result = evaluate_inventory(broken, "f" * 40, self.root)
        self.assertFalse(result["compatible"])
        self.assertEqual(result["incompatible"][0]["scope"], "issues")

    def test_consumer_evidence_binds_repository_workflow_and_exact_sha(self):
        raw, calls = CALLER.encode(), {}
        def getter(path):
            parts = path.split("/")
            repo = "/".join(parts[2:4])
            if path == f"/repos/{repo}":
                return {"default_branch": "main"}
            if "/commits/main" in path:
                calls[repo] = calls.get(repo, 0) + 1
                return {"sha": "a" * 40}
            if "/git/trees/" in path:
                return {"truncated": False, "tree": [
                    {"type": "blob", "path": ".github/workflows/caller.yml", "sha": "b" * 40}
                ]}
            self.fail(path)
        rows = collect_inventory(getter, lambda _: raw)
        self.assertEqual({r["repository"] for r in rows}, set(CONSUMERS))
        self.assertTrue(all(calls[r] == 2 for r in CONSUMERS))
        n = {"value": 0}
        def stale(path):
            value = getter(path)
            if "/commits/main" in path and "Condor" in path:
                n["value"] += 1
                return {"sha": ("a" if n["value"] == 1 else "b") * 40}
            return value
        raw_reader = lambda _: raw
        with self.assertRaisesRegex(PreflightError, "stale"):
            collect_inventory(stale, raw_reader)

    def test_missing_stale_or_ambiguous_consumer_evidence_fails_closed(self):
        with self.assertRaisesRegex(PreflightError, "incompleto"):
            evaluate_inventory(inventory()[:-1], "f" * 40, self.root)
        duplicate = inventory()
        duplicate[-1]["repository"] = duplicate[0]["repository"]
        with self.assertRaisesRegex(PreflightError, "duplicado"):
            evaluate_inventory(duplicate, "f" * 40, self.root)
        no_call = inventory()
        no_call[0]["workflows"][0]["content"] = "name: Local\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        with self.assertRaisesRegex(PreflightError, "sin caller Factory@v1"):
            evaluate_inventory(no_call, "f" * 40, self.root)

        unrelated = inventory()
        unrelated[0]["workflows"].append({
            "path": ".github/workflows/unrelated.yml",
            "blob_sha": "a" * 40,
            "content": "name: Unrelated\npermissions: read-all\nnot-even-jobs: true\n",
        })
        self.assertTrue(
            evaluate_inventory(unrelated, "f" * 40, self.root)["compatible"]
        )

        dynamic = inventory()
        dynamic_content = CALLER.replace(
            "@v1",
            "@${{github.ref_name}}",
        )
        dynamic[0]["workflows"].append({
            "path": ".github/workflows/dynamic.yml",
            "blob_sha": "c" * 40,
            "content": dynamic_content,
        })
        with self.assertRaisesRegex(PreflightError, "referencia Factory ambigua"):
            evaluate_inventory(dynamic, "f" * 40, self.root)

    def test_incompatibility_reports_repo_workflow_and_scope_without_sensitive_payload(self):
        broken = inventory()
        broken[1]["workflows"][0]["content"] = CALLER.replace(
            "issues: write", "issues: read\n    # SUPER_SECRET_SHOULD_NEVER_APPEAR"
        )
        rendered = json.dumps(evaluate_inventory(broken, "f" * 40, self.root))
        for expected in ("pl0n3r/ControlBot", ".github/workflows/caller.yml", '"scope": "issues"'):
            self.assertIn(expected, rendered)
        self.assertNotIn("SUPER_SECRET_SHOULD_NEVER_APPEAR", rendered)

    def test_release_job_requires_consumer_compat_preflight_and_human_gate(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release-bootstrap.yml").read_text()
        for token in ("consumer-compat:", "python3 -m scripts.reusable_release_preflight",
                      "workflow_dispatch:", "expected_sha:", "gate_issue:",
                      "needs: [candidate-template, consumer-compat]", "needs: preflight"):
            self.assertIn(token, workflow)
        job = workflow.split("  consumer-compat:", 1)[1].split("\n  release:", 1)[0]
        self.assertIn("contents: read", job)
        self.assertNotIn("contents: write", job)

    def test_network_clients_pin_github_hosts_and_fail_closed(self):
        FakeConnection.instances = []
        FakeConnection.response = FakeResponse(payload=b'{"ok": true}')
        with patch.object(target, "HTTPSConnection", FakeConnection):
            self.assertEqual(target._github_json("/repos/pl0n3r/Factory"), {"ok": True})
        self.assertEqual(FakeConnection.instances[-1].host, target.API_HOST)
        self.assertTrue(FakeConnection.instances[-1].closed)

        FakeConnection.response = FakeResponse(payload=b"workflow")
        with patch.object(target, "HTTPSConnection", FakeConnection):
            self.assertEqual(
                target._github_bytes("/pl0n3r/Factory/a/.github/workflows/ci.yml"),
                b"workflow",
            )
        self.assertEqual(FakeConnection.instances[-1].host, target.RAW_HOST)

        FakeConnection.response = FakeResponse(status=500)
        with patch.object(target, "HTTPSConnection", FakeConnection):
            with self.assertRaisesRegex(PreflightError, "ilegible"):
                target._github_json("/repos/pl0n3r/Factory")

    def test_inventory_rejects_malformed_tree_and_workflow_content(self):
        def truncated(path):
            if path.endswith("/Condor"):
                return {"default_branch": "main"}
            if "/commits/main" in path:
                return {"sha": "a" * 40}
            return {"truncated": True, "tree": []}
        with self.assertRaisesRegex(PreflightError, "truncado"):
            collect_inventory(truncated, lambda _: b"")

        def oversized(path):
            if path.endswith("/Condor"):
                return {"default_branch": "main"}
            if "/commits/main" in path:
                return {"sha": "a" * 40}
            if "/git/trees/" in path:
                return {"truncated": False, "tree": [
                    {"type": "blob", "path": ".github/workflows/caller.yml", "sha": "b" * 40}
                ]}
            self.fail(path)
        with self.assertRaisesRegex(PreflightError, "demasiado grande"):
            collect_inventory(oversized, lambda _: b"x" * 300_001)

    def test_parser_rejects_tabs_unknown_permissions_and_ambiguous_factory_refs(self):
        with self.assertRaisesRegex(PreflightError, "tabs"):
            target._jobs("jobs:\n\tcall:\n    runs-on: ubuntu-latest\n", "tabbed")

        invalid_candidate = CANDIDATE.replace("issues: write", "issues: admin")
        (self.root / ".github/workflows/coordinacion.yml").write_text(invalid_candidate)
        with self.assertRaisesRegex(PreflightError, "desconocido"):
            evaluate_inventory(inventory(), "f" * 40, self.root)

        ambiguous = inventory()
        ambiguous[0]["workflows"][0]["content"] = CALLER.replace("@v1", "@${{ inputs.ref }}")
        with self.assertRaisesRegex(PreflightError, "ambigua"):
            evaluate_inventory(ambiguous, "f" * 40, self.root)

    def test_main_returns_success_and_fail_closed(self):
        good = evaluate_inventory(inventory(), "f" * 40, self.root)
        with patch.object(target, "collect_inventory", return_value=inventory()), \
             patch.object(target, "evaluate_inventory", return_value=good), \
             patch.object(target.sys, "argv", ["preflight", "--factory-sha", "f" * 40]), \
             patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(target.main(), 0)
            self.assertIn('"compatible": true', stdout.getvalue())

        with patch.object(target, "collect_inventory", side_effect=PreflightError("boom")), \
             patch.object(target.sys, "argv", ["preflight", "--factory-sha", "f" * 40]), \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(target.main(), 2)
            self.assertIn("ERROR: boom", stderr.getvalue())

if __name__ == "__main__":
    unittest.main()
