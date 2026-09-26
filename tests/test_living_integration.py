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
        forbidden_claims = (
            "autonomía segura/completa",
            "promoción verificada end-to-end",
            "self-healing confiable/production-ready",
            "ciclo autónomo completo listo",
        )
        lowered = combined.casefold()
        for claim in forbidden_claims:
            self.assertNotIn(claim.casefold(), lowered)

    def test_all_living_hardenings_are_documented_closed(self):
        hardenings = ("#209", "#211", "#213", "#215", "#221", "#223")
        for issue in hardenings:
            self.assertIn(issue, PLAN)
            self.assertIn(issue, README)
            self.assertIn(issue, LIVING)

        for fragment in (
            "**#209** — Autonomy authority + evidencia canónica: ✅ cerrado",
            "**#211** — Factory Lab promotion provenance: ✅ cerrado",
            "**#213** — Growth/Pruning source evidence: ✅ cerrado",
            "**#215** — Repair human authority + immunity provenance: ✅ cerrado",
            "**#221** — retry de renovación v2: ✅ cerrado",
            "**#223** — provenance confiable de Repair/Immune: ✅ cerrado",
        ):
            self.assertIn(fragment, PLAN)

        self.assertNotIn("#211 Factory Lab promotion provenance:** 🚧 pendiente", README)
        self.assertNotIn("#213 Growth/Pruning source evidence:** 🚧 pendiente", README)
        self.assertNotIn("#215 Repair human authority + immunity provenance:** 🚧 pendiente", README)
        self.assertNotIn("#211 — Factory Lab promotion provenance:** pendiente", LIVING)
        self.assertNotIn("#213 — Growth/Pruning source evidence:** pendiente", LIVING)
        self.assertNotIn("#215 — Repair human authority + immunity provenance:** pendiente", LIVING)

    def test_completed_hardening_does_not_expand_external_authority(self):
        combined = "\n".join((PLAN, README, LIVING))
        for boundary in (
            "dinero",
            "legal",
            "datos reales/personales",
            "borrado irreversible",
            "publicación/live",
        ):
            self.assertIn(boundary, combined.casefold())
        self.assertIn("no amplía autoridad", README)
        self.assertIn("automatic_execution_allowed=false", LIVING)
        self.assertIn("execution=not-performed", LIVING)
        self.assertIn("continúa fallando cerrado", PLAN)

    def test_epic_completion_is_structural_not_unbounded_production_authority(self):
        combined = "\n".join((PLAN, README, LIVING))
        self.assertIn(
            "arquitectura/protocolo Living Software está integrada y endurecida",
            PLAN,
        )
        self.assertIn(
            "arquitectura/protocolo Living Software integrado y endurecido",
            README,
        )
        self.assertIn(
            "arquitectura/protocolo Living Software integrado y endurecido",
            LIVING,
        )
        self.assertIn("producción autónoma irrestricta", combined)
        self.assertIn("no una concesión de producción autónoma irrestricta", LIVING)


if __name__ == "__main__":
    unittest.main()
