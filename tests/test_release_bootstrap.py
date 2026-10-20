"""Regresiones para releases protegidos del canal mayor v1."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from test_release_bootstrap_runtime import (
    SHA,
    ReleaseBootstrapError,
    bot_source_issue,
    owner_source_issue,
    rearmed_gate_body,
    valid_rearmed_v2_payload,
    validate_payload,
)

RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TEMPLATE_RELEASE = ROOT / "template" / ".github" / "workflows" / "release.yml"
GUIDE = ROOT / "docs" / "release-bootstrap.md"


class ReleaseBootstrapTests(unittest.TestCase):
    """Preserva la frontera de seguridad de releases v1.x."""

    @classmethod
    def setUpClass(cls):
        """Carga los artefactos de release una sola vez."""
        cls.release = RELEASE.read_text(encoding="utf-8")
        cls.template_release = TEMPLATE_RELEASE.read_text(encoding="utf-8")
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def test_write_release_stays_on_published_v1(self):
        """AC-01: release ejecuta únicamente el kit publicado v1."""
        self.assertIn("repository: pl0n3r/factory", self.release)
        self.assertIn("ref: v1", self.release)
        self.assertNotIn("inputs.kit_ref", self.release)

    def test_release_api_has_no_dynamic_kit_ref(self):
        """AC-02: workflow_call no ofrece una referencia dinámica del kit."""
        workflow_call = self.release.split("outputs:", 1)[0]
        self.assertNotIn("kit_ref:", workflow_call)

    def test_bootstrap_guide_requires_human_gate(self):
        """AC-03: la guía falla cerrado ante gates humanos pendientes."""
        for required in (
            "release-1.0.0",
            "factory-release",
            "default seguro es **no publicar**",
            "/decidir A",
            "/decidir B",
            "factory-human-decision",
            "compatibilidad histórica",
            "SHA exacto aprobado",
            "mueve manualmente el tag mayor",
            "nunca crea ni mueve `v1`",
        ):
            self.assertIn(required, self.guide)

    def test_template_release_stays_on_v1(self):
        """AC-04: el template continúa consumiendo el canal mayor v1."""
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/release.yml@v1",
            self.template_release,
        )

    def test_rearm_chain_stops_at_human_decided_gate(self):
        """AC-01: una cadena larga de rearmados sigue válida si termina en el OWNER."""
        def chain(bots):
            sources = [
                bot_source_issue(number=1000 + i, source_issue=1001 + i)
                for i in range(bots)
            ]
            sources.append(owner_source_issue(number=1000 + bots))
            return valid_rearmed_v2_payload(
                gate_body=rearmed_gate_body(source_issue=1000),
                sources=sources,
            )

        self.assertEqual(
            validate_payload(chain(17)), {"status": "ready", "sha": SHA}
        )
        oversized = chain(64)
        with self.assertRaises(ReleaseBootstrapError):
            validate_payload(oversized)

        undecided = chain(17)
        undecided["gate"]["comments"] = []
        with self.assertRaisesRegex(ReleaseBootstrapError, "Decisión v2"):
            validate_payload(undecided)

        cyclic = chain(3)
        cyclic["rearm_sources"][1]["body"] = bot_source_issue(
            number=1001, source_issue=1000
        )["body"]
        cyclic["rearm_sources"][2] = dict(
            cyclic["rearm_sources"][0]
        )
        with self.assertRaisesRegex(ReleaseBootstrapError, "cíclica"):
            validate_payload(cyclic)

    def test_workflow_and_script_share_rearm_depth(self):
        """La profundidad del bucle del workflow coincide con el script."""
        from scripts.release_bootstrap import MAX_REARM_DEPTH

        workflow = (
            ROOT / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("{1.." + str(MAX_REARM_DEPTH) + "}", workflow)
if __name__ == "__main__":
    unittest.main()

