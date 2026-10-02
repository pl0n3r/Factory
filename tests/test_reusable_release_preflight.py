#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.reusable_release_preflight import (
    CANONICAL_CONSUMERS,
    ReusableReleasePreflightError,
    evaluate_payload,
)


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def workflow_record(path: str, content: str, repository_sha: str) -> dict[str, str]:
    raw = content.encode("utf-8")
    return {
        "path": path,
        "blob_sha": git_blob_sha(raw),
        "repository_sha": repository_sha,
        "content_b64": base64.b64encode(raw).decode("ascii"),
    }


def caller_yaml(
    reusable: str = "coordinacion.yml",
    *,
    contents: str = "read",
    issues: str = "write",
    extra_comment: str = "",
) -> str:
    return f"""name: Caller
on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  call:
    permissions:
      contents: {contents}
      issues: {issues}
    uses: pl0n3r/factory/.github/workflows/{reusable}@v1
{extra_comment}
"""


def candidate_yaml(*, contents: str = "read", issues: str = "write") -> str:
    return f"""name: Reusable
on:
  workflow_call:

permissions:
  contents: read

jobs:
  validate:
    permissions:
      contents: {contents}
      issues: {issues}
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""


def payload_for(content_by_repo: dict[str, str] | None = None) -> dict:
    content_by_repo = content_by_repo or {}
    consumers = []
    for index, repo in enumerate(sorted(CANONICAL_CONSUMERS), start=1):
        sha = f"{index:040x}"
        content = content_by_repo.get(repo, caller_yaml())
        consumers.append(
            {
                "repository": repo,
                "repository_sha": sha,
                "workflows": [
                    workflow_record(".github/workflows/caller.yml", content, sha)
                ],
            }
        )
    return {"version": 1, "factory_sha": "f" * 40, "consumers": consumers}


class ReusableReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        workflow_dir = self.root / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "coordinacion.yml").write_text(
            candidate_yaml(),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_six_consumer_callers_must_be_compatible_before_release(self):
        compatible = evaluate_payload(payload_for(), root=self.root)
        self.assertTrue(compatible["compatible"])
        self.assertEqual(compatible["status"], "COMPATIBLE")
        self.assertEqual(compatible["consumer_count"], 6)
        self.assertEqual(compatible["caller_count"], 6)

        broken = payload_for(
            {"pl0n3r/Condor": caller_yaml(issues="read")}
        )
        result = evaluate_payload(broken, root=self.root)
        self.assertFalse(result["compatible"])
        self.assertEqual(result["status"], "INCOMPATIBLE")
        self.assertEqual(
            result["incompatible"],
            [
                {
                    "repository": "pl0n3r/Condor",
                    "workflow": ".github/workflows/caller.yml",
                    "job": "call",
                    "reusable": (
                        "pl0n3r/factory/.github/workflows/coordinacion.yml@v1"
                    ),
                    "scope": "issues",
                    "required": "write",
                    "granted": "read",
                }
            ],
        )

    def test_consumer_evidence_binds_repository_workflow_and_exact_sha(self):
        base = payload_for()

        stale = copy.deepcopy(base)
        stale["consumers"][0]["workflows"][0]["repository_sha"] = "a" * 40
        with self.assertRaisesRegex(ReusableReleasePreflightError, "stale"):
            evaluate_payload(stale, root=self.root)

        forged = copy.deepcopy(base)
        forged["consumers"][0]["workflows"][0]["blob_sha"] = "b" * 40
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "blob SHA no corresponde",
        ):
            evaluate_payload(forged, root=self.root)

        wrong_path = copy.deepcopy(base)
        wrong_path["consumers"][0]["workflows"][0]["path"] = "../caller.yml"
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "workflow path inválido",
        ):
            evaluate_payload(wrong_path, root=self.root)

    def test_missing_stale_or_ambiguous_consumer_evidence_fails_closed(self):
        missing = payload_for()
        missing["consumers"].pop()
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "inventario de consumidores incompleto",
        ):
            evaluate_payload(missing, root=self.root)

        duplicate_repo = payload_for()
        duplicate_repo["consumers"][-1]["repository"] = (
            duplicate_repo["consumers"][0]["repository"]
        )
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "duplicado",
        ):
            evaluate_payload(duplicate_repo, root=self.root)

        duplicate_workflow = payload_for()
        duplicate_workflow["consumers"][0]["workflows"].append(
            copy.deepcopy(duplicate_workflow["consumers"][0]["workflows"][0])
        )
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "workflow duplicado",
        ):
            evaluate_payload(duplicate_workflow, root=self.root)

        no_factory_call = payload_for()
        repo_sha = no_factory_call["consumers"][0]["repository_sha"]
        no_factory_call["consumers"][0]["workflows"] = [
            workflow_record(
                ".github/workflows/caller.yml",
                "name: Local\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
                repo_sha,
            )
        ]
        with self.assertRaisesRegex(
            ReusableReleasePreflightError,
            "sin caller Factory@v1 verificable",
        ):
            evaluate_payload(no_factory_call, root=self.root)

    def test_incompatibility_reports_repo_workflow_and_scope_without_sensitive_payload(self):
        secret_marker = "SUPER_SECRET_SHOULD_NEVER_APPEAR"
        value = payload_for(
            {
                "pl0n3r/ControlBot": caller_yaml(
                    issues="read",
                    extra_comment=f"# {secret_marker}",
                )
            }
        )
        result = evaluate_payload(value, root=self.root)
        rendered = json.dumps(result, sort_keys=True)

        self.assertIn("pl0n3r/ControlBot", rendered)
        self.assertIn(".github/workflows/caller.yml", rendered)
        self.assertIn('"scope": "issues"', rendered)
        self.assertNotIn(secret_marker, rendered)
        self.assertEqual(
            set(result["incompatible"][0]),
            {
                "repository",
                "workflow",
                "job",
                "reusable",
                "scope",
                "required",
                "granted",
            },
        )

    def test_release_job_requires_consumer_compat_preflight_and_human_gate(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")

        for token in (
            "consumer-compat:",
            "Compatibilidad de consumidores",
            "python3 -m scripts.reusable_release_preflight",
            "raw.githubusercontent.com",
            "git/trees",
            "pl0n3r/Condor",
            "pl0n3r/ControlBot",
            "pl0n3r/FactoryRunner",
            "pl0n3r/GrindFlow",
            "pl0n3r/brvtal",
            "pl0n3r/AutoFactory",
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: [candidate-template, consumer-compat]",
            "needs: preflight",
        ):
            self.assertIn(token, workflow)

        consumer_job = workflow.split("  consumer-compat:", 1)[1].split(
            "\n  preflight:",
            1,
        )[0]
        self.assertIn("contents: read", consumer_job)
        self.assertNotIn("contents: write", consumer_job)
        self.assertNotIn("issues: write", consumer_job)


if __name__ == "__main__":
    unittest.main()
