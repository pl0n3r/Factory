#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/politica.yml").read_text(encoding="utf-8")
DOC = (ROOT / "docs/politica-revisor-externo.md").read_text(encoding="utf-8")


class PoliticaWorkflowRefTests(unittest.TestCase):
    def _factory_checkout_section(self) -> str:
        start = WORKFLOW.index("Checkout Factory stable v1")
        end = WORKFLOW.index(
            "Validar política canónica con evidencia reviewer-bot observada",
            start,
        )
        return WORKFLOW[start:end]

    def _pre_checkout_validation(self) -> str:
        start = WORKFLOW.index(
            "Validar evento, PR, HEAD y policy base antes de checkout"
        )
        end = WORKFLOW.index("actions/checkout@", start)
        return WORKFLOW[start:end]

    def test_default_v1_preserves_legacy_callers_and_checkout_uses_input(self) -> None:
        self.assertIn(
            'factory_ref: {required: false, type: string, default: "v1"}',
            WORKFLOW,
        )
        checkout = self._factory_checkout_section()
        self.assertEqual(checkout.count("repository: pl0n3r/factory"), 2)
        self.assertEqual(checkout.count("path: .factory"), 2)
        self.assertIn("Checkout Factory stable v1", checkout)
        self.assertIn("if: ${{ inputs.factory_ref == 'v1' }}", checkout)
        self.assertIn("ref: v1", checkout)
        self.assertIn("Checkout Factory exact SHA", checkout)
        self.assertIn("if: ${{ inputs.factory_ref != 'v1' }}", checkout)
        self.assertIn("ref: ${{ inputs.factory_ref }}", checkout)
        self.assertEqual(checkout.count("persist-credentials: false"), 2)
        self.assertIn("El reusable `politica.yml` mantiene compatibilidad histórica", DOC)

    def test_exact_40_hex_factory_ref_is_allowed_for_immutable_bridge(self) -> None:
        validation = self._pre_checkout_validation()
        self.assertIn('FACTORY_REF: ${{ inputs.factory_ref }}', validation)
        self.assertIn('v1) ;;', validation)
        self.assertIn('^' + '[0-9a-f]{40}' + '$', validation)
        allowed = re.compile(r"^(?:v1|[0-9a-f]{40})$")
        self.assertRegex("v1", allowed)
        self.assertRegex("0123456789abcdef0123456789abcdef01234567", allowed)
        checkout = self._factory_checkout_section()
        self.assertIn("if: ${{ inputs.factory_ref != 'v1' }}", checkout)
        self.assertIn("ref: ${{ inputs.factory_ref }}", checkout)
        self.assertIn("un commit inmutable", DOC)
        self.assertIn("no publica ni mueve `Factory@v1`", DOC)

    def test_moving_or_malformed_factory_refs_fail_closed_before_internal_checkout(
        self,
    ) -> None:
        validation = self._pre_checkout_validation()
        self.assertIn("factory_ref debe ser v1 o un SHA lowercase exacto de 40 hex", validation)
        self.assertLess(
            WORKFLOW.index("case \"$FACTORY_REF\" in"),
            WORKFLOW.index("repository: pl0n3r/factory"),
        )
        allowed = re.compile(r"^(?:v1|[0-9a-f]{40})$")
        for rejected in (
            "main",
            "master",
            "v1.0.27",
            "refs/heads/main",
            "0123456",
            "ABCDEF0123456789ABCDEF0123456789ABCDEF01",
            "0123456789abcdef0123456789abcdef0123456g",
            "",
        ):
            with self.subTest(factory_ref=rejected):
                self.assertIsNone(allowed.fullmatch(rejected))
        self.assertIn("fallan cerrado **antes** del checkout interno", DOC)


if __name__ == "__main__":
    unittest.main()
