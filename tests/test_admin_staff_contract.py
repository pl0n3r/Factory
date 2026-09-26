"""Contrato Factory D-060 para administración de staff."""
import hashlib
import hmac
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SPEC_PATH = TEMPLATE / "ops" / "admin-staff-api.json"
DOC_PATH = ROOT / "docs" / "admin-staff-api.md"


def load_json(path: Path):
    """Carga un artefacto JSON versionado del contrato Factory."""
    return json.loads(path.read_text(encoding="utf-8"))


class AdminStaffContractTests(unittest.TestCase):
    """Verifica que D-060 sea portable, fail-closed y criptográficamente determinista."""
    def test_d060_is_consistent_in_root_template_and_plan(self):
        root = load_json(ROOT / "decisiones.yml")
        template = load_json(TEMPLATE / "decisiones.yml")
        for data in (root, template):
            rows = [row for row in data["decisions"] if row["id"] == "D-060"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "active")
            self.assertIn("staff", rows[0]["text"])
            self.assertIn("clientes finales", rows[0]["text"])
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("D-060 — administración de staff", plan)
        self.assertIn("ControlBot nunca define ni recibe contraseñas/tokens", plan)

    def test_documented_api_is_staff_only_and_fail_closed(self):
        doc = DOC_PATH.read_text(encoding="utf-8")
        for route in (
            "/ops/staff", "/ops/staff/{id}/suspend",
            "/ops/staff/{id}/reactivate", "/ops/staff/{id}/role",
            "/ops/staff/{id}/password-reset", "/ops/summary",
        ):
            self.assertIn(route, doc)
        self.assertIn("clientes finales", doc)
        self.assertIn("ControlBot nunca define, recibe ni devuelve contraseñas", doc)
        self.assertIn("2–120 caracteres", doc)
        self.assertIn("nunca supera 100", doc)
        self.assertIn("HTTPS con validación de certificado", doc)
        self.assertIn("HMAC aporta autenticidad e integridad", doc)
        self.assertIn("preservando claves repetidas", doc)
        self.assertIn("RFC 3986", doc)
        self.assertIn("clave de idempotencia", doc)
        self.assertIn("Idempotency-Key", doc)
        self.assertIn("exactamente un `=` crudo", doc)
        self.assertIn("no registra ninguna ruta `/ops`", doc)
        self.assertIn("responde `404`", doc)
        self.assertNotIn("DELETE /ops/staff/{id}", doc)
        self.assertIn("autoridad protegida", doc)
        self.assertIn("octetos crudos", doc)
        self.assertIn("86.400 s", doc)
        self.assertIn("handoff server-side", doc)

    def test_template_stub_requires_security_controls(self):
        spec = load_json(SPEC_PATH)
        self.assertFalse(spec["enabled_by_default"])
        self.assertFalse(spec["scope"]["physical_delete"])
        self.assertFalse(spec["scope"]["bulk_export"])
        self.assertEqual(spec["authentication"]["mode"], "hmac-sha256")
        self.assertEqual(spec["authentication"]["method_normalization"], "ASCII_UPPERCASE")
        self.assertEqual(spec["authentication"]["body_hash_source"], "raw_request_body_bytes_before_decode")
        self.assertEqual(spec["authentication"]["body_hash_encoding"], "sha256_hex_lowercase_64")
        self.assertEqual(spec["authentication"]["canonical_request_encoding"], "UTF-8")
        self.assertEqual(spec["authentication"]["line_separator"], "LF")
        self.assertEqual(spec["authentication"]["signature_encoding"], "hex_lowercase_64")
        self.assertTrue(spec["authentication"]["json_reserialization_forbidden"])
        self.assertEqual(spec["authentication"]["key_scope"], "per_product")
        self.assertEqual(spec["authentication"]["key_source"], "environment")
        self.assertTrue(spec["authentication"]["constant_time_compare"])
        self.assertTrue(spec["authentication"]["fail_closed_without_key"])
        routes = spec["authentication"]["route_registration"]
        self.assertTrue(routes["requires_configured_key"])
        self.assertTrue(routes["requires_allowlist"])
        self.assertEqual(routes["disabled_behavior"], "routes_absent_404")
        self.assertTrue(spec["authentication"]["allowlist_required"])
        self.assertEqual(spec["transport"]["scheme"], "https")
        self.assertTrue(spec["transport"]["certificate_validation_required"])
        self.assertTrue(spec["transport"]["cleartext_http_forbidden"])
        self.assertFalse(spec["transport"]["hmac_provides_confidentiality"])
        self.assertEqual(
            spec["authentication"]["canonical_request"],
            "KEY_ID\nMETHOD\nPATH_WITH_SORTED_QUERY\nTIMESTAMP\nNONCE\nSHA256(BODY)",
        )
        query = spec["authentication"]["query_canonicalization"]
        self.assertEqual(query["representation"], "ordered_pairs")
        self.assertTrue(query["preserve_duplicate_keys"])
        self.assertTrue(query["preserve_empty_values"])
        self.assertTrue(query["raw_plus_forbidden"])
        self.assertEqual(query["space_encoding"], "%20")
        self.assertEqual(query["literal_plus_encoding"], "%2B")
        self.assertEqual(query["reencode"], "RFC3986")
        self.assertEqual(query["percent_hex_case"], "uppercase")
        self.assertEqual(query["sort"], ["encoded_name", "encoded_value"])
        self.assertEqual(query["pair_format"], "name=value")
        self.assertEqual(query["raw_pair_separator"], "&")
        self.assertEqual(query["raw_name_value_separator"], "=")
        self.assertTrue(query["exactly_one_raw_equals_per_pair"])
        self.assertTrue(query["reject_missing_equals"])
        self.assertTrue(query["reject_empty_names"])
        self.assertEqual(query["literal_equals_encoding"], "%3D")
        self.assertTrue(query["reject_malformed_percent_escapes"])
        self.assertEqual(query["percent_decode_passes"], 1)
        self.assertTrue(query["omit_question_mark_when_empty"])
        self.assertTrue(spec["mutations"]["idempotency_key_required"])
        self.assertEqual(spec["mutations"]["idempotency_key_location"], "header")
        self.assertEqual(spec["mutations"]["idempotency_key_header"], "Idempotency-Key")
        self.assertTrue(spec["mutations"]["replay_nonce_is_not_idempotency"])
        self.assertEqual(spec["mutations"]["idempotency_scope"], ["product", "actor_key_id", "action", "target"])
        self.assertEqual(spec["mutations"]["fingerprint_encoding"], "sha256_hex_lowercase_64")
        self.assertGreaterEqual(spec["mutations"]["retention_min_seconds"], 86400)
        self.assertNotEqual(spec["mutations"]["retention_min_seconds"], spec["authentication"]["nonce_ttl_seconds"])
        self.assertTrue(spec["mutations"]["store_result_with_fingerprint"])
        self.assertEqual(spec["mutations"]["equivalent_retry"], "return_same_logical_result_without_side_effect")
        self.assertEqual(spec["mutations"]["mismatched_fingerprint_status"], 409)
        self.assertTrue(spec["mutations"]["nonce_ttl_is_separate"])
        self.assertTrue(
            spec["mutations"]["invalidate_active_authority_on_suspend_or_privilege_reduction"]
        )
        self.assertLessEqual(spec["authentication"]["max_clock_skew_seconds"], 300)
        self.assertGreaterEqual(spec["authentication"]["nonce_min_bits"], 128)
        self.assertGreaterEqual(
            spec["authentication"]["nonce_ttl_seconds"],
            spec["authentication"]["max_clock_skew_seconds"],
        )
        self.assertEqual(spec["authentication"]["replay_policy"], "reject_reuse_per_key")
        self.assertTrue(spec["rate_limit"]["required"])
        self.assertTrue(spec["audit"]["required"])
        self.assertLessEqual(spec["pagination"]["max_limit"], 100)
        self.assertTrue(spec["pagination"]["cursor_required_after_first_page"])
        self.assertFalse(spec["pagination"]["unlimited"])
        self.assertFalse(spec["search"]["empty_query_allowed"])
        self.assertGreaterEqual(spec["search"]["min_query_length"], 2)
        self.assertLessEqual(spec["search"]["max_query_length"], 120)
        self.assertTrue(spec["authentication"]["rotation_supported"])
        self.assertTrue(spec["authentication"]["revocation_immediate"])
        self.assertNotIn("DELETE", {row["method"] for row in spec["operations"]})
        self.assertTrue(spec["scope"]["protected_subject_mutation_forbidden"])
        self.assertIn("owner", spec["scope"]["protected_subjects"])
        self.assertIn("platform_owner", spec["scope"]["protected_roles"])
        self.assertTrue(spec["scope"]["product_role_mapping_required"])
        self.assertTrue(spec["invitation_delivery"]["server_side_handoff_required"])
        self.assertTrue(spec["invitation_delivery"]["success_requires_handoff"])
        self.assertFalse(spec["invitation_delivery"]["token_in_response"])
        self.assertEqual(spec["invitation_delivery"]["failure_policy"], "fail_and_leave_no_usable_invitation")
        composer = load_json(TEMPLATE / "composer.json")
        self.assertIn("admin_staff_contract.php", composer["scripts"]["test"])

    def test_hmac_known_answer_vector(self):
        """El fixture común fija bytes, hash y firma interoperables."""
        spec = load_json(SPEC_PATH)
        fixture = spec["authentication"]["known_answer"]
        body = fixture["body"].encode("utf-8")
        self.assertEqual(hashlib.sha256(body).hexdigest(), fixture["body_sha256"])
        canonical = fixture["canonical_request"]
        self.assertEqual(
            canonical,
            "\n".join([
                fixture["key_id"], fixture["method"], fixture["path_with_sorted_query"],
                fixture["timestamp"], fixture["nonce"], fixture["body_sha256"],
            ]),
        )
        signature = hmac.new(
            fixture["key"].encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(signature, fixture["signature"])

    def test_template_privacy_declares_minimum_staff_treatment(self):
        spec = load_json(SPEC_PATH)
        privacy = spec["privacy"]
        self.assertEqual(
            privacy["activation"],
            "copy_required_treatments_to_datos_yml_before_enabling",
        )
        self.assertTrue(privacy["legal_review_before_live"])
        self.assertEqual(
            {row["id"] for row in privacy["required_treatments"]},
            {"staff_identity", "staff_contact", "staff_access_metadata"},
        )
        for row in privacy["required_treatments"]:
            self.assertEqual(row["basis"], "review_required")
            self.assertEqual(row["consent"], "review_required")
            self.assertEqual(row["providers"], [])
        data = load_json(TEMPLATE / "datos.yml")
        self.assertEqual(data["phase"], "construccion")
        self.assertTrue(
            all(value == "[COMPLETAR POR EL DUEÑO]" for value in data["controller"].values())
        )


if __name__ == "__main__":
    unittest.main()
