#!/usr/bin/env python3
import hashlib, json, tempfile, unittest
from pathlib import Path
from urllib.parse import urlparse
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

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def inventory(caller=CALLER):
    raw = caller.encode()
    return [{
        "repository": repo, "repository_sha": f"{n:040x}",
        "workflows": [{"path": ".github/workflows/caller.yml", "blob_sha": blob(raw), "content": caller}],
    } for n, repo in enumerate(CONSUMERS, 1)]

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
        broken = inventory()
        broken[0]["workflows"][0]["content"] = CALLER.replace("issues: write", "issues: read")
        result = evaluate_inventory(broken, "f" * 40, self.root)
        self.assertFalse(result["compatible"])
        self.assertEqual(result["incompatible"][0]["scope"], "issues")

    def test_consumer_evidence_binds_repository_workflow_and_exact_sha(self):
        raw, digest, calls = CALLER.encode(), blob(CALLER.encode()), {}
        def getter(url):
            parts = urlparse(url).path.split("/")
            repo = "/".join(parts[2:4])
            if url.endswith(f"/repos/{repo}"):
                return {"default_branch": "main"}
            if "/commits/main" in url:
                calls[repo] = calls.get(repo, 0) + 1
                return {"sha": "a" * 40}
            if "/git/trees/" in url:
                return {"truncated": False, "tree": [
                    {"type": "blob", "path": ".github/workflows/caller.yml", "sha": digest}
                ]}
            self.fail(url)
        rows = collect_inventory(getter, lambda _: raw)
        self.assertEqual({r["repository"] for r in rows}, set(CONSUMERS))
        self.assertTrue(all(calls[r] == 2 for r in CONSUMERS))
        n = {"value": 0}
        def stale(url):
            value = getter(url)
            if "/commits/main" in url and "Condor" in url:
                n["value"] += 1
                return {"sha": ("a" if n["value"] == 1 else "b") * 40}
            return value
        with self.assertRaisesRegex(PreflightError, "stale"):
            collect_inventory(stale, lambda _: raw)

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

if __name__ == "__main__":
    unittest.main()
