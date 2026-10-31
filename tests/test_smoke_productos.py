"""Regresiones sintéticas para smoke post-release Factory@v1."""
import io
import json
import unittest
from unittest.mock import patch
from scripts.smoke_productos import PRODUCTOS, evaluate

SHA = "a" * 40


def valid_inventory():
    return {"products": [
        {"repository": p, "phase": "construccion", "origin": None, "version": None}
        for p in PRODUCTOS
    ]}


def fake_fetch(path):
    if path.endswith("/git/ref/heads/main"):
        return {"object": {"sha": SHA}}
    if path.endswith("/check-runs?per_page=100"):
        return {"total_count": 1, "check_runs": [{"id": 1, "name": "Validar", "head_sha": SHA,
             "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"}}]}
    return {"full_name": "/".join(path.split("/")[2:4]), "default_branch": "main"}


class SmokeProductosTests(unittest.TestCase):
    def test_criterio_principal(self):
        result = evaluate(valid_inventory(), fetch=fake_fetch, health=lambda *a, **kw: {})
        self.assertEqual(result["decision"], "GO")
        self.assertEqual(len(result["products"]), 6)
        self.assertTrue(all(x["health"] == "NO_APLICA" for x in result["products"]))
        self.assertTrue(all(x["ci"] == "success" for x in result["products"]))

    def test_omission_and_duplicate_fail_closed(self):
        for rows in (valid_inventory()["products"][:-1], valid_inventory()["products"][:5] + valid_inventory()["products"][:1]):
            with self.subTest(rows=len(rows)):
                self.assertEqual(evaluate({"products": rows}, fetch=fake_fetch, health=lambda *a, **kw: {})["decision"], "NO-GO")

    def test_unknown_phase_and_missing_live_version_are_no_go(self):
        for phase, origin, version in (("UNKNOWN", None, None), ("live", "https://example.org", None)):
            inventory = valid_inventory()
            inventory["products"][0].update(phase=phase, origin=origin, version=version)
            self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=lambda *a, **kw: {})["decision"], "NO-GO")

    def test_failing_or_missing_ci_is_no_go(self):
        def bad_fetch(path):
            value = fake_fetch(path)
            if path.endswith("check-runs?per_page=100"):
                value["check_runs"][0]["conclusion"] = "failure"
            return value
        report = evaluate(valid_inventory(), fetch=bad_fetch, health=lambda *a, **kw: {})
        self.assertEqual(report["decision"], "NO-GO")
        self.assertTrue(all(x["ci"] != "success" for x in report["products"]))

    def test_main_drift_fails_closed(self):
        count = {}
        def moved(path):
            count[path] = count.get(path, 0) + 1
            value = fake_fetch(path)
            if path.endswith("git/ref/heads/main") and count[path] == 2:
                value["object"]["sha"] = "b" * 40
            return value
        self.assertEqual(evaluate(valid_inventory(), fetch=moved, health=lambda *a, **kw: {})["decision"], "NO-GO")

    def test_live_health_is_checked_and_failure_blocks(self):
        inventory = valid_inventory()
        inventory["products"][0].update(phase="live", origin="https://example.org", version="1.2.3")
        calls = []
        def health(*args, **kwargs):
            calls.append((args, kwargs))
            return {"status": "ok"}
        report = evaluate(inventory, fetch=fake_fetch, health=health)
        self.assertEqual(report["decision"], "GO")
        self.assertEqual(calls[0][0], ("https://example.org", "/health", "1.2.3", SHA))
        def down(*_args, **_kwargs):
            raise RuntimeError("unreachable")
        self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=down)["decision"], "NO-GO")

    def test_malformed_main_ref_fails_closed(self):
        count = {}
        def malformed(path):
            count[path] = count.get(path, 0) + 1
            value = fake_fetch(path)
            if path.endswith("git/ref/heads/main") and count[path] == 2:
                value["object"] = None
            return value
        report = evaluate(valid_inventory(), fetch=malformed, health=lambda *a, **kw: {})
        self.assertEqual(report["decision"], "NO-GO")
        self.assertEqual(report["products"][0]["reason"], "evidence_unverified")

    def test_partial_check_pages_are_no_go(self):
        def partial(path):
            value = fake_fetch(path)
            if path.endswith("check-runs?per_page=100"):
                value["total_count"] = 2
            return value
        self.assertEqual(evaluate(valid_inventory(), fetch=partial, health=lambda *a, **kw: {})["decision"], "NO-GO")


    def test_repository_identity_and_canonical_check_fail_closed(self):
        for mode in ("metadata", "no_checks", "other_app", "unfinished", "bad_id", "bad_sha"):
            def invalid(path):
                value = fake_fetch(path)
                if mode == "metadata" and path.endswith("/Condor"):
                    value["full_name"] = "wrong/repo"
                if path.endswith("/check-runs?per_page=100"):
                    run = value["check_runs"][0]
                    if mode == "no_checks":
                        value["check_runs"] = []
                        value["total_count"] = 0
                    elif mode == "other_app":
                        run["app"]["slug"] = "untrusted"
                    elif mode == "unfinished":
                        run["status"] = "in_progress"
                    elif mode == "bad_id":
                        run["id"] = "1"
                    elif mode == "bad_sha":
                        run["head_sha"] = "b" * 40
                return value
            with self.subTest(mode=mode):
                result = evaluate(valid_inventory(), fetch=invalid, health=lambda *a, **k: {})
                self.assertEqual(result["decision"], "NO-GO")

    def test_missing_sha_and_invalid_response_fail_closed(self):
        for mode in ("missing_sha", "invalid_checks", "exception", "invalid_check_list"):
            def invalid(path):
                if mode == "exception":
                    raise RuntimeError("unavailable")
                value = fake_fetch(path)
                if path.endswith("/git/ref/heads/main") and mode == "missing_sha":
                    value["object"] = {"sha": "unknown"}
                if path.endswith("/check-runs?per_page=100") and mode == "invalid_checks":
                    value["total_count"] = None
                if path.endswith("/check-runs?per_page=100") and mode == "invalid_check_list":
                    value["check_runs"] = {}
                return value
            with self.subTest(mode=mode):
                result = evaluate(valid_inventory(), fetch=invalid, health=lambda *a, **k: {})
                self.assertEqual(result["decision"], "NO-GO")

    def test_prelive_metadata_and_invalid_inventory_are_no_go(self):
        for inventory in (None, {}, {"products": []}, {"products": "text"},
                          {"products": valid_inventory()["products"], "extra": True}):
            with self.subTest(inventory=str(inventory)[:30]):
                self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=lambda *a, **k: {})["decision"], "NO-GO")
        inventory = valid_inventory()
        inventory["products"][0]["origin"] = "https://example.org"
        self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=lambda *a, **k: {})["decision"], "NO-GO")

    def test_live_invalid_version_and_health_are_no_go(self):
        for version in ("0.1", "v1.2.3", "01.2.3", None):
            inventory = valid_inventory()
            inventory["products"][0].update(phase="live", origin="https://example.org", version=version)
            self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=lambda *a, **k: {})["decision"], "NO-GO")
        inventory = valid_inventory()
        inventory["products"][0].update(phase="live", origin="https://example.org", version="1.2.3")
        def error(*args, **kwargs):
            raise OSError("TLS failed")
        self.assertEqual(evaluate(inventory, fetch=fake_fetch, health=error)["decision"], "NO-GO")

    def test_github_response_is_bounded_and_fail_closed(self):
        from scripts.smoke_productos import MAX_BYTES, github_get
        for body, expected in ((b'{"ok":true}', True), (b'[]', None),
                               (b'{', None), (b'x' * (MAX_BYTES + 1), None)):
            with self.subTest(length=len(body)):
                with patch("scripts.smoke_productos.urlopen", return_value=io.BytesIO(body)):
                    if expected is None:
                        with self.assertRaises(ValueError):
                            github_get("/repos/pl0n3r/Condor")
                    else:
                        self.assertEqual(github_get("/repos/pl0n3r/Condor"), {"ok": expected})
        with patch("scripts.smoke_productos.urlopen", side_effect=TimeoutError("timeout")):
            with self.assertRaises(ValueError):
                github_get("/repos/pl0n3r/Condor")

    def test_cli_only_accepts_stdin_and_never_open_paths(self):
        from scripts.smoke_productos import MAX_BYTES, main
        for argv, content in ((["--inventory", "../etc/passwd"], b"{}"),
                              ([], b"{"), ([], b"x" * (MAX_BYTES + 1)), ([], b"")):
            with self.subTest(args=argv, length=len(content)):
                stdin = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8")
                with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(main(argv), 1)
                    self.assertEqual(json.loads(output.getvalue())["decision"], "NO-GO")
        stdin = io.TextIOWrapper(io.BytesIO(b'{"products":[]}'), encoding="utf-8")
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main([]), 1)
            self.assertEqual(json.loads(output.getvalue())["reason"], "inventory_incomplete_or_invalid")

    def test_untyped_api_evidence_fails_closed(self):
        for suffix in ("/Condor", "/git/ref/heads/main", "/check-runs?per_page=100"):
            def untyped(path):
                if path.endswith(suffix):
                    return None
                return fake_fetch(path)
            with self.subTest(suffix=suffix):
                result = evaluate(valid_inventory(), fetch=untyped, health=lambda *a, **k: {})
                self.assertEqual(result["decision"], "NO-GO")



if __name__ == "__main__":
    unittest.main()
