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
  self.assertEqual(release_step.count("verify_remote_main\n"),1)
  self.assertLess(release_step.index("verify_remote_main\n"),release_step.index('gh release create "$TAG"'))
  self.assertIn('TARGET_SHA: ${{ github.sha }}',release_step)
  self._actual_guard("RELEASE")

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
