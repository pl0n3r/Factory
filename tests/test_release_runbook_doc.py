"""AC-01: pasos y trampas del release v1.x respaldados por workflows."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/release-runbook.md"
WINDOW = ROOT / ".github/workflows/release-window.yml"
BOOTSTRAP = ROOT / ".github/workflows/release-bootstrap.yml"
REUSABLE = ROOT / ".github/workflows/release.yml"


class ReleaseRunbookDocTests(unittest.TestCase):
    def test_runbook_covers_steps_and_known_traps(self):
        doc = DOC.read_text(encoding="utf-8")
        window = WINDOW.read_text(encoding="utf-8")
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        reusable = REUSABLE.read_text(encoding="utf-8")

        for number in range(1, 6):
            self.assertRegex(doc, rf"(?m)^## {number}\. ")
        for term in (
            "config/version.json",
            "tests/test_release_candidate_<X_Y_Z>.py",
            "revision-juridica/00-LEEME.md",
            "revision-juridica/paquete-completo.md",
            "scripts/generar_revision_juridica.py --check",
            "gh workflow run release-window.yml",
            "gh workflow run release-bootstrap.yml",
            "expected_sha=latest",
            "gate_issue=",
            "/decidir A",
            "/decidir B",
            "revalidation_required",
            "Ventana de release Factory",
            "require_exact_main_success: command not found",
            "ya apunta a otro commit",
            "64",
            "403/429",
            "CI factory",
            "Sonar CI-based",
            "Evidencia CodeQL",
            "Compatibilidad de consumidores",
            "reusable-release-watchdog.yml",
            "channel-ready",
            "self-test",
            "refs/tags/v1",
            "ruleset",
        ):
            with self.subTest(term=term):
                self.assertIn(term, doc)

        self.assertNotIn("gh workflow run factory-release-window.yml", doc)
        self.assertNotIn("force=true", doc)
        self.assertIn("name: Factory Release Window", window)
        self.assertIn("name: Release Factory v1.x", bootstrap)
        self.assertIn("expected_sha:", bootstrap)
        self.assertIn("gate_issue:", bootstrap)
        self.assertIn("factory-release", window)
        self.assertIn("require_exact_main_success()", bootstrap)
        self.assertIn("factory_bootstrap:", reusable)
        self.assertIn("workflow_dispatch:", window)

    def test_runbook_never_converts_manual_gates_into_agent_authority(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("Solo el OWNER", doc)
        self.assertIn("**no mueve §v1§**".replace("§", chr(96)), doc)
        self.assertIn("segundo bootstrap", doc)
        self.assertIn("fallo **histórico**", doc)
        self.assertIn("no equivale", doc)


if __name__ == "__main__":
    unittest.main()
