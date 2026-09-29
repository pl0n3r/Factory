import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock

from scripts import bootstrap_coordination as b

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def request(key="b" * 64):
    return {"target_repository":"pl0n3r/Consumer","target_issue":"187","expected_main_sha":SHA,"governance_ref":b.GOVERNANCE_REF,"idempotency_key":key}

CALLER = """name: Coordinación\non:\n  schedule:\n    - cron: '17 * * * *'\n  workflow_dispatch:\n  pull_request:\n  issues:\n  issue_comment:\njobs:\n  comentario:\n    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1\n    with:\n      operation: comment\n  pr:\n    if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository\n    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1\n    with:\n      operation: pr\n  validar-pr:\n    if: github.event_name == 'pull_request'\n    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1\n    with:\n      operation: validate\n      require_reservation: true\n"""

def generated_validation_runs(value, *, event_name="pull_request", ref, head_repo, repository, association):
    block=value.split("  validar-pr:",1)[1].split("    uses:",1)[0]
    expression=" ".join(
        line.strip()
        for line in block.splitlines()
        if line.strip() and line.strip() != "if: >-"
    )
    atoms={
        "github.event_name == 'pull_request'": event_name == "pull_request",
        "startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')": ref.startswith("factory/bootstrap-coordination-"),
        "github.event.pull_request.head.repo.full_name == github.repository": head_repo == repository,
        "github.event.pull_request.author_association == 'OWNER'": association == "OWNER",
    }
    for atom,result in atoms.items():
        expression=expression.replace(atom,str(result))
    expression=expression.replace("&&"," and ").replace("!(","not (")
    if "github." in expression or "startsWith(" in expression:
        raise AssertionError(f"Expresión no evaluada completamente: {expression}")
    return bool(eval(expression, {"__builtins__": {}}, {}))


class FakeGateway:
    def __init__(self, *, owner=True, issue=True, main=SHA, branch=None, pr=None, same=True):
        self.owner, self.issue, self.main = owner, issue, main
        self.branch, self.pr, self.same = branch, pr, same
        self.created, self.deleted = [], []
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
    def pr_matches(self, *_): return self.same
    def delete_branch(self, _, branch): self.deleted.append(branch)
    def create_pr(self, _, branch, __, ___): self.created.append(("pr",branch)); return 98
    def materialize(self, req, patch):
        self.created.append((req, patch, b.branch_name(req)))
        return "c" * 40, 99
    def materialize_replacement(self, req, patch, branch, legacy_branch, legacy_sha, legacy_pr):
        self.created.append(("replacement",req,patch,branch,legacy_branch,legacy_sha,legacy_pr))
        return "d" * 40, 100


class BootstrapCoordinationTests(unittest.TestCase):
    def test_request_requires_owner_main_exact_sha_and_open_issue(self):
        self.assertTrue(b.bootstrap(request(), FakeGateway(), CALLER)["created"])
        raw=request()
        for gateway in (FakeGateway(owner=False), FakeGateway(issue=False), FakeGateway(main="c"*40)):
            with self.assertRaises(b.BootstrapError): b.bootstrap(raw, gateway, CALLER)
        for invalid in ({**request(), "target_repository":"other/x"}, {**request(), "governance_ref":"pl0n3r/factory@main"}, {**request(), "target_issue":"0"}):
            with self.assertRaises(b.BootstrapError): b.validate_request(invalid)

    def test_patch_is_path_allowlisted_and_bounded(self):
        patch=b.build_patch(CALLER); self.assertEqual(set(patch), {b.CALLER_PATH,b.TEST_PATH})
        with self.assertRaises(b.BootstrapError): b.validate_patch({"evil.txt":"x", **patch})
        with self.assertRaises(b.BootstrapError): b.validate_patch({b.CALLER_PATH:"x"*(b.MAX_FILE+1), b.TEST_PATH:"x"})
        gateway=b.GitHubGateway("token"); paths=set(patch)
        with mock.patch.object(gateway,"_request",side_effect=[{"tree":{"sha":"t"}}, {"tree":[{"path":".github","mode":"120000"}]}]):
            with self.assertRaisesRegex(b.BootstrapError,"symlinks"): gateway.tree_info("pl0n3r/Consumer",SHA,paths)

    def test_generated_caller_uses_factory_v1_spanish_profile_only(self):
        value=b.caller_content(CALLER)
        self.assertIn("coordinacion.yml@v1",value); self.assertIn("profile: es",value)
        self.assertNotIn("@main",value); self.assertNotIn("coordinar_trabajo.py",value)
        for event in ("schedule:","workflow_dispatch:","pull_request:","issues:","issue_comment:"): self.assertIn(event,value)

    def test_generated_caller_skips_validation_only_for_owner_same_repo_bootstrap(self):
        value=b.caller_content(CALLER)
        block=value.split("  validar-pr:",1)[1]
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')",block)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository",block)
        self.assertIn("github.event.pull_request.author_association == 'OWNER'",block)
        self.assertEqual(value.count("factory/bootstrap-coordination-"),1)

    def test_generated_caller_keeps_validation_for_regular_and_untrusted_prefixed_prs(self):
        value=b.caller_content(CALLER)
        repo="pl0n3r/Consumer"
        cases=(
            ("trabajo/issue-123",repo,"OWNER",True),
            ("factory/bootstrap-coordination-187",repo,"MEMBER",True),
            ("factory/bootstrap-coordination-187",repo,"COLLABORATOR",True),
            ("factory/bootstrap-coordination-187","fork/Consumer","OWNER",True),
            ("factory/bootstrap-coordination-187",repo,"OWNER",False),
        )
        for ref,head_repo,association,expected_validation in cases:
            with self.subTest(ref=ref,head_repo=head_repo,association=association):
                self.assertEqual(
                    generated_validation_runs(
                        value,
                        ref=ref,
                        head_repo=head_repo,
                        repository=repo,
                        association=association,
                    ),
                    expected_validation,
                )

    def test_generated_caller_keeps_require_reservation_true(self):
        value=b.caller_content(CALLER)
        block=value.split("  validar-pr:",1)[1]
        self.assertIn("operation: validate",block)
        self.assertIn("require_reservation: true",block)

    def test_generated_caller_keeps_pr_sync_for_same_repo_bootstrap_branch(self):
        value=b.caller_content(CALLER)
        pr_block=value.split("  pr:",1)[1].split("  validar-pr:",1)[0]
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository",pr_block)
        self.assertIn("operation: pr",pr_block)
        self.assertNotIn("factory/bootstrap-coordination-",pr_block)

    def test_generated_caller_remains_pinned_and_permission_bounded(self):
        value=b.caller_content(CALLER)
        self.assertIn("coordinacion.yml@v1",value)
        self.assertNotIn("@main",value)
        self.assertNotIn("coordinar_trabajo.py",value)

    def test_grindflow_188_bootstrap_branch_does_not_self_block(self):
        value=b.caller_content(CALLER)
        validation=value.split("  validar-pr:",1)[1]
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-')",validation)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository",validation)
        self.assertIn("github.event.pull_request.author_association == 'OWNER'",validation)
        self.assertIn("require_reservation: true",validation)

    def test_untrusted_bootstrap_prefix_does_not_bypass_validation(self):
        value=b.caller_content(CALLER)
        repo="pl0n3r/Consumer"
        for head_repo,association in (
            (repo,"MEMBER"),
            (repo,"COLLABORATOR"),
            ("fork/Consumer","OWNER"),
            ("fork/Consumer","MEMBER"),
        ):
            with self.subTest(head_repo=head_repo,association=association):
                self.assertTrue(
                    generated_validation_runs(
                        value,
                        ref="factory/bootstrap-coordination-187",
                        head_repo=head_repo,
                        repository=repo,
                        association=association,
                    )
                )
        self.assertFalse(
            generated_validation_runs(
                value,
                ref="factory/bootstrap-coordination-187",
                head_repo=repo,
                repository=repo,
                association="OWNER",
            )
        )

    def test_bootstrap_pins_main_and_writes_only_branch_and_pr(self):
        gateway=FakeGateway(); result=b.bootstrap(request(),gateway,CALLER)
        req,patch,branch=gateway.created[0]
        self.assertEqual(req["expected_main_sha"],SHA); self.assertEqual(branch,"factory/bootstrap-coordination-187")
        self.assertTrue(set(patch).issubset(b.ALLOWED_PATHS)); self.assertEqual(result["pr"],99)

    def test_bootstrap_is_idempotent_and_rejects_conflicting_intent(self):
        req=b.validate_request(request()); good_pr={"number":7,"body":b.marker(req)}
        same=FakeGateway(branch="c"*40,pr=good_pr,same=True)
        self.assertFalse(b.bootstrap(request(),same,CALLER)["created"])
        raw=request(); conflict=FakeGateway(branch="c"*40,pr=good_pr,same=False)
        with self.assertRaises(b.BootstrapError): b.bootstrap(raw,conflict,CALLER)
        stale=FakeGateway(main="d"*40,branch="c"*40,pr=None,same=True)
        patch=b.build_patch(CALLER); branch=b.branch_name(req)
        with self.assertRaises(b.BootstrapError): b.reuse_existing(req,stale,patch,b.legacy_patch(CALLER),branch,stale.branch,None)
        self.assertEqual(stale.deleted,[branch])


    def _legacy_pr(self, req, branch, number=188):
        return {
            "number":number,
            "state":"open",
            "body":b.marker(req),
            "base":{"ref":"main"},
            "head":{"ref":branch,"repo":{"full_name":req["target_repository"]}},
        }

    def _legacy_upgrade_gateway(self):
        req=b.validate_request(request())
        patch=b.build_patch(CALLER)
        legacy=b.legacy_patch(CALLER)
        branch=b.branch_name(req)
        old_sha="c"*40
        legacy_pr=self._legacy_pr(req,branch)
        gateway=FakeGateway(branch=old_sha,pr=legacy_pr,same=True)
        replacement=b.replacement_branch_name(req,patch)
        return req,patch,legacy,branch,old_sha,legacy_pr,replacement,gateway

    def test_same_intent_stale_generated_patch_can_be_upgraded(self):
        req,patch,legacy,branch,old_sha,legacy_pr,replacement,gateway=self._legacy_upgrade_gateway()
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: old_sha if v==branch else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch):
            result=b.bootstrap(request(),gateway,CALLER)
        self.assertEqual(result,{"status":"confirmed","branch":replacement,"pr":100,"created":True})
        replacements=[row for row in gateway.created if row[0]=="replacement"]
        self.assertEqual(len(replacements),1)
        self.assertEqual(replacements[0][3],replacement)
        self.assertEqual(gateway.deleted,[])

    def test_upgrade_rejects_tampered_or_conflicting_existing_branch(self):
        req,patch,legacy,branch,old_sha,legacy_pr,_,gateway=self._legacy_upgrade_gateway()
        with mock.patch.object(gateway,"branch_sha",return_value=old_sha), \
             mock.patch.object(gateway,"open_pr",return_value=legacy_pr), \
             mock.patch.object(gateway,"branch_matches",return_value=False):
            with self.assertRaisesRegex(b.BootstrapError,"otra intención"):
                b.bootstrap(request(),gateway,CALLER)
        self.assertEqual(gateway.created,[])

    def test_upgrade_aborts_on_remote_head_drift(self):
        gateway=b.GitHubGateway("token")
        req=b.validate_request(request())
        patch=b.build_patch(CALLER)
        legacy_branch=b.branch_name(req)
        replacement=b.replacement_branch_name(req,patch)
        legacy_sha="c"*40
        for changed in ("d"*40,SHA,"e"*40):
            calls=[]
            def api(method,path,payload=None,allow=()):
                calls.append((method,path))
                if "/git/blobs" in path: return {"sha":"b"*40}
                if "/git/trees" in path: return {"sha":"t"*40}
                if "/git/commits" in path: return {"sha":"f"*40}
                return {}
            with self.subTest(changed=changed), \
                 mock.patch.object(gateway,"tree_info",return_value="base"), \
                 mock.patch.object(gateway,"_request",side_effect=api), \
                 mock.patch.object(gateway,"main_sha",return_value=SHA), \
                 mock.patch.object(gateway,"branch_sha",side_effect=[legacy_sha,changed]):
                with self.assertRaisesRegex(b.BootstrapError,"cambió"):
                    gateway.materialize_replacement(req,patch,replacement,legacy_branch,legacy_sha,188)
            self.assertFalse(any(method=="POST" and "/git/refs" in path for method,path in calls))

    def test_upgrade_uses_only_canonical_template_and_allowlist(self):
        req=b.validate_request(request())
        patch=b.build_patch(CALLER)
        legacy=b.legacy_patch(CALLER)
        self.assertEqual(set(patch),{b.CALLER_PATH,b.TEST_PATH})
        self.assertEqual(set(legacy),{b.CALLER_PATH,b.TEST_PATH})
        self.assertNotEqual(patch,legacy)
        self.assertIn("author_association == 'OWNER'",patch[b.CALLER_PATH])
        self.assertIn("!startsWith(",legacy[b.CALLER_PATH])
        expected=hashlib.sha256(json.dumps(patch,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:12]
        self.assertEqual(b.replacement_branch_name(req,patch),f"{b.branch_name(req)}-{expected}")

    def test_upgraded_bootstrap_is_idempotent(self):
        req,patch,legacy,branch,old_sha,legacy_pr,replacement,gateway=self._legacy_upgrade_gateway()
        replacement_sha="d"*40
        replacement_pr=self._legacy_pr(req,replacement,189)
        replacement_pr["body"] += f"\n\nSupersedes bootstrap PR #{legacy_pr['number']}."
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: old_sha if v==branch else replacement_sha if v==replacement else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else replacement_pr if v==replacement else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch if v==replacement else False):
            result=b.bootstrap(request(),gateway,CALLER)
        self.assertEqual(result,{"status":"confirmed","branch":replacement,"pr":189,"created":False})
        self.assertEqual(gateway.created,[])

    def test_grindflow_188_existing_bootstrap_can_be_hardened(self):
        req,patch,legacy,branch,old_sha,legacy_pr,replacement,gateway=self._legacy_upgrade_gateway()
        self.assertEqual(branch,"factory/bootstrap-coordination-187")
        self.assertIn("!startsWith(",legacy[b.CALLER_PATH])
        self.assertIn("author_association == 'OWNER'",patch[b.CALLER_PATH])
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: old_sha if v==branch else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch):
            result=b.bootstrap(request(),gateway,CALLER)
        self.assertTrue(result["created"])
        self.assertEqual(result["branch"],replacement)
        self.assertNotEqual(result["branch"],branch)
        self.assertEqual(gateway.deleted,[])

    def test_materialize_rolls_back_partial_remote_state(self):
        gateway=b.GitHubGateway("token"); req=b.validate_request(request()); patch=b.build_patch(CALLER)
        calls=[]
        def api(method,path,payload=None,allow=()):
            calls.append((method,path))
            if "/git/blobs" in path: return {"sha":"b"}
            if "/git/trees" in path: return {"sha":"t"}
            if "/git/commits" in path: return {"sha":"c"*40}
            if method=="POST" and path.endswith("/pulls"): return {}
            return {}
        with mock.patch.object(gateway,"tree_info",return_value="base"), mock.patch.object(gateway,"_request",side_effect=api), mock.patch.object(gateway,"main_sha",side_effect=["d"*40]):
            with self.assertRaises(b.BootstrapError): gateway.materialize(req,patch)
        self.assertEqual(calls,[])
        calls.clear()
        with mock.patch.object(gateway,"tree_info",return_value="base"), mock.patch.object(gateway,"_request",side_effect=api), mock.patch.object(gateway,"main_sha",side_effect=[SHA,SHA,"d"*40]):
            with self.assertRaises(b.BootstrapError): gateway.materialize(req,patch)
        self.assertTrue(any(method=="DELETE" for method,_ in calls))
        calls.clear()
        with mock.patch.object(gateway,"tree_info",return_value="base"), mock.patch.object(gateway,"_request",side_effect=api), mock.patch.object(gateway,"main_sha",return_value=SHA):
            with self.assertRaises(b.BootstrapError): gateway.materialize(req,patch)
        self.assertTrue(any(method=="DELETE" for method,_ in calls))

    def test_workflow_reuses_existing_provision_authority_without_human_gate(self):
        text=(ROOT/".github/workflows/bootstrap-coordination.yml").read_text(encoding="utf-8")
        for value in ("workflow_dispatch:","FACTORY_PROVISION_TOKEN","github.repository_owner","contents: read","ref: v1","python3 runtime/scripts/bootstrap_coordination.py"):
            self.assertIn(value,text)
        self.assertNotIn("factory-human-gate",text); self.assertNotIn("github.token",text)
        source=(ROOT/"scripts/bootstrap_coordination.py").read_text(encoding="utf-8")
        self.assertIn('CALLER_TEMPLATE = Path("governance/template/.github/workflows/coordinacion.yml")',source)
        self.assertNotIn("--caller-template",source)


if __name__ == "__main__": unittest.main()
