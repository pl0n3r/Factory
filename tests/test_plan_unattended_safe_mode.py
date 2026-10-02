#!/usr/bin/env python3
"""Regresiones del contrato aprobado de modo desatendido seguro."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "unattended-safe-mode.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

DIRECTED_PROMPT = (
    "Trabajas en el repositorio pl0n3r/Condor. Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "para este repositorio."
)
DISPATCH_PROMPT = (
    "Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "en modo despachador."
)


class UnattendedSafeModePlanTests(unittest.TestCase):
    def test_plan_points_to_canonical_unattended_contract(self):
        self.assertIn(
            "[docs/unattended-safe-mode.md](docs/unattended-safe-mode.md)",
            PLAN,
        )
        self.assertIn("modo desatendido seguro", PLAN)
        self.assertIn("no amplía autoridad", PLAN)
        self.assertIn(
            "Estado: **aprobado por el dueño · Tramo 4A · contrato, no runtime**",
            DOC,
        )

    def test_risk_and_incident_severity_contract_is_explicit(self):
        for level in ("**Bajo**", "**Medio**", "**Alto**"):
            self.assertIn(level, DOC)
        self.assertIn("Segunda pasada obligatoria por otro rol", DOC)
        for severity in (
            "**S1 — crítico inmediato:**",
            "**S2 — grave:**",
            "**S3 — contenido:**",
        ):
            self.assertIn(severity, DOC)
        self.assertIn("S1 y S2 interrumpen al dueño", PLAN)
        self.assertIn("S3 entra por", PLAN)
        self.assertIn("No interrumpe al dueño", DOC)

    def test_state_handoff_is_closed_and_secret_free(self):
        for field in (
            "work_identity:",
            "repository:",
            "branch:",
            "head_sha:",
            "reservation_id:",
            "risk:",
            "severity:",
            "evidence:",
            "last_state:",
            "next_action:",
            "blockers:",
            "updated_at:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, DOC)
        self.assertIn("no incluir secretos", DOC)
        self.assertIn("credenciales", DOC)
        self.assertIn("PII", DOC)
        self.assertIn("datos personales", DOC)
        self.assertIn("UNKNOWN", DOC)

    def test_slos_are_evidence_adjustable_and_never_expand_authority(self):
        self.assertIn("SLOs operativos", DOC)
        self.assertIn("objetivos configurables y ajustables con", DOC)
        self.assertIn("este contrato **no inventa defaults", DOC)
        self.assertIn("su estado es `UNKNOWN`", DOC)
        self.assertIn("marcar GREEN", DOC)
        self.assertIn(
            "SLOs son objetivos configurables y ajustables con evidencia",
            PLAN,
        )

    def test_blast_radius_keeps_sensitive_actions_fail_closed(self):
        for required in (
            "go-live",
            "gasto/pagos",
            "borrado irreversible",
            "credenciales",
            "datos reales/personales",
            "backup previo",
            "blast radius",
            "smoke rojo sostenido",
        ):
            with self.subTest(required=required):
                self.assertIn(required, DOC)
        self.assertIn("falla\ncerrado", PLAN)
        self.assertIn("Nunca se infiere presupuesto", DOC)
        self.assertIn("rollback destructivo", DOC)

    def test_tranche_four_runtime_slices_are_serial_and_bounded(self):
        order = (
            "**4A — contrato**",
            "**4B — guardas runtime:**",
            "**4C — watchdog + resumen diario:**",
            "**4D — simulacro E2E controlado:**",
        )
        positions = [DOC.index(value) for value in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Un slice posterior no se ejecuta por", DOC)
        self.assertIn(
            "guardas runtime de pausa/disyuntor/techos → watchdog +",
            PLAN,
        )
        self.assertIn("simulacro E2E controlado", PLAN)

    def test_existing_dispatch_prompts_ranking_and_human_gates_stay_frozen(self):
        self.assertEqual(README.count(DIRECTED_PROMPT), 1)
        self.assertEqual(README.count(DISPATCH_PROMPT), 1)
        ordered = (
            "HEALTH degradado",
            "Issue abierto de incidente",
            "reparación activa válida",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
        )
        positions = [PLAN.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        for gate in (
            "No gastar, publicar/live, usar datos reales ni tomar decisiones reservadas al dueño.",
            "SQL destructivo o borrado irreversible siguen requiriendo autorización.",
            "comprar, renovar o cambiar planes y pagos nunca lo hace un agente",
        ):
            self.assertIn(gate, PLAN)
        self.assertIn("[ESTADO.md](ESTADO.md)", PLAN)
        self.assertIn("ARCHIVADO · ya cumplido · no aplicar", PLAN)


if __name__ == "__main__":
    unittest.main()
