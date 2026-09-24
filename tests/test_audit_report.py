#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "docs/auditoria-pre-v1.md").read_text(encoding="utf-8")
SHA = "4b2be9fcf827278631caa3e3e68603b6e2a680d7"
ALLOWED = {
    "DEMOSTRADO",
    "IMPLEMENTADO PERO NO DEMOSTRADO",
    "PARCIAL",
    "BLOQUEADO",
    "AUSENTE",
    "NO APLICA",
}


class AuditReportTests(unittest.TestCase):
    def test_report_has_required_scope_and_sha(self):
        self.assertIn(SHA, REPORT)
        for section in (
            "## Resumen ejecutivo",
            "### Seguridad y supply chain",
            "### Arquitectura",
            "### Testing / QA",
            "### Performance",
            "### CI/CD",
            "### Release Engineering",
            "### Observabilidad / SRE / resiliencia",
            "### Privacidad y datos",
            "### Documentación / DX",
            "### Costos",
            "## Readiness v1.0.0",
        ):
            self.assertIn(section, REPORT)

    def test_high_findings_reference_issues(self):
        self.assertRegex(REPORT, r"AUD-REL-001[\s\S]+?\*\*Issue:\*\* #82")
        self.assertRegex(REPORT, r"AUD-SEC-002[\s\S]+?\*\*Issue:\*\* #83")
        self.assertIn("**Severidad:** ALTO", REPORT)

    def test_report_has_prioritization_and_discarded_findings(self):
        for section in (
            "## Priorización impacto vs esfuerzo",
            "## Quick wins",
            "## Puede esperar después de v1.0",
            "## Falsos positivos / candidatos descartados",
        ):
            self.assertIn(section, REPORT)
        self.assertIn("AUD-SC-003", REPORT)
        self.assertIn("AUD-DX-004", REPORT)
        self.assertIn("AUD-COST-006", REPORT)

    def test_readiness_matrix_uses_closed_status_vocabulary(self):
        section = REPORT.split("## Readiness v1.0.0", 1)[1].split(
            "## Priorización impacto vs esfuerzo", 1
        )[0]
        rows = [line for line in section.splitlines() if line.startswith("| ")][2:]
        self.assertGreater(len(rows), 5)
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertGreaterEqual(len(cells), 3)
            self.assertIn(cells[1], ALLOWED)


if __name__ == "__main__":
    unittest.main()
