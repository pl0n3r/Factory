import unittest
from pathlib import Path
from unittest import mock

from scripts import bootstrap_coordination as b

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def request(key="b" * 64):
    return {"target_repository":"pl0n3r/Consumer","target_issue":"187","expected_main_sha":SHA,"governance_ref":b.GOVERNANCE_REF,"idempotency_key":key}

CALLER = """name: Coordinación\non:\n  schedule:\n    - cron: '17 * * * *'\n  workflow_dispatch:\n  pull_request:\n  issues:\n  issue_comment:\njobs:\n  comentario:\n    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1\n    with:\n      operation: comment\n"""


class FakeGateway:
    def __init__(self, *, owner=True, issue=True, main=SHA, branch=None, pr=None, same=True):
        self.owner, self.issue, self.main = owner, issue, main
        self.branch, self.pr, self.same = branch, pr, same
        self.created = []
    def authorize(self):
        if not self.owner: raise b.BootstrapError("owner")
    def repository(self, _): return None
    def issue_open(self, *_): return self.issue
    def main_sha(self, _): return self.main
    def branch_sha(self, *_): return self.branch
    def open_pr(self, *_): return self.pr
    def file_text(self, *_): return None
    def commit_matches(self, *_): return self.same
    def branch_matches(self, *_): return self.same
    def materialize(self, req, patch):
        self.created.append((req, patch, b.branch_name(req)))
        return "c" * 40, 99


class BootstrapCoordinationTests(unittest.TestCase):
    def test_request_requires_owner_main_exact_sha_and_open_issue(self):
        self.assertTrue(b.bootstrap(request(), FakeGateway(), CALLER)["created"])
        for gateway in (FakeGateway(owner=False), FakeGateway(issue=False), FakeGateway(main="c"*40)):
            with self.assertRaises(b.BootstrapError): b.bootstrap(request(), gateway, CALLER)
        for invalid in ({**request(), "target_repository":"other/x"}, {**request(), "governance_ref":"pl0n3r/factory@main"}, {**request(), "target_issue":"0"}):
            with self.assertRaises(b.BootstrapError): b.validate_request(invalid)

    def test_patch_is_path_allowlisted_and_bounded(self):
        patch=b.build_patch(CALLER); self.assertEqual(set(patch), {b.CALLER_PATH,b.TEST_PATH})
        with self.assertRaises(b.BootstrapError): b.validate_patch({"evil.txt":"x", **patch})
        with self.assertRaises(b.BootstrapError): b.validate_patch({b.CALLER_PATH:"x"*(b.MAX_FILE+1), b.TEST_PATH:"x"})
        gateway=b.GitHubGateway("token")
        with mock.patch.object(gateway,"_request",side_effect=[{"tree":{"sha":"t"}}, {"tree":[{"path":".github","mode":"120000"}]}]):
            with self.assertRaisesRegex(b.BootstrapError,"symlinks"): gateway.tree_info("pl0n3r/Consumer",SHA,set(patch))

    def test_generated_caller_uses_factory_v1_spanish_profile_only(self):
        value=b.caller_content(CALLER)
        self.assertIn("coordinacion.yml@v1",value); self.assertIn("profile: es",value)
        self.assertNotIn("@main",value); self.assertNotIn("coordinar_trabajo.py",value)
        for event in ("schedule:","workflow_dispatch:","pull_request:","issues:","issue_comment:"): self.assertIn(event,value)

    def test_bootstrap_pins_main_and_writes_only_branch_and_pr(self):
        gateway=FakeGateway(); result=b.bootstrap(request(),gateway,CALLER)
        req,patch,branch=gateway.created[0]
        self.assertEqual(req["expected_main_sha"],SHA); self.assertEqual(branch,"factory/bootstrap-coordination-187")
        self.assertTrue(set(patch).issubset(b.ALLOWED_PATHS)); self.assertEqual(result["pr"],99)
        source=(ROOT/"scripts/bootstrap_coordination.py").read_text(encoding="utf-8")
        materialize=source.split("def materialize",1)[1].split("\ndef bootstrap",1)[0]
        self.assertGreaterEqual(materialize.count("self.main_sha(name)"),3)
        self.assertNotIn('refs/heads/main',materialize)

    def test_bootstrap_is_idempotent_and_rejects_conflicting_intent(self):
        req=b.validate_request(request()); good_pr={"number":7,"body":b.marker(req)}
        same=FakeGateway(branch="c"*40,pr=good_pr,same=True)
        self.assertFalse(b.bootstrap(request(),same,CALLER)["created"])
        with self.assertRaises(b.BootstrapError): b.bootstrap(request(),FakeGateway(branch="c"*40,pr=good_pr,same=False),CALLER)
        self.assertIn("/compare/",(ROOT/"scripts/bootstrap_coordination.py").read_text(encoding="utf-8"))

    def test_workflow_reuses_existing_provision_authority_without_human_gate(self):
        text=(ROOT/".github/workflows/bootstrap-coordination.yml").read_text(encoding="utf-8")
        for value in ("workflow_dispatch:","FACTORY_PROVISION_TOKEN","github.repository_owner","contents: read","ref: v1","--caller-template governance/template/.github/workflows/coordinacion.yml"):
            self.assertIn(value,text)
        self.assertNotIn("factory-human-gate",text); self.assertNotIn("github.token",text)


if __name__ == "__main__": unittest.main()
