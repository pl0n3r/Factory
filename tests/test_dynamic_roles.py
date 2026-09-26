#!/usr/bin/env python3
import unittest
from scripts.roles_kit import CANDIDATE_REQUIRED_FIELDS,RoleError,compile_team,load_catalog,propose_role_candidate,register_role_candidate,validate_role_candidate
def ctx(title="",body="",files=None,labels=None): return {"title":title,"body":body,"files":files or [],"labels":labels or []}
class DynamicRolesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=load_catalog()
    def test_task_context_compiles_different_professional_team(self):
        backend=compile_team(ctx(title="Symfony auth hardening",body="PHP Symfony on Hostinger with MariaDB",files=["src/Auth.php",".github/workflows/deploy.yml"]),self.catalog)
        product=compile_team(ctx(title="Definir onboarding",body="Problema de usuario y métrica",labels=["tipo: producto"]),self.catalog)
        self.assertIn("Staff php/symfony Engineer",backend["contextual_profiles"]); self.assertIn("Hostinger SRE",backend["contextual_profiles"]); self.assertEqual(product["primary"],"producto"); self.assertNotEqual(backend["roles"],product["roles"]); self.assertTrue(backend["trace"]["signals"])
    def test_missing_capability_generates_traceable_role_candidate(self):
        candidate=propose_role_candidate(ctx(title="Android client",body="Kotlin mobile app",files=["app/MainActivity.kt"]),self.catalog)
        self.assertIsNotNone(candidate); self.assertEqual(candidate["slug"],"mobile-engineering"); self.assertIn("Señal objetiva",candidate["trigger"]); self.assertGreaterEqual(len(candidate["checklist"]),3)
    def test_candidate_must_validate_before_registration(self):
        with self.assertRaises(RoleError): validate_role_candidate({"slug":"incompleto"})
        candidate=propose_role_candidate(ctx(title="MLOps pipeline",body="PyTorch machine learning"),self.catalog)
        self.assertEqual(validate_role_candidate(candidate)["slug"],"ml-engineering")
        registry=register_role_candidate({},candidate)
        self.assertIn("ml-engineering",registry)
        self.assertEqual(set(registry["ml-engineering"]),CANDIDATE_REQUIRED_FIELDS)
        self.assertNotIn("file",registry["ml-engineering"])
        self.assertNotIn("ml-engineering",self.catalog)
    def test_candidate_slug_must_be_string(self):
        candidate=propose_role_candidate(ctx(title="MLOps pipeline",body="PyTorch machine learning"),self.catalog)
        candidate=dict(candidate); candidate["slug"]=12
        with self.assertRaises(RoleError): validate_role_candidate(candidate)
    def test_negated_capability_does_not_propose_candidate(self):
        self.assertIsNone(propose_role_candidate(ctx(title="Scope",body="No incluye machine learning"),self.catalog))
    def test_catalog_extension_can_be_selected(self):
        catalog=dict(self.catalog)
        catalog["mobile-engineering"]={"slug":"mobile-engineering","label_es":"rol: mobile-engineering","label_en":"role: mobile-engineering","file":"agentes/roles/mobile-engineering.md"}
        team=compile_team(ctx(title="Android client",body="Kotlin mobile app",files=["app/MainActivity.kt"]),catalog)
        self.assertIn("mobile-engineering",team["roles"])
    def test_schema_team_gets_eligible_reviewer(self):
        team=compile_team(ctx(files=["migrations/change.sql"]),self.catalog)
        self.assertIsNotNone(team["review"])
        self.assertNotEqual(team["review"],team["primary"])
if __name__=="__main__": unittest.main()
