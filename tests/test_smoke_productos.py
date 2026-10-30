"""Regresiones sintéticas para smoke post-release Factory@v1."""
import unittest
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


if __name__ == "__main__":
    unittest.main()
