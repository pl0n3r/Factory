#!/usr/bin/env python3
import unittest
from pathlib import Path
from scripts.roles_kit import REQUIRED_ROLES, load_catalog, parse_checklist
ROOT=Path(__file__).resolve().parents[1]
ROLES=ROOT/"agentes"/"roles"
class RoleProfilesV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=load_catalog()
    def test_all_profiles_expose_seniority_stack_and_judgment(self):
        self.assertTrue(REQUIRED_ROLES <= set(self.catalog))
        for slug in REQUIRED_ROLES:
            content=(ROLES/f"{slug}.md").read_text(encoding="utf-8")
            self.assertIn("## Experiencia simulada y especialidades",content)
            self.assertIn("Seniority simulado:",content)
            self.assertIn("Especialidades:",content)
            self.assertIn("Superficies de decisión:",content)
    def test_all_profiles_expose_mature_team_sections(self):
        headings=("## Investigación inicial","## Heurísticas y trade-offs","## Señales de excelencia","## Red flags y colaboración")
        for slug in REQUIRED_ROLES:
            content=(ROLES/f"{slug}.md").read_text(encoding="utf-8")
            for heading in headings: self.assertIn(heading,content)
    def test_existing_checklist_contract_stays_compatible(self):
        for slug in REQUIRED_ROLES:
            self.assertGreaterEqual(len(parse_checklist((ROLES/f"{slug}.md").read_text(encoding="utf-8"))),3)
    def test_profiles_remain_operational_not_decorative(self):
        for slug in REQUIRED_ROLES:
            content=(ROLES/f"{slug}.md").read_text(encoding="utf-8")
            self.assertIn("evidencia",content.lower()); self.assertIn("trade-off",content.lower()); self.assertIn("## Checklist",content)
if __name__=="__main__": unittest.main()
