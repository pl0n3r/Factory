#!/usr/bin/env python3
"""Opt-in, fail-closed Qwen edit smoke. No GitHub, model downloads or host mutation."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
from secrets import token_urlsafe
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

BROKEN = "def triple(value):\n    return value * 2\n"
FIXED = "def triple(value):\n    return value * 3\n"
TEST = ("import unittest\nfrom module import triple\n\n"
        "class TripleTest(unittest.TestCase):\n"
        "    def test_seven(self):\n"
        "        self.assertEqual(triple(7), 21)\n")
EXPECTED = {"module.py", "test_module.py"}
MAX_OUTPUT = 524288


def digest(data):
    return hashlib.sha256(data).hexdigest()


def evaluate(before, after, test_before, test_after, files, exit_code, stdout,
             initial_red, final_green, isolation_ok, synthetic=False):
    """Never infer a tool call from prose or exit=0 alone."""
    calls, results, terminal = set(), set(), False
    valid_stream = True
    try:
        if not isinstance(stdout, str) or len(stdout) > MAX_OUTPUT:
            raise ValueError("oversized or absent structured output")
        for line in stdout.splitlines():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("not an event")
            if item.get("type") == "assistant":
                for block in item.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "edit" and isinstance(block.get("id"), str):
                        calls.add(block["id"])
            if item.get("type") == "user":
                for block in item.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error") is False and isinstance(block.get("tool_use_id"), str):
                        results.add(block["tool_use_id"])
            if item.get("type") == "result" and item.get("subtype") == "success" and item.get("is_error") is False:
                terminal = True
    except (ValueError, TypeError, AttributeError, KeyError):
        valid_stream = False
    evidence = bool(valid_stream and terminal and calls & results)
    good = bool(isolation_ok and initial_red and final_green and exit_code == 0 and
                before == BROKEN and after == FIXED and test_before == test_after == TEST and
                set(files) == EXPECTED and evidence)
    return {"state": "FIXTURE_ONLY" if synthetic else ("TOOL_SMOKE_VERIFIED" if good else "FAILED"),
            "accepted": good, "edit_tool_succeeded": evidence,
            "original_sha256": digest(before.encode()), "final_sha256": digest(after.encode()),
            "test_before_sha256": digest(test_before.encode()),
            "test_after_sha256": digest(test_after.encode()),
            "diff": ("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="module.py:before", tofile="module.py:after")) if before == BROKEN and after == FIXED else ("REDACTED_UNEXPECTED_CHANGE" if before != after else "")),
            "exit_code": exit_code, "exit_55_observed": exit_code == 55,
            "initial_red": initial_red, "final_green": final_green,
            "file_inventory_ok": set(files) == EXPECTED, "isolation_verified": isolation_ok,
            "observed_edit_calls": len(calls), "successful_edit_calls": len(calls & results)}


def endpoint_ok(url):
    try:
        u = urlsplit(url)
        return (u.scheme == "http" and u.hostname == "127.0.0.1" and
                1 <= (u.port or 0) <= 65535 and u.path == "/v1" and
                not u.username and not u.password and not u.query and not u.fragment)
    except ValueError:
        return False


def seatbelt_profile(root):
    """Restrictive macOS kernel policy; the process and descendants inherit it."""
    safe = str(root.resolve())
    if not safe.startswith("/private/tmp/") and not safe.startswith("/tmp/"):
        raise RuntimeError("lab must be below system temporary directory")
    return '\n'.join([
        '(version 1)', '(deny default)',
        '(allow process-fork)', '(allow process-exec)',
        '(allow file-read* (subpath "/System") (subpath "/usr") (subpath "/Library") (subpath "/opt/homebrew") (subpath "/dev") (subpath "/private/var/db/dyld") (subpath "'+safe+'"))',
        '(allow file-write* (subpath "'+safe+'") (literal "/dev/null"))',
        '(allow network-outbound (remote ip "127.0.0.1:*"))',
    ]) + '\n'


def sandboxed(root, profile, command, env, timeout=10):
    return subprocess.run(["/usr/bin/sandbox-exec", "-f", str(profile), *command],
                          cwd=root, env=env, capture_output=True, text=True,
                          timeout=timeout, check=False)


def verify_isolation(root, profile, env):
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        return False
    witness = root.parent / "witness"
    witness.write_text("do not touch", encoding="utf8")
    probe = ("import os,socket,sys\n"
             "from pathlib import Path\n"
             "base=Path(sys.argv[1]); target=Path(sys.argv[2]); host=int(sys.argv[3])\n"
             "try: (base/'inside').write_text('yes')\n"
             "except Exception: sys.exit(11)\n"
             "try: target.write_text('breach'); sys.exit(12)\n"
             "except (PermissionError,OSError): pass\n"
             "try: os.kill(host,0); sys.exit(13)\n"
             "except (PermissionError,OSError): pass\n"
             "s=socket.socket();s.settimeout(1)\n"
             "try: s.connect(('1.1.1.1',443));sys.exit(14)\n"
             "except OSError: pass\n"
             "finally: s.close()\n")
    try:
        result = sandboxed(root, profile, [sys.executable, "-c", probe, str(root), str(witness), str(os.getpid())], env)
        return result.returncode == 0 and witness.read_text(encoding="utf8") == "do not touch" and (root / "inside").read_text(encoding="utf8") == "yes"
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        witness.unlink(missing_ok=True)
        (root / "inside").unlink(missing_ok=True)


def unittest_green(folder, env, profile=None):
    command = [sys.executable, "-m", "unittest", "-q", "test_module"]
    if profile is not None:
        p = sandboxed(folder, profile, command, env)
    else:
        p = subprocess.run(command, cwd=folder, env=env, capture_output=True, timeout=10)
    return p.returncode == 0


def run_real(endpoint, model, max_seconds=90):
    if not endpoint_ok(endpoint) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,80}", model):
        return {"state": "UNKNOWN", "reason": "invalid local endpoint or model"}
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        return {"state": "UNKNOWN", "reason": "kernel sandbox not available; no CLI invoked"}
    qwen = shutil.which("qwen")
    if not qwen or not Path(qwen).is_absolute():
        return {"state": "UNKNOWN", "reason": "installed Qwen CLI not found"}
    with tempfile.TemporaryDirectory(prefix="qwen-smoke-", dir="/private/tmp") as td:
        root = Path(td, "lab").resolve()
        root.mkdir(mode=0o700)
        if root.is_symlink():
            return {"state": "UNKNOWN", "reason": "unsafe sandbox root"}
        project, home = root / "project", root / "home"
        project.mkdir(mode=0o700); home.mkdir(mode=0o700)
        (project / "module.py").write_text(BROKEN, encoding="utf8")
        (project / "test_module.py").write_text(TEST, encoding="utf8")
        profile = root / "profile.sb"
        profile.write_text(seatbelt_profile(root), encoding="utf8")
        env = {"HOME": str(home), "QWEN_HOME": str(home / ".qwen"),
               "PATH": os.pathsep.join([str(Path(qwen).parent), str(Path(sys.executable).parent), "/usr/bin", "/bin"]),
               "NO_COLOR": "1", "CI": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "QWEN_CODE_DISABLE_TELEMETRY": "true", "QWEN_CODE_UNATTENDED_RETRY": "0"}
        red = not unittest_green(project, env)
        if not red or not verify_isolation(root, profile, env):
            return {"state": "UNKNOWN", "reason": "isolation probe/initial RED failed; no CLI invoked"}
        try:
            about = sandboxed(project, profile, [qwen, "--version"], env)
            help_result = sandboxed(project, profile, [qwen, "--help"], env)
        except (OSError, subprocess.TimeoutExpired):
            return {"state": "UNKNOWN", "reason": "CLI preflight failed inside sandbox"}
        if (about.returncode != 0 or help_result.returncode != 0 or
                "--core-tools" not in help_result.stdout or "--max-wall-time" not in help_result.stdout):
            return {"state": "UNKNOWN", "reason": "CLI flags/version unverified inside sandbox"}
        version_match = re.search(r"\b\d+\.\d+\.\d+\b", about.stdout[:256])
        version = version_match.group(0) if version_match else "UNKNOWN"
        argv = [qwen, "--bare", "--auth-type", "openai", "--openai-base-url", endpoint,
                "--openai-api-key", token_urlsafe(16), "--model", model,
                "--approval-mode", "auto-edit", "--core-tools", "read_file,edit",
                "--max-tool-calls", "4", "--max-session-turns", "12",
                "--max-wall-time", str(max_seconds), "--output-format", "stream-json",
                "-p", "Read module.py, fix triple so triple(7)==21 by editing module.py. Do not edit test_module.py or any other file."]
        before = (project / "module.py").read_text(encoding="utf8")
        test_before = (project / "test_module.py").read_text(encoding="utf8")
        try:
            done = sandboxed(project, profile, argv, env, timeout=max_seconds+8)
            rc, stdout, stderr = done.returncode, done.stdout, done.stderr or ""
        except (OSError, subprocess.TimeoutExpired):
            rc, stdout, stderr = 124, "", ""
        children = list(project.iterdir())
        if any(x.is_symlink() for x in children):
            return {"state": "UNKNOWN", "reason": "symlink in fixture; refusing unsandboxed reads"}
        after = (project / "module.py").read_text(encoding="utf8") if (project / "module.py").is_file() else ""
        test_after = (project / "test_module.py").read_text(encoding="utf8") if (project / "test_module.py").is_file() else ""
        files = [x.name for x in children]
        green = unittest_green(project, env, profile) if after == FIXED and test_after == TEST and set(files) == EXPECTED else False
        result = evaluate(before, after, test_before, test_after, files, rc, stdout, red, green, True)
        if rc == 55:
            result["exit_55_cause"] = ("budget-evidenced" if re.search(r"budget|tool.?call.?limit|turn.?limit", stderr[:2048], re.I) else "unknown")
            result["stderr_sha256"] = digest(stderr.encode())
        result.update({"runtime": "Qwen Code CLI", "model": model, "endpoint": endpoint,
                       "max_wall_seconds": max_seconds, "max_tool_calls": 4,
                       "tool_evidence_sha256": digest(stdout.encode()),
                       "runtime_version": version, "test_runner": "unittest (harness; not Qwen shell)"})
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="opt-in Mac sandbox smoke; never run in CI")
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--model", default="qwen3:4b")
    args = ap.parse_args()
    result = run_real(args.endpoint, args.model) if args.run else {"state": "UNKNOWN", "reason": "opt-in --run required"}
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["state"] == "TOOL_SMOKE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
