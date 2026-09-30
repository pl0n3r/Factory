from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTES.md"


class RemoteDesktopPolicyTests(unittest.TestCase):
    def setUp(self):
        self.text = AGENTS.read_text(encoding="utf-8")

    def test_policy_requires_efficient_remote_desktop_usage(self):
        self.assertIn("## Uso eficiente de Remote Desktop Commander", self.text)
        self.assertIn("Prioriza GitHub/API", self.text)
        self.assertIn("Agrupa varios pasos locales", self.text)
        self.assertIn("No sondees procesos", self.text)
        self.assertIn("Limita la salida", self.text)

    def test_policy_limits_high_call_and_unsolicited_revalidation(self):
        self.assertIn("más de ~20 llamadas", self.text)
        self.assertIn("avisa antes", self.text)
        self.assertIn("No hagas revisiones periódicas", self.text)
        self.assertIn("revalidaciones globales no solicitadas", self.text)

    def test_policy_forbids_paid_upgrade_and_stays_compact(self):
        self.assertIn("No está autorizado comprar plan Pro", self.text)
        self.assertIn("recargar saldo", self.text)
        self.assertLessEqual(len(self.text.splitlines()), 110)


if __name__ == "__main__":
    unittest.main()
