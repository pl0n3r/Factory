import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
W=(Path(__file__).resolve().parents[1]/".github/workflows/release.yml").read_text()
class T(unittest.TestCase):
 def test_outputs_are_yaml_blocks(self):
  self.assertIn("version:\n        description:",W); self.assertNotIn("version: {value:",W)
 def test_existing_tag_must_match_sha(self):
  self.assertIn('existing_sha="$(git rev-parse "refs/tags/$TAG^{commit}")"',W); self.assertIn('"$existing_sha" == "$TARGET_SHA"',W); self.assertIn("409|422",W)
 def test_factory_bootstrap_normalizes_repository_casing(self):
  self.assertIn('REPOSITORY="${REPOSITORY,,}"',W)
  self.assertIn('[[ "$REPOSITORY" == "pl0n3r/factory" ]]',W)

 def _actual_guard(self, kind):
  start=f"# RELEASE_EXACT_MAIN_{kind}_GUARD_BEGIN"
  end=f"# RELEASE_EXACT_MAIN_{kind}_GUARD_END"
  self.assertEqual(W.count(start),1)
  self.assertEqual(W.count(end),1)
  return textwrap.dedent(W.split(start,1)[1].split(end,1)[0])

 def test_reusable_revalidates_main_before_tag_mutation(self):
  tag_step=W.split("      - name: Asegurar tag anotado",1)[1].split("      - id: release",1)[0]
  self.assertEqual(tag_step.count("verify_remote_main\n"),2)
  self.assertLess(tag_step.index("verify_remote_main\n"),tag_step.index('gh api --method POST "repos/$REPOSITORY/git/tags"'))
  self.assertLess(tag_step.index('gh api --method POST "repos/$REPOSITORY/git/tags"'),tag_step.rindex("verify_remote_main\n"))
  self.assertLess(tag_step.rindex("verify_remote_main\n"),tag_step.index('gh api --include --silent --method POST'))
  self._actual_guard("TAG")

 def test_reusable_revalidates_main_before_release_mutation(self):
  release_step=W.split("      - id: release",1)[1]
  self.assertEqual(release_step.count("verify_remote_main\n"),3)
  self.assertLess(release_step.index("verify_remote_main\n"),release_step.index('gh release create "$TAG"'))
  self.assertIn('TARGET_SHA: ${{ github.sha }}',release_step)
  self._actual_guard("RELEASE")
  self.assertIn("verify_remote_tag\n",release_step)
  self.assertLess(release_step.index("verify_remote_tag\n"),release_step.index('gh release create "$TAG"'))

 def test_reusable_denies_bad_or_changed_main_without_mutation(self):
  sha="a"*40
  with tempfile.TemporaryDirectory() as tmp:
   gh=Path(tmp)/"gh"
   gh.write_text('#!/bin/sh\nif [ "$FAKE_API_FAILURE" = 1 ]; then exit 22; fi\nprintf "%s\\n" "$FAKE_MAIN_SHA"\n',encoding="utf-8")
   gh.chmod(0o700)
   base=dict(os.environ,PATH=tmp+":"+os.environ.get("PATH",""),
             TARGET_SHA=sha,BOOTSTRAP="true",EXPECTED_SHA=sha,
             REPOSITORY="pl0n3r/Factory",DEFAULT_BRANCH="main",
             FAKE_MAIN_SHA=sha,FAKE_API_FAILURE="0")
   cases=[
    ("success",{},True),
    ("changed SHA",{"FAKE_MAIN_SHA":"b"*40},False),
    ("empty result",{"FAKE_MAIN_SHA":""},False),
    ("malformed SHA",{"FAKE_MAIN_SHA":"not-a-sha"},False),
    ("API failure",{"FAKE_API_FAILURE":"1"},False),
    ("wrong approved SHA",{"EXPECTED_SHA":"b"*40},False),
    ("invalid candidate",{"TARGET_SHA":"broken"},False),
   ]
   for kind in ("TAG","RELEASE"):
    script="set -euo pipefail\n"+self._actual_guard(kind)+"\nverify_remote_main\nprintf 'MUTATION_ALLOWED\\n'"
    for label,changes,allowed in cases:
     with self.subTest(kind=kind,case=label):
      p=subprocess.run(["bash","-c",script],env={**base,**changes},
                       capture_output=True,text=True,timeout=10)
      self.assertEqual(p.returncode==0,allowed,p.stdout+p.stderr)
      self.assertEqual("MUTATION_ALLOWED" in p.stdout,allowed,p.stdout+p.stderr)

 def _step_body(self, kind):
  if kind=="tag":
   segment=W.split("      - name: Asegurar tag anotado",1)[1].split("      - id: release",1)[0]
  else:
   segment=W.split("      - id: release",1)[1]
  return textwrap.dedent(segment.split("        run: |\n",1)[1])

 def _execute_step(self, kind, *, main=None, mutate="", tag_exists=False, approved=None,
                   remote_ref=None,remote_target=None,release_status="404",
                   tag_object=None,view_url=None):
  sha="a"*40
  drift="b"*40
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)
   log=folder/"mutations.log"
   log.write_text("",encoding="utf-8")
   remote=folder/"main.sha"
   remote.write_text(sha if main is None else main,encoding="utf-8")
   release=folder/"release.created"
   remote_tag_file=folder/"remote-tag.target"
   remote_tag_file.write_text(sha if remote_target is None else remote_target,encoding="utf-8")
   if release_status=="200":
    release.write_text("exists",encoding="utf-8")
   gh=folder/"gh"
   gh.write_text(textwrap.dedent(r"""
    #!/bin/sh
    printf '%s\n' "$*" >> "$FAKE_LOG"
    if [ "$1" = api ]; then
      case "$*" in
        */commits/*)
          state="$(cat "$FAKE_MAIN_FILE")"
          [ "$state" != API_ERROR ] || exit 33
          printf '%s\n' "$state"
          exit 0 ;;
        */git/ref/tags/*)
          [ "$FAKE_REMOTE_REF" != API_ERROR ] || exit 33
          printf '%s\n' "$FAKE_REMOTE_REF"
          exit 0 ;;
        */git/tags/*)
          value="$(cat "$FAKE_REMOTE_TARGET_FILE")"
          [ "$value" != API_ERROR ] || exit 33
          printf '%s\n' "$value"
          exit 0 ;;
        */git/tags*)
          if [ "$FAKE_MUTATE" = tag ]; then
            printf '%s' "$FAKE_DRIFT_SHA" > "$FAKE_MAIN_FILE"
          fi
          printf '%s\n' "$FAKE_TAG_OBJECT_SHA"
          exit 0 ;;
        */git/refs*)
          printf 'HTTP/2 201\n'
          exit 0 ;;
        */releases/tags/*)
          if [ "$FAKE_MUTATE" = view ]; then
            printf '%s' "$FAKE_DRIFT_SHA" > "$FAKE_MAIN_FILE"
          fi
          if [ "$FAKE_MUTATE" = remote_tag ]; then
            printf '%s' "$FAKE_DRIFT_SHA" > "$FAKE_REMOTE_TARGET_FILE"
          fi
          printf 'HTTP/2 %s\n' "$FAKE_RELEASE_STATUS"
          if [ "$FAKE_RELEASE_STATUS" = 200 ]; then exit 0; fi
          exit 22 ;;
      esac
    fi
    if [ "$1" = release ]; then
      if [ "$2" = view ]; then
        if [ -f "$FAKE_RELEASE_FILE" ]; then
          printf '%s\n' "$FAKE_VIEW_URL"
          exit 0
        fi
        exit 1
      fi
      if [ "$2" = create ]; then
        : > "$FAKE_RELEASE_FILE"
        exit 0
      fi
    fi
    exit 88
   """).lstrip(),encoding="utf-8")
   gh.chmod(0o700)
   git=folder/"git"
   git.write_text(textwrap.dedent(r"""
    #!/bin/sh
    if [ "$1" = show-ref ]; then
      if [ "$FAKE_TAG_EXISTS" = 1 ]; then exit 0; fi
      exit 1
    fi
    if [ "$1" = cat-file ]; then printf 'tag\n'; exit 0; fi
    if [ "$1" = rev-parse ]; then printf '%s\n' "$TARGET_SHA"; exit 0; fi
    exit 88
   """).lstrip(),encoding="utf-8")
   git.chmod(0o700)
   output=folder/"outputs.txt"
   env=dict(os.environ,PATH=tmp+os.pathsep+os.environ.get("PATH",""),
     REPOSITORY="pl0n3r/Factory",DEFAULT_BRANCH="main",BOOTSTRAP="true",
     TARGET_SHA=sha,EXPECTED_SHA=sha if approved is None else approved,
     TAG="v1.0.29",VERSION="1.0.29",GH_TOKEN="fixture",
     FAKE_MAIN_FILE=str(remote),FAKE_LOG=str(log),
     FAKE_RELEASE_FILE=str(release),FAKE_MUTATE=mutate,
     FAKE_DRIFT_SHA=drift,
     FAKE_TAG_OBJECT_SHA="c"*40 if tag_object is None else tag_object,
     FAKE_VIEW_URL=("https://github.com/pl0n3r/Factory/releases/tag/v1.0.29"
                    if view_url is None else view_url),
     FAKE_REMOTE_REF="c"*40 if remote_ref is None else remote_ref,
     FAKE_REMOTE_TARGET_FILE=str(remote_tag_file),
     FAKE_RELEASE_STATUS=release_status,
     FAKE_TAG_EXISTS="1" if tag_exists else "0",GITHUB_OUTPUT=str(output))
   run=subprocess.run(["bash","-euo","pipefail","-c",self._step_body(kind)],
                      env=env,capture_output=True,text=True,timeout=10)
   if run.returncode:
    self.assertFalse(output.exists() and output.read_text(encoding="utf-8"),
                     "failed release exported approval")
   return run,log.read_text(encoding="utf-8"),release.exists(),remote.read_text(encoding="utf-8")

 def test_actual_tag_script_stops_before_ref_after_intermediate_drift(self):
  run,log,created,main=self._execute_step("tag",mutate="tag")
  self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertEqual(main,"b"*40)
  self.assertEqual(log.count("git/tags"),1,log)
  self.assertNotIn("git/refs",log)
  self.assertFalse(created)

 def test_actual_release_script_stops_after_view_changes_main(self):
  run,log,created,main=self._execute_step("release",mutate="view")
  self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertEqual(main,"b"*40)
  self.assertIn("releases/tags/",log)
  self.assertNotIn("release view",log)
  self.assertNotIn("release create",log)
  self.assertFalse(created)

 def test_actual_tag_and_release_scripts_fail_closed_and_preserve_idempotence(self):
  for kind in ("tag","release"):
   for label,kwargs in (
     ("advanced",{"main":"b"*40}),
     ("empty",{"main":""}),
     ("malformed",{"main":"not-a-sha"}),
     ("api failure",{"main":"API_ERROR"}),
     ("expected mismatch",{"approved":"b"*40}),
   ):
    with self.subTest(kind=kind,case=label):
     run,log,created,_=self._execute_step(kind,**kwargs)
     self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
     self.assertNotIn("git/tags",log)
     self.assertNotIn("git/refs",log)
     self.assertNotIn("release create",log)
     self.assertFalse(created)
  run,log,created,_=self._execute_step("tag",tag_exists=True)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertNotIn("git/tags",log)
  self.assertNotIn("git/refs",log)
  run,log,created,_=self._execute_step("release")
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn("release create",log)
  self.assertTrue(created)

 def test_actual_release_refuses_remote_tag_drift_before_publish(self):
  run,log,created,main=self._execute_step("release",mutate="remote_tag")
  self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertEqual(main,"a"*40,"main is unchanged; only remote tag drifted")
  self.assertIn("git/ref/tags/",log)
  self.assertIn("git/tags/",log)
  self.assertNotIn("release create",log)
  self.assertFalse(created)
  for label,params in (
    ("missing",{"remote_ref":""}),
    ("lightweight",{"remote_ref":"null"}),
    ("remote ref API",{"remote_ref":"API_ERROR"}),
    ("invalid tag object",{"remote_ref":"not-a-sha"}),
    ("wrong commit",{"remote_target":"b"*40}),
    ("missing object",{"remote_target":""}),
    ("object API",{"remote_target":"API_ERROR"}),
  ):
   with self.subTest(case=label):
    res,trace,created,_=self._execute_step("release",**params)
    self.assertNotEqual(res.returncode,0,res.stdout+res.stderr)
    self.assertNotIn("release create",trace)
    self.assertFalse(created)

 def test_release_status_requires_rest_404_before_real_create(self):
  release_step=self._step_body("release")
  self.assertIn('gh api --include --silent "repos/$REPOSITORY/releases/tags/$TAG"',release_step)
  self.assertLess(release_step.index("probe="),release_step.index('gh release create "$TAG"'))
  for code in ("403","429","500","401","302","unknown",""):
   with self.subTest(code=code):
    run,trace,created,_=self._execute_step("release",release_status=code)
    self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
    self.assertIn("releases/tags/",trace)
    self.assertNotIn("release create",trace)
    self.assertFalse(created)
  run,trace,created,_=self._execute_step("release",release_status="404")
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn("releases/tags/",trace)
  self.assertIn("release create",trace)
  self.assertTrue(created)
  run,trace,created,_=self._execute_step("release",release_status="200")
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn("releases/tags/",trace)
  self.assertNotIn("release create",trace)
  self.assertTrue(created)


 def test_existing_release_must_revalidate_remote_tag(self):
  # A REST 200 is not proof that the existing remote tag matches TARGET_SHA.
  run,trace,created,_=self._execute_step("release",release_status="200",
                                         remote_target="b"*40)
  self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn("git/ref/tags/",trace)
  self.assertIn("git/tags/",trace)
  self.assertNotIn("release create",trace)
  run,trace,created,_=self._execute_step("release",release_status="200")
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn("git/ref/tags/",trace)
  self.assertNotIn("release create",trace)
  self.assertTrue(created)

 def test_idempotent_release_validates_url_and_remote_tag(self):
  for label,settings in (
    ("changed tag",{"remote_target":"b"*40}),
    ("wrong URL",{"view_url":"https://example.invalid/wrong"}),
    ("empty URL",{"view_url":""}),
    ("null URL",{"view_url":"null"}),
  ):
   with self.subTest(case=label):
    run,trace,_,_=self._execute_step("release",release_status="200",**settings)
    self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
    self.assertNotIn("release create",trace)
  run,trace,_,_=self._execute_step("release",release_status="200")
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertNotIn("release create",trace)

 def test_tag_creation_response_requires_sha_before_ref_post(self):
  for value in ("","null","abc","not-a-sha"):
   with self.subTest(value=value):
    run,trace,_,_=self._execute_step("tag",tag_object=value)
    self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
    self.assertIn("git/tags",trace)
    self.assertNotIn("git/refs",trace)
