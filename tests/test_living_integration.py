from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
LIVING = (ROOT / "docs" / "factory-living-software.md").read_text(encoding="utf-8")


class LivingIntegrationTests(unittest.TestCase):
    def test_plan_and_readme_reference_living_software_contract(self):
        self.assertIn("## 9. Living Software: ciclo operativo canónico", PLAN)
        self.assertIn("## Living Software", README)
        self.assertIn("docs/factory-living-software.md", README)
        self.assertIn("Project DNA", PLAN)
        self.assertIn("Factory Lab", PLAN)

    def test_protocol_preserves_human_authority_boundaries(self):
        combined = "\n".join((PLAN, LIVING))
        for boundary in (
            "Dinero",
            "legal",
            "datos reales/personales",
            "borrado irreversible",
            "publicación/live",
        ):
            self.assertIn(boundary, combined)
        self.assertIn("no sustituye puertas humanas", PLAN)
        self.assertIn("no amplía autoridad", PLAN)

    def test_protocol_defines_observe_learn_experiment_adopt_prune_cycle(self):
        cycle = (
            "observe → learn → experiment → adopt_or_reject → measure → prune"
        )
        self.assertIn(cycle, README)
        self.assertIn(cycle, LIVING)
        self.assertIn("promote_or_reject", LIVING)
        self.assertIn("rollback", LIVING)

    def test_docs_do_not_claim_unimplemented_capabilities(self):
        combined = "\n".join((PLAN, README, LIVING))
        for issue in ("#209", "#211", "#213", "#215"):
            self.assertIn(issue, combined)
        self.assertIn("#143 permanece abierto", PLAN)
        self.assertIn("#143 debe permanecer abierto", README)
        self.assertIn("#143 permanece abierto", LIVING)

        forbidden_claims = (
            "autonomía segura/completa",
            "promoción verificada end-to-end",
            "self-healing confiable/production-ready",
            "ciclo autónomo completo listo",
        )
        lowered = combined.casefold()
        for claim in forbidden_claims:
            self.assertNotIn(claim.casefold(), lowered)

        self.assertIn("#209", LIVING)
        self.assertIn("cerrado", LIVING)
        for issue in ("#211", "#213", "#215"):
            self.assertIn(issue, LIVING)
        self.assertIn("pendiente", LIVING)
        self.assertIn("#157 no habilita promoción autónoma adicional", LIVING)


if __name__ == "__main__":
    unittest.main()
