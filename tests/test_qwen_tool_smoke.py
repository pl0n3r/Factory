"""Pure offline regression tests. Never start Qwen or contact a provider."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "qwen_tool_smoke", Path(__file__).resolve().parents[1] / "scripts/qwen_tool_smoke.py")
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def receipt(tool=True, success=True):
    blocks = [{"type": "tool_use", "name": "edit", "id": "edit-1"}] if tool else [{"type": "text", "text": '{"name":"edit","id":"edit-1"}'}]
    events = [{"type": "assistant", "message": {"content": blocks}}]
    if success:
        events.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "edit-1", "is_error": False}]}})
    events.append({"type": "result", "subtype": "success", "is_error": False})
    return "\n".join(json.dumps(x) for x in events)


class QwenToolSmokeTests(unittest.TestCase):
    def verdict(self, **changes):
        args = dict(before=q.BROKEN, after=q.FIXED, test_before=q.TEST,
                    test_after=q.TEST, files=q.EXPECTED, exit_code=0,
                    stdout=receipt(), initial_red=True, final_green=True,
                    isolation_ok=True, synthetic=True)
        args.update(changes)
        return q.evaluate(**args)

    def test_requires_real_edit_and_unchanged_green_test(self):
        yes = self.verdict()
        self.assertTrue(yes["accepted"])
        self.assertEqual(yes["state"], "FIXTURE_ONLY")
        self.assertEqual(yes["test_before_sha256"], yes["test_after_sha256"])
        self.assertIn("+    return value * 3", yes["diff"])

    def test_exit_zero_without_diff_is_rejected(self):
        self.assertFalse(self.verdict(after=q.BROKEN)["accepted"])

    def test_diff_without_green_test_is_rejected(self):
        self.assertFalse(self.verdict(final_green=False)["accepted"])
        self.assertFalse(self.verdict(initial_red=False)["accepted"])

    def test_tampered_test_is_rejected(self):
        self.assertFalse(self.verdict(test_after="pass\n")["accepted"])

    def test_textual_tool_imitation_is_rejected(self):
        self.assertFalse(self.verdict(stdout=receipt(tool=False))["accepted"])
        self.assertFalse(self.verdict(stdout='{"name":"edit","result":"ok"}')["accepted"])
        self.assertFalse(self.verdict(stdout=receipt(success=False))["accepted"])

    def test_extra_file_is_rejected(self):
        self.assertFalse(self.verdict(files=q.EXPECTED | {"extra.py"})["accepted"])

    def test_sandbox_unverified_and_timeout_fail_closed(self):
        self.assertFalse(self.verdict(isolation_ok=False)["accepted"])
        self.assertFalse(self.verdict(exit_code=124)["accepted"])
        self.assertFalse(self.verdict(exit_code=55)["accepted"])
        self.assertTrue(self.verdict(exit_code=55)["exit_55_budget"])

    def test_only_literal_loopback_endpoint_allowed(self):
        self.assertTrue(q.endpoint_ok("http://127.0.0.1:11434/v1"))
        for bad in ("https://127.0.0.1:11434/v1", "http://localhost:11434/v1",
                    "http://192.168.1.1:11434/v1", "http://127.0.0.1.evil/v1",
                    "http://127.0.0.1:11434/v1?x=1", "http://user:pw@127.0.0.1:11434/v1"):
            with self.subTest(bad=bad):
                self.assertFalse(q.endpoint_ok(bad))

    def test_no_sandbox_does_not_invoke_qwen(self):
        with patch.object(q.sys, "platform", "linux"), patch.object(q.shutil, "which") as which:
            self.assertEqual(q.run_real("http://127.0.0.1:11434/v1", "qwen3:4b")["state"], "UNKNOWN")
            which.assert_not_called()

    def test_invalid_endpoint_does_not_invoke_qwen(self):
        with patch.object(q.shutil, "which") as which:
            self.assertEqual(q.run_real("http://example.org/v1", "qwen3:4b")["state"], "UNKNOWN")
            which.assert_not_called()

    def test_fixture_red_then_green_with_unmodified_test(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "module.py").write_text(q.BROKEN)
            (root / "test_module.py").write_text(q.TEST)
            # Offline test owns its synthetic fixture; never used to claim real CLI edits.
            env = {"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}
            self.assertFalse(q.unittest_green(root, env))
            original = (root / "test_module.py").read_bytes()
            (root / "module.py").write_text(q.FIXED)
            self.assertTrue(q.unittest_green(root, env))
            self.assertEqual(original, (root / "test_module.py").read_bytes())

    def test_cleanup_owns_only_private_temp_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            witness = root / "external_witness"
            witness.write_text("untouched")
            with tempfile.TemporaryDirectory(dir=root, prefix="qwen-smoke-") as lab:
                path = Path(lab)
                (path / "module.py").write_text(q.BROKEN)
            self.assertFalse(path.exists())
            self.assertEqual(witness.read_text(), "untouched")


    def test_real_cli_path_isolated_and_fail_closed_without_edits(self):
        real_temp = tempfile.TemporaryDirectory

        class Completed:
            def __init__(self, code=0, stdout=""):
                self.returncode, self.stdout = code, stdout

        def temp_factory(**_):
            return real_temp(prefix="qwen-test-", dir="/tmp")

        seen = []
        def cli(root, profile, command, env, timeout=10):
            if "--version" in command:
                return Completed(stdout="qwen 0.26.9")
            if "--help" in command:
                return Completed(stdout="--core-tools --max-wall-time")
            if "unittest" in command:
                seen.append("sandboxed-unittest")
                return Completed()
            if mode == "edit":
                (root / "module.py").write_text(q.FIXED)
            elif mode == "symlink":
                (root / "module.py").unlink()
                (root / "module.py").symlink_to(root / "test_module.py")
            return Completed(stdout=receipt())

        for mode in ("edit", "no-edit", "symlink"):
            seen.clear()
            with self.subTest(mode=mode), patch.object(q.sys, "platform", "darwin"), \
                 patch.object(q.Path, "is_file", return_value=True), \
                 patch.object(q.shutil, "which", return_value="/usr/bin/qwen"), \
                 patch.object(q.tempfile, "TemporaryDirectory", side_effect=temp_factory), \
                 patch.object(q, "verify_isolation", return_value=True), \
                 patch.object(q, "sandboxed", side_effect=cli):
                result = q.run_real("http://127.0.0.1:11434/v1", "qwen3:4b")
            self.assertEqual(result["state"], {"edit": "TOOL_SMOKE_VERIFIED", "no-edit": "FAILED", "symlink": "UNKNOWN"}[mode])
            self.assertEqual(result.get("accepted", False), mode == "edit")
            self.assertEqual("sandboxed-unittest" in seen, mode != "symlink")

    def test_isolation_witness_requires_successful_kernel_probe(self):
        class Completed:
            returncode = 0

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "lab"
            root.mkdir()
            profile = root / "profile.sb"
            profile.write_text(q.seatbelt_profile(root))
            def safe_probe(*args, **kwargs):
                (root / "inside").write_text("yes")
                return Completed()
            with patch.object(q.sys, "platform", "darwin"), \
                 patch.object(q.Path, "is_file", return_value=True), \
                 patch.object(q, "sandboxed", side_effect=safe_probe):
                self.assertTrue(q.verify_isolation(root, profile, {}))
            with patch.object(q.sys, "platform", "darwin"), \
                 patch.object(q.Path, "is_file", return_value=True), \
                 patch.object(q, "sandboxed", return_value=Completed()):
                self.assertFalse(q.verify_isolation(root, profile, {}))


if __name__ == "__main__":
    unittest.main()
