"""Factory #1323 / F1F: retirar telemetría CI, preservar presupuesto exigible.

Regresión completamente offline. No lee secretos, no usa la red y prueba
explícitamente los negativos que impedirían retirar una puerta de gasto.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/costos.yml"
DIET = ROOT / "docs/dieta-factory.md"
COSTDOC = ROOT / "docs/costos-presupuestos.md"
EXPECTED_BEFORE = "e88c1e5986c56264ce97b5341b8af4fa9a41e0e0"


def job_block(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if match is None:
        raise AssertionError(f"Job obligatorio ausente: {name}")
    return match.group("body")


def assert_budget_contract(workflow: str) -> None:
    assert "on:\n  pull_request:" in workflow
    assert "    types: [opened, synchronize, edited, reopened, ready_for_review]" in workflow
    assert "permissions: {}" in workflow
    candidate = job_block(workflow, "validar-candidato")
    budget = job_block(workflow, "presupuesto-pr")
    for token in (
        "if: github.event_name == 'pull_request'",
        "contents: read",
        "persist-credentials: false",
        "python3 -m py_compile metricas/costos.py",
        "test_costos.py",
    ):
        assert token in candidate
    for token in (
        "name: Presupuesto del PR",
        "if: github.event_name == 'pull_request'",
        "contents: read",
        "ref: ${{ github.event.pull_request.base.sha }}",
        "persist-credentials: false",
        "trusted-base-without-cost-control",
        "metricas/presupuestos.json",
        "presupuesto-pr.json",
        "presupuesto-pr.md",
        "name: presupuesto-pr-${{ github.event.pull_request.number }}-${{ github.run_id }}",
        "retention-days: 30",
        "if-no-files-found: error",
    ):
        assert token in budget, token
    assert "issues: write" not in workflow
    assert "contents: write" not in workflow


class DietaFase1FTests(unittest.TestCase):
    def test_only_pull_request_trigger_and_no_trend_job(self):
        workflow = WF.read_text(encoding="utf-8")
        self.assertEqual(
            re.findall(r"(?m)^  ([a-z_]+):\s*$", workflow.split("\npermissions:", 1)[0]),
            ["pull_request"],
        )
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("  tendencia-ci:", workflow)
        self.assertEqual(
            re.findall(r"(?m)^  ([a-z][a-z0-9-]+):\s*$", workflow.split("\njobs:\n", 1)[1]),
            ["validar-candidato", "presupuesto-pr"],
        )
        self.assertNotIn("gh api", workflow, "El job de tendencia no debe seguir llamando a GitHub")
        self.assertNotIn("actions: read", workflow)

    def test_pr_budget_jobs_and_artifacts_remain_safe(self):
        workflow = WF.read_text(encoding="utf-8")
        assert_budget_contract(workflow)
        with self.assertRaises(AssertionError):
            assert_budget_contract(workflow.replace(
                "ref: ${{ github.event.pull_request.base.sha }}", "ref: main"
            ))
        with self.assertRaises(AssertionError):
            assert_budget_contract(workflow.replace("retention-days: 30", "retention-days: 0"))
        with self.assertRaises(AssertionError):
            assert_budget_contract(workflow.replace("  presupuesto-pr:", "  budget-removed:"))

    def test_offline_trend_and_documented_rollback(self):
        source = (ROOT / "metricas/costos.py").read_text(encoding="utf-8")
        tests = (ROOT / "metricas/test_costos.py").read_text(encoding="utf-8")
        self.assertIn("def ci_trend(", source)
        self.assertIn("def test_ci_trend_groups_all_completed_runs_by_pr", tests)
        doc = COSTDOC.read_text(encoding="utf-8")
        self.assertIn("## Tendencia de CI (solo motor offline)", doc)
        self.assertIn("no programa", doc)
        self.assertIn("presupuesto", doc)
        diet = DIET.read_text(encoding="utf-8")
        ledger = diet.split("## Ledger F1F:", 1)[1]
        self.assertIn(EXPECTED_BEFORE, ledger)
        self.assertIn("31 → 31", ledger)
        self.assertIn("squash-revert solo del PR F1F", ledger)
        self.assertEqual(ledger.count("| F1F |"), 1)

    def test_inventory_preserves_exact_workflow_set(self):
        from tests.test_dieta_fase1c import EXPECTED_ACTIVE
        from tests.test_factory_diet_inventory import workflow_events

        paths = {p.name for p in (ROOT / ".github/workflows").glob("*.yml")}
        self.assertEqual(len(paths), 31)
        self.assertEqual(paths, set(EXPECTED_ACTIVE))
        diet = DIET.read_text(encoding="utf-8")
        rows = [line for line in diet.splitlines()
                if line.startswith("| `.github/workflows/costos.yml` |")]
        self.assertEqual(len(rows), 1)
        self.assertIn("| pull_request |", rows[0])
        self.assertNotIn("schedule", rows[0])
        self.assertEqual(workflow_events(WF), {"pull_request"})
        swapped = (paths - {"costos.yml"}) | {"costo-no-autorizado.yml"}
        self.assertNotEqual(swapped, set(EXPECTED_ACTIVE))


if __name__ == "__main__":
    unittest.main()
