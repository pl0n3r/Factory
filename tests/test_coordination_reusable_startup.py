import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "coordinacion.yml"


class CoordinationReusableStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def _concurrency_lines(self) -> list[str]:
        lines = self.text.splitlines()
        try:
            start = lines.index("concurrency:")
        except ValueError as exc:
            self.fail(f"missing concurrency block: {exc}")

        block: list[str] = []
        for line in lines[start + 1 :]:
            if line and not line.startswith("  "):
                break
            if line.strip():
                block.append(line)
        return block

    def test_concurrency_uses_only_supported_keys(self) -> None:
        keys = [line.strip().split(":", 1)[0] for line in self._concurrency_lines()]
        self.assertEqual(["group", "cancel-in-progress"], keys)
        self.assertIn("group: factory-coordination-${{ github.repository_id }}", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_queue_key_regression_is_rejected(self) -> None:
        self.assertNotIn("queue:", "\n".join(self._concurrency_lines()))
        self.assertNotIn("queue: max", self.text)

    def test_metadata_repair_preserves_coordination_contract(self) -> None:
        required_fragments = (
            "name: Coordinación reusable",
            "workflow_call:",
            "operation:",
            "profile:",
            "kit_ref:",
            "permissions:\n  contents: read",
            "name: Validar operación",
            "name: Procesar comando",
            "name: Sincronizar reserva",
            "name: Sincronizar PR",
            "name: Sincronizar Issue",
            "name: Validar coordinación",
            "name: Barrer coordinación y bloqueos",
            "python3 .factory/scripts/coordinar_trabajo.py comentario",
            "python3 .factory/scripts/coordinar_trabajo.py label-event",
            "python3 .factory/scripts/coordinar_trabajo.py pr-event",
            "python3 .factory/scripts/coordinar_trabajo.py issue-event",
            "python3 .factory/scripts/coordinar_trabajo.py validar-pr",
            "python3 .factory/scripts/coordinar_trabajo.py marcar-inactivas",
        )
        for fragment in required_fragments:
            self.assertIn(fragment, self.text)


if __name__ == "__main__":
    unittest.main()
