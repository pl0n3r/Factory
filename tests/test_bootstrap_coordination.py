import os
import hashlib
import json
import subprocess
import tempfile
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
    def main_descends_from(self, *_): return self.same
    def legacy_marker(self, _, __, pr, req):
        if not self.same:
            return None
        value=b.parse_marker((pr or {}).get("body"))
        if value is None or value["target_issue"]!=req["target_issue"] or value["governance_ref"]!=req["governance_ref"]:
            return None
        return value
    def commit_matches_marker(self, *_): return self.same
    def legacy_pr_matches_exact(self, _, branch, number, req, legacy_sha=None, legacy_body=None, legacy_patch=None):
        pr=self.pr
        historical=self.legacy_marker(None,branch,pr,req)
        if historical is None or not isinstance(pr,dict) or pr.get("number")!=number:
            return False
        if legacy_body is not None and str(pr.get("body") or "")!=legacy_body:
            return False
        if legacy_sha is not None and self.branch!=legacy_sha:
            return False
        return self.same
    def delete_branch(self, _, branch): self.deleted.append(branch)
    def create_pr(self, _, branch, __, ___): self.created.append(("pr",branch)); return 98
    def materialize(self, req, patch):
        self.created.append((req, patch, b.branch_name(req)))
        return "c" * 40, 99
    def materialize_replacement(self, req, patch, branch, legacy_branch, legacy_sha, legacy_pr, legacy_body, legacy_patch):
        self.created.append(("replacement",req,patch,branch,legacy_branch,legacy_sha,legacy_pr,legacy_body,legacy_patch))
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
        patch=b.build_patch(CALLER); self.assertEqual({b.CALLER_PATH,b.TEST_PATH},set(patch))
        with self.assertRaises(b.BootstrapError): b.validate_patch({"evil.txt":"x", **patch})
        with self.assertRaises(b.BootstrapError): b.validate_patch({b.CALLER_PATH:"x"*(b.GRINDFLOW_MAX_FILE+1), b.TEST_PATH:"x"})
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
        restored=FakeGateway(branch="c"*40,pr=None,same=True)
        with mock.patch.object(restored,"create_pr",return_value=101) as create_pr:
            result=b.reuse_existing(req,restored,patch,b.legacy_patch(CALLER),branch,restored.branch,None)
        self.assertEqual(result,{"status":"confirmed","branch":branch,"pr":101,"created":True})
        body=create_pr.call_args.args[3]
        self.assertIn(f"Base exacta: `{req['expected_main_sha']}`",body)
        self.assertIn(b.marker(req),body)


    def _legacy_pr(self, req, branch, number=188):
        return {
            "number":number,
            "state":"open",
            "body":b.marker(req),
            "base":{"ref":"main","sha":req["expected_main_sha"],"repo":{"full_name":req["target_repository"]}},
            "head":{"ref":branch,"sha":"c"*40,"repo":{"full_name":req["target_repository"]}},
            "user":{"login":b.OWNER},
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
        legacy_body=b.marker(req)
        legacy=b.legacy_patch(CALLER)

        calls=[]
        def api(method,path,payload=None,allow=()):
            calls.append((method,path))
            if "/git/blobs" in path: return {"sha":"b"*40}
            if "/git/trees" in path: return {"sha":"t"*40}
            if "/git/commits" in path: return {"sha":"f"*40}
            return {}
        with mock.patch.object(gateway,"tree_info",return_value="base"), \
             mock.patch.object(gateway,"_request",side_effect=api), \
             mock.patch.object(gateway,"main_sha",return_value=SHA), \
             mock.patch.object(gateway,"branch_sha",return_value=legacy_sha), \
             mock.patch.object(gateway,"legacy_pr_matches_exact",return_value=False):
            with self.assertRaisesRegex(b.BootstrapError,"cambió"):
                gateway.materialize_replacement(
                    req,patch,replacement,legacy_branch,legacy_sha,188,legacy_body,legacy
                )
        self.assertFalse(any(method=="POST" and "/git/refs" in path for method,path in calls))

        calls.clear()
        with mock.patch.object(gateway,"tree_info",return_value="base"), \
             mock.patch.object(gateway,"_request",side_effect=api), \
             mock.patch.object(gateway,"main_sha",return_value=SHA), \
             mock.patch.object(gateway,"branch_sha",return_value=legacy_sha), \
             mock.patch.object(gateway,"legacy_pr_matches_exact",side_effect=[True,True,False]):
            with self.assertRaisesRegex(b.BootstrapError,"cambió"):
                gateway.materialize_replacement(
                    req,patch,replacement,legacy_branch,legacy_sha,188,legacy_body,legacy
                )
        self.assertTrue(any(method=="POST" and "/git/refs" in path for method,path in calls))
        self.assertTrue(any(method=="DELETE" and "/git/refs/heads/" in path for method,path in calls))

    def test_upgrade_revalidates_legacy_pr_before_and_after_replacement_ref(self):
        gateway=b.GitHubGateway("token")
        req=b.validate_request(request())
        patch=b.build_patch(CALLER)
        legacy_branch=b.branch_name(req)
        replacement=b.replacement_branch_name(req,patch)
        legacy_sha="c"*40
        legacy_body=b.marker(req)
        legacy=b.legacy_patch(CALLER)
        with mock.patch.object(gateway,"tree_info",return_value="base"), \
             mock.patch.object(gateway,"_request") as api, \
             mock.patch.object(gateway,"main_sha",return_value=SHA), \
             mock.patch.object(gateway,"branch_sha",return_value=legacy_sha), \
             mock.patch.object(gateway,"legacy_pr_matches_exact",return_value=False):
            with self.assertRaisesRegex(b.BootstrapError,"primer write"):
                gateway.materialize_replacement(req,patch,replacement,legacy_branch,legacy_sha,188,legacy_body,legacy)
        api.assert_not_called()

        calls=[]
        def api_after_ref(method,path,payload=None,allow=()):
            calls.append((method,path))
            if "/git/blobs" in path: return {"sha":"b"*40}
            if "/git/trees" in path: return {"sha":"t"*40}
            if "/git/commits" in path: return {"sha":"f"*40}
            return {}
        with mock.patch.object(gateway,"tree_info",return_value="base"), \
             mock.patch.object(gateway,"_request",side_effect=api_after_ref), \
             mock.patch.object(gateway,"main_sha",return_value=SHA), \
             mock.patch.object(gateway,"branch_sha",return_value=legacy_sha), \
             mock.patch.object(gateway,"legacy_pr_matches_exact",side_effect=[True,True,False]):
            with self.assertRaisesRegex(b.BootstrapError,"durante la migración"):
                gateway.materialize_replacement(req,patch,replacement,legacy_branch,legacy_sha,188,legacy_body,legacy)
        self.assertTrue(any(method=="POST" and "/git/refs" in path for method,path in calls))
        self.assertTrue(any(method=="DELETE" and "/git/refs/heads/" in path for method,path in calls))

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

    def test_replacement_branch_without_pr_recovers_only_after_exact_revalidation(self):
        req,patch,legacy,branch,old_sha,legacy_pr,replacement,gateway=self._legacy_upgrade_gateway()
        replacement_sha="d"*40
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: old_sha if v==branch else replacement_sha if v==replacement else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch if v==replacement else False), \
             mock.patch.object(gateway,"create_pr",return_value=190) as create_pr:
            result=b.bootstrap(request(),gateway,CALLER)
        self.assertEqual(result,{"status":"confirmed","branch":replacement,"pr":190,"created":True})
        self.assertEqual(gateway.created,[])
        args=create_pr.call_args.args
        self.assertEqual(args[1],replacement)
        self.assertIn(f"Base exacta: `{req['expected_main_sha']}`",args[3])
        self.assertIn(f"Supersedes bootstrap PR #{legacy_pr['number']}.",args[3])
        self.assertIn(b.marker(req),args[3])

    def test_create_pr_rolls_back_best_effort_on_transport_error(self):
        gateway=b.GitHubGateway("token")
        with mock.patch.object(gateway,"_request",side_effect=OSError("timeout")), \
             mock.patch.object(gateway,"delete_branch") as delete_branch:
            with self.assertRaises(OSError):
                gateway.create_pr("pl0n3r/Consumer","factory/bootstrap-coordination-187","title","body")
        delete_branch.assert_called_once_with("pl0n3r/Consumer","factory/bootstrap-coordination-187")

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


    def _grindflow_fixture(self, version="0.1.144"):
        tmp=tempfile.TemporaryDirectory()
        root=Path(tmp.name)
        for path in ("config","scripts","tests",".github/workflows"):
            (root/path).mkdir(parents=True,exist_ok=True)
        (root/"config/version.php").write_text(
            "<?php return ['number' => '"+version+"', 'released_at' => '2026-09-25'];\n",
            encoding="utf-8",
        )
        package={"name":"grindflow","version":version,"private":True}
        lock={"name":"grindflow","version":version,"lockfileVersion":3,"packages":{"":{"name":"grindflow","version":version}}}
        (root/"package.json").write_text(json.dumps(package,indent=2)+"\n",encoding="utf-8")
        (root/"package-lock.json").write_text(json.dumps(lock,indent=2)+"\n",encoding="utf-8")
        (root/"README.md").write_text("# GrindFlow — Último deploy\nVersion v"+version+"\n",encoding="utf-8")
        (root/"scripts/readme-dashboard.py").write_text("# README dashboard updater supports --update\n",encoding="utf-8")
        return tmp,root

    def _prepared_grindflow_patch(self, version="0.1.144"):
        tmp,root=self._grindflow_fixture(version)
        completed=lambda args,**kwargs: subprocess.CompletedProcess(
            args,0,stdout=(SHA+"\n" if args[:3]==["git","rev-parse","HEAD"] else ""),stderr=""
        )
        with mock.patch("scripts.bootstrap_coordination.subprocess.run",side_effect=completed):
            patch=b.grindflow_delivery_patch(CALLER,root,SHA)
        return tmp,root,patch

    def test_grindflow_adapter_requires_exact_version_parity_and_patch_increment(self):
        tmp,root,patch=self._prepared_grindflow_patch()
        self.addCleanup(tmp.cleanup)
        self.assertIn("'number' => '0.1.145'",patch["config/version.php"])
        package=json.loads(patch["package.json"])
        lock=json.loads(patch["package-lock.json"])
        self.assertEqual(package["version"],"0.1.145")
        self.assertEqual(lock["version"],"0.1.145")
        self.assertEqual(lock["packages"][""]["version"],"0.1.145")
        (root/"package.json").write_text('{"name":"grindflow","version":"0.1.143"}\n',encoding="utf-8")
        completed=lambda args,**kwargs: subprocess.CompletedProcess(args,0,stdout=SHA+"\n",stderr="")
        with mock.patch("scripts.bootstrap_coordination.subprocess.run",side_effect=completed):
            with self.assertRaisesRegex(b.BootstrapError,"paridad"):
                b.grindflow_delivery_patch(CALLER,root,SHA)

    def test_grindflow_patch_paths_are_closed_and_bounded(self):
        tmp,_,patch=self._prepared_grindflow_patch()
        self.addCleanup(tmp.cleanup)
        self.assertEqual(set(patch),b.GRINDFLOW_DELIVERY_PATHS)
        b.validate_patch(patch,b.GRINDFLOW_DELIVERY_PATHS)
        with self.assertRaises(b.BootstrapError):
            b.validate_patch({**patch,"evil.txt":"x"},b.GRINDFLOW_DELIVERY_PATHS)
        oversized={**patch,"README.md":"x"*(b.GRINDFLOW_MAX_FILE+1)}
        with self.assertRaises(b.BootstrapError):
            b.validate_patch(oversized,b.GRINDFLOW_DELIVERY_PATHS)

    def test_grindflow_patch_updates_version_package_lock_and_readme(self):
        tmp,root,patch=self._prepared_grindflow_patch()
        self.addCleanup(tmp.cleanup)
        self.assertIn("0.1.145",patch["config/version.php"])
        self.assertEqual(json.loads(patch["package.json"])["version"],"0.1.145")
        lock=json.loads(patch["package-lock.json"])
        self.assertEqual((lock["version"],lock["packages"][""]["version"]),("0.1.145","0.1.145"))
        self.assertEqual(patch["README.md"],(root/"README.md").read_text(encoding="utf-8"))
        self.assertIn(b.CALLER_PATH,patch)
        self.assertIn(b.TEST_PATH,patch)

    def test_grindflow_188_fixture_no_longer_has_same_version_transition(self):
        tmp,_,patch=self._prepared_grindflow_patch("0.1.143")
        self.addCleanup(tmp.cleanup)
        self.assertIn("'number' => '0.1.144'",patch["config/version.php"])
        self.assertNotIn("'number' => '0.1.143'",patch["config/version.php"])

    def test_replacement_idempotency_stays_fail_closed_with_delivery_patch(self):
        tmp,_,patch=self._prepared_grindflow_patch()
        self.addCleanup(tmp.cleanup)
        raw=request()
        raw["target_repository"]=b.GRINDFLOW_REPO
        req=b.validate_request(raw)
        legacy=b.legacy_patch(CALLER)
        branch=b.branch_name(req)
        old_sha="c"*40
        legacy_pr=self._legacy_pr(req,branch)
        gateway=FakeGateway(branch=old_sha,pr=legacy_pr,same=True)
        replacement=b.replacement_branch_name(req,patch)
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: old_sha if v==branch else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch):
            result=b.reuse_existing(req,gateway,patch,legacy,branch,old_sha,legacy_pr)
        self.assertEqual(result["branch"],replacement)
        drift=FakeGateway(main="d"*40)
        with self.assertRaisesRegex(b.BootstrapError,"expected_main_sha"):
            b.bootstrap_prepared(raw,drift,CALLER,patch)

    def test_unsupported_strict_consumer_fails_before_write(self):
        tmp,root=self._grindflow_fixture()
        self.addCleanup(tmp.cleanup)
        raw=request()
        with self.assertRaisesRegex(b.BootstrapError,"sin adapter"):
            b.prepare_delivery_patch(raw,CALLER,root)


    def test_grindflow_real_lock_uses_consumer_specific_limit(self):
        tmp,root=self._grindflow_fixture()
        self.addCleanup(tmp.cleanup)
        lock=json.loads((root/"package-lock.json").read_text(encoding="utf-8"))
        lock["padding"]="x"*(b.MAX_FILE+4096)
        (root/"package-lock.json").write_text(json.dumps(lock,indent=2)+"\n",encoding="utf-8")
        completed=lambda args,**kwargs: subprocess.CompletedProcess(
            args,0,stdout=(SHA+"\n" if args[:3]==["git","rev-parse","HEAD"] else ""),stderr=""
        )
        with mock.patch("scripts.bootstrap_coordination.subprocess.run",side_effect=completed):
            patch=b.grindflow_delivery_patch(CALLER,root,SHA)
        size=len(patch[b.LOCK_PATH].encode())
        self.assertGreater(size,b.MAX_FILE)
        self.assertLess(size,b.GRINDFLOW_MAX_FILE)

        lock["padding"]="x"*(b.GRINDFLOW_MAX_FILE+4096)
        (root/"package-lock.json").write_text(json.dumps(lock,indent=2)+"\n",encoding="utf-8")
        with mock.patch("scripts.bootstrap_coordination.subprocess.run",side_effect=completed):
            with self.assertRaisesRegex(b.BootstrapError,"excede límite"):
                b.grindflow_delivery_patch(CALLER,root,SHA)

    def test_regular_consumer_keeps_generic_file_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"plain.txt").write_text("x"*(b.MAX_FILE+1),encoding="utf-8")
            with self.assertRaisesRegex(b.BootstrapError,"excede límite"):
                b._regular_text(root,"plain.txt")

    def test_prepared_manifest_remains_bound_before_write(self):
        raw=request()
        req=b.validate_request(raw)
        patch=b.build_patch(CALLER)
        prepared={
            "version":1,
            "identity":b.identity(req),
            "target_repository":req["target_repository"],
            "expected_main_sha":req["expected_main_sha"],
            "patch_sha256":b.patch_sha(patch),
            "patch":patch,
        }
        self.assertEqual(b.load_prepared_delivery(raw,prepared),patch)
        tampered=json.loads(json.dumps(prepared))
        tampered["patch"][b.CALLER_PATH]+="# tamper\n"
        with self.assertRaisesRegex(b.BootstrapError,"cambió"):
            b.load_prepared_delivery(raw,tampered)
        wrong=json.loads(json.dumps(prepared))
        wrong["identity"]="0"*64
        with self.assertRaisesRegex(b.BootstrapError,"intención"):
            b.load_prepared_delivery(raw,wrong)

    def test_prepared_manifest_temp_path_keeps_binding_before_write(self):
        raw=request()
        req=b.validate_request(raw)
        patch=b.build_patch(CALLER)
        prepared={
            "version":1,
            "identity":b.identity(req),
            "target_repository":req["target_repository"],
            "expected_main_sha":req["expected_main_sha"],
            "patch_sha256":b.patch_sha(patch),
            "patch":patch,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/b.PREPARED_FILE.name
            target.write_text(json.dumps(prepared),encoding="utf-8")
            with mock.patch.dict(os.environ,{b.PREPARED_DIR_ENV:str(root)},clear=False):
                resolved=b.prepared_file_for_mode(True)
            self.assertEqual(resolved,target)
            loaded=json.loads(resolved.read_text(encoding="utf-8"))
            self.assertEqual(b.load_prepared_delivery(raw,loaded),patch)
            loaded["patch"][b.CALLER_PATH]+="# tamper\n"
            with self.assertRaisesRegex(b.BootstrapError,"cambió"):
                b.load_prepared_delivery(raw,loaded)


    def _cross_main(self, patch=None, repository="pl0n3r/Consumer"):
        old_raw,new_raw=request("c"*64),request("d"*64)
        for raw in (old_raw,new_raw): raw["target_repository"]=repository
        old_raw["expected_main_sha"],new_raw["expected_main_sha"]="f"*40,SHA
        old_req,new_req=b.validate_request(old_raw),b.validate_request(new_raw)
        patch=patch or b.build_patch(CALLER); legacy=b.legacy_patch(CALLER)
        branch=b.branch_name(new_req); legacy_sha="c"*40
        legacy_pr=self._legacy_pr(old_req,branch)
        gateway=FakeGateway(main=SHA,branch=legacy_sha,pr=legacy_pr,same=True)
        return old_req,new_req,patch,legacy,branch,legacy_sha,legacy_pr,b.replacement_branch_name(new_req,patch),gateway

    def _reuse_cross_main(self, data, replacement_sha=None, replacement_pr=None):
        _,req,patch,legacy,branch,legacy_sha,legacy_pr,replacement,gateway=data
        with mock.patch.object(gateway,"branch_sha",side_effect=lambda _,v: legacy_sha if v==branch else replacement_sha if v==replacement else None), \
             mock.patch.object(gateway,"open_pr",side_effect=lambda _,v: legacy_pr if v==branch else replacement_pr if v==replacement else None), \
             mock.patch.object(gateway,"branch_matches",side_effect=lambda _,v,p: p==legacy if v==branch else p==patch if v==replacement else False):
            return b.reuse_existing(req,gateway,patch,legacy,branch,legacy_sha,legacy_pr)

    def test_legacy_from_previous_main_can_be_reconciled_against_current_exact_main(self):
        data=self._cross_main(); old,req,_,_,_,_,_,replacement,_=data
        self.assertEqual(self._reuse_cross_main(data),{"status":"confirmed","branch":replacement,"pr":100,"created":True})
        self.assertNotEqual(old["expected_main_sha"],req["expected_main_sha"])

    def test_previous_main_legacy_is_superseded_without_overwrite(self):
        data=self._cross_main(); _,_,_,_,branch,legacy_sha,_,replacement,gateway=data
        self.assertEqual(self._reuse_cross_main(data)["branch"],replacement)
        call=[row for row in gateway.created if row[0]=="replacement"][0]
        self.assertEqual((call[4],call[5],gateway.deleted),(branch,legacy_sha,[]))

    def test_historical_legacy_identity_is_verified_independently_from_new_request(self):
        data=self._cross_main(); old,req,_,_,branch,_,pr,_,_=data; gateway=b.GitHubGateway("token")
        with mock.patch.object(gateway,"main_descends_from",return_value=True) as descends:
            historical=gateway.legacy_marker(req["target_repository"],branch,pr,req)
        self.assertEqual(historical["identity"],b.identity(old)); self.assertNotEqual(historical["identity"],b.identity(req))
        descends.assert_called_once_with(req["target_repository"],old["expected_main_sha"],req["expected_main_sha"])
        altered=json.loads(json.dumps(pr)); altered["user"]["login"]="other-owner"
        with mock.patch.object(gateway,"main_descends_from",return_value=True):
            self.assertIsNone(gateway.legacy_marker(req["target_repository"],branch,altered,req))

    def test_cross_main_replacement_fails_closed_on_legacy_or_current_main_drift(self):
        data=self._cross_main(); _,req,patch,legacy,branch,legacy_sha,pr,_,gateway=data
        changed=json.loads(json.dumps(pr)); changed["body"]+="\nchanged"; gateway.pr=changed
        self.assertFalse(gateway.legacy_pr_matches_exact(req["target_repository"],branch,pr["number"],req,legacy_sha,pr["body"],legacy))
        raw=request("d"*64); raw["target_repository"],raw["expected_main_sha"]=req["target_repository"],req["expected_main_sha"]
        drift=FakeGateway(main="e"*40,branch=legacy_sha,pr=pr,same=True)
        with self.assertRaisesRegex(b.BootstrapError,"expected_main_sha"):
            b.bootstrap_prepared(raw,drift,CALLER,patch)

    def test_cross_main_grindflow_replacement_preserves_delivery_contract(self):
        tmp,_,patch=self._prepared_grindflow_patch("0.1.144"); self.addCleanup(tmp.cleanup)
        data=self._cross_main(patch,b.GRINDFLOW_REPO); old,req,_,_,_,_,_,replacement,_=data
        lock=json.loads(patch[b.LOCK_PATH])
        self.assertEqual(set(patch),b.GRINDFLOW_DELIVERY_PATHS)
        self.assertIn("'number' => '0.1.145'",patch[b.VERSION_PATH])
        self.assertEqual((json.loads(patch[b.PACKAGE_PATH])["version"],lock["version"],lock["packages"][""]["version"]),("0.1.145",)*3)
        self.assertEqual(self._reuse_cross_main(data)["branch"],replacement); self.assertNotEqual(old["expected_main_sha"],req["expected_main_sha"])

    def test_cross_main_replacement_is_idempotent(self):
        data=self._cross_main(); _,req,_,_,_,_,legacy_pr,replacement,gateway=data
        replacement_pr=self._legacy_pr(req,replacement,189); replacement_pr["body"]+=f"\n\nSupersedes bootstrap PR #{legacy_pr['number']}."
        result=self._reuse_cross_main(data,"d"*40,replacement_pr)
        self.assertEqual(result,{"status":"confirmed","branch":replacement,"pr":189,"created":False}); self.assertEqual(gateway.created,[])

    def test_grindflow_188_real_sha_transition(self):
        old_raw,new_raw=request("c"*64),request("d"*64)
        for raw in (old_raw,new_raw): raw["target_repository"]=b.GRINDFLOW_REPO
        old_raw["expected_main_sha"]="f5b74ddff10569023dd1b2a73de5dd8937bc3192"
        new_raw["expected_main_sha"]="4e28fbb277c3642e48535a005540d159c2c5c21e"
        old,req=b.validate_request(old_raw),b.validate_request(new_raw); branch=b.branch_name(req); gateway=b.GitHubGateway("token")
        with mock.patch.object(gateway,"main_descends_from",return_value=True):
            historical=gateway.legacy_marker(b.GRINDFLOW_REPO,branch,self._legacy_pr(old,branch),req)
        first,middle,head="e9d3daafd407abd4d375f5b7b344e4316b8935eb","3282f81e8bdec055bd91e2347f43a4c2bd9e6125","7f5929a70990574453855e02d8c5021bf97a646b"
        compare={"status":"ahead","ahead_by":3,"behind_by":0,"merge_base_commit":{"sha":old_raw["expected_main_sha"]},
                 "commits":[{"sha":first,"parents":[{"sha":old_raw["expected_main_sha"]}]},{"sha":middle,"parents":[{"sha":first}]},{"sha":head,"parents":[{"sha":middle}]}],
                 "files":[{"filename":b.CALLER_PATH},{"filename":b.TEST_PATH}]}
        anchor={"message":"Factory-Bootstrap-Identity: "+historical["identity"],"parents":[{"sha":old_raw["expected_main_sha"]}]}
        with mock.patch.object(gateway,"_request",side_effect=[compare,anchor]):
            self.assertTrue(gateway.commit_matches_marker(b.GRINDFLOW_REPO,head,historical,{b.CALLER_PATH,b.TEST_PATH}))

    def test_cross_main_legacy_rejects_non_linear_history(self):
        old,req,_,_,branch,_,pr,_,_=self._cross_main(); gateway=b.GitHubGateway("token")
        with mock.patch.object(gateway,"main_descends_from",return_value=True):
            historical=gateway.legacy_marker(req["target_repository"],branch,pr,req)
        first,merge,head="1"*40,"2"*40,"3"*40
        compare={"status":"ahead","ahead_by":3,"behind_by":0,"merge_base_commit":{"sha":old["expected_main_sha"]},
                 "commits":[{"sha":first,"parents":[{"sha":old["expected_main_sha"]}]},{"sha":merge,"parents":[{"sha":first},{"sha":"9"*40}]},{"sha":head,"parents":[{"sha":merge}]}],
                 "files":[{"filename":b.CALLER_PATH},{"filename":b.TEST_PATH}]}
        with mock.patch.object(gateway,"_request",return_value=compare):
            self.assertFalse(gateway.commit_matches_marker(req["target_repository"],head,historical,{b.CALLER_PATH,b.TEST_PATH}))


    def test_bootstrap_validation_bypass_requires_owner_same_repo_identity(self):
        template=(ROOT/"template/.github/workflows/coordinacion.yml").read_text(encoding="utf-8")
        value=b.caller_content(template)
        repo="pl0n3r/Consumer"
        self.assertFalse(
            generated_validation_runs(
                value,
                ref="factory/bootstrap-coordination-187",
                head_repo=repo,
                repository=repo,
                association="OWNER",
            )
        )
        for ref,head_repo,association in (
            ("trabajo/issue-187",repo,"OWNER"),
            ("factory/bootstrap-coordination-187",repo,"MEMBER"),
            ("factory/bootstrap-coordination-187",repo,"COLLABORATOR"),
            ("factory/bootstrap-coordination-187","fork/Consumer","OWNER"),
        ):
            with self.subTest(ref=ref,head_repo=head_repo,association=association):
                self.assertTrue(
                    generated_validation_runs(
                        value,
                        ref=ref,
                        head_repo=head_repo,
                        repository=repo,
                        association=association,
                    )
                )

    def test_grindflow_regeneration_inherits_hardened_consumer_caller(self):
        template=(ROOT/"template/.github/workflows/coordinacion.yml").read_text(encoding="utf-8")
        tmp,root=self._grindflow_fixture("0.1.144")
        self.addCleanup(tmp.cleanup)
        completed=lambda args,**kwargs: subprocess.CompletedProcess(
            args,0,stdout=(SHA+"\n" if args[:3]==["git","rev-parse","HEAD"] else ""),stderr=""
        )
        with mock.patch("scripts.bootstrap_coordination.subprocess.run",side_effect=completed):
            patch=b.grindflow_delivery_patch(template,root,SHA)
        caller=patch[b.CALLER_PATH]
        self.assertIn(
            "types: [opened, reopened, synchronize, edited, ready_for_review, converted_to_draft, closed]",
            caller,
        )
        self.assertIn("group: coordinacion-${{ github.repository }}",caller)
        self.assertIn("cancel-in-progress: false",caller)
        self.assertIn("queue: max",caller)
        comment=caller.split("  comentario:",1)[1].split("  etiqueta:",1)[0]
        self.assertIn("github.event.comment.body == '/tomar'",comment)
        self.assertIn("contains(github.event.comment.body, '/tomar')",comment)
        self.assertIn("startsWith(github.event.comment.body, '/renovar-contrato ')",comment)
        self.assertIn("profile: es",caller)
        self.assertIn("require_reservation: true",caller)
        self.assertNotIn("@main",caller)


if __name__ == "__main__": unittest.main()
