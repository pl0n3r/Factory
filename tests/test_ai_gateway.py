#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from intelligence.ai_gateway import AIGatewayError, execute_capability, route_capability
from producto.feedback import validate_execution_feedback


def item(**overrides):
    value = {
        "work_id": "work-ai-1", "origin_mode": "automatic", "origin_system": "factory",
        "group_id": "group-ai", "work_type": "engineering",
        "requested_capabilities": ["coding", "code_review"],
        "required_roles": ["ingenieria-software"], "authority_level": "standard",
        "producer_ref": "factory#274", "priority_class": "high", "depends_on": [],
        "claims": ["scripts/example.py"], "policy_ref": "aegis/ai-gateway-v1",
        "evidence_refs": ["evidence/source-1"], "idempotency_key": "ai-gateway-e2e",
        "venture_id": "factory", "project_id": "ai-gateway",
        "repository_ref": "pl0n3r/Factory", "budget_ref": "capital/factory-ai",
    }
    value.update(overrides)
    return value


def policy(**overrides):
    value = {
        "max_cost": 2.0, "data_classification": "internal",
        "min_quality": 70, "min_security": 80,
        "allowed_providers": ["manual", "openai", "codex"], "max_attempts": 2,
    }
    value.update(overrides)
    return value


def adapter(provider="manual", model="human-assisted", executor="chatgpt-web", kind="manual", **overrides):
    value = {
        "provider": provider, "model": model, "executor": executor, "kind": kind,
        "capabilities": ["coding"], "authority_levels": ["standard"],
        "data_level": "internal", "cost": 0.0, "quality": 80, "security": 90,
        "latency_ms": 500, "outcome": "success", "governed": True, "workspace": None,
    }
    value.update(overrides)
    return value


class AIGatewayTests(unittest.TestCase):
    def test_routes_capability_without_hardcoded_model(self):
        routed = route_capability(item(), capability="coding", policy=policy(), adapters=[
            adapter(provider="openai", model="model-a", executor="api-a", kind="api", cost=1.0),
            adapter(),
        ])
        self.assertEqual(routed["eligible"][0].provider, "manual")
        self.assertNotIn("model", item())

    def test_manual_and_provider_share_execution_contract(self):
        manual = execute_capability(item(), capability="coding", policy=policy(), adapters=[adapter()], observed_at="2026-09-28T02:00:00Z")
        api = execute_capability(item(), capability="coding", policy=policy(), adapters=[adapter(provider="openai", model="model-a", executor="api-a", kind="api", cost=1.0)], observed_at="2026-09-28T02:00:00Z")
        fields = {"status", "work_id", "capability", "provider", "model", "executor", "kind", "actual_cost", "feedback"}
        self.assertTrue(fields <= set(manual) and fields <= set(api))

    def test_execution_evidence_is_attributable(self):
        result = execute_capability(item(), capability="coding", policy=policy(), adapters=[adapter()], observed_at="2026-09-28T02:00:00Z")
        self.assertEqual((result["venture_id"], result["project_id"]), ("factory", "ai-gateway"))
        self.assertEqual(result["feedback"]["executor_ref"], "manual/chatgpt-web")

    def test_budget_gate_fails_closed(self):
        with self.assertRaisesRegex(AIGatewayError, "budget-blocked"):
            route_capability(item(), capability="coding", policy=policy(max_cost=0.1), adapters=[adapter(cost=1.0)])

    def test_data_policy_and_authority_fail_closed(self):
        with self.assertRaisesRegex(AIGatewayError, "data-policy-blocked"):
            route_capability(item(), capability="coding", policy=policy(data_classification="confidential"), adapters=[adapter()])
        with self.assertRaisesRegex(AIGatewayError, "authority-not-allowed"):
            route_capability(item(authority_level="production-write"), capability="coding", policy=policy(), adapters=[adapter()])
        with self.assertRaises(AIGatewayError):
            route_capability({**item(), "api_key": "forbidden"}, capability="coding", policy=policy(), adapters=[adapter()])

    def test_provider_failure_uses_bounded_auditable_fallback(self):
        result = execute_capability(item(), capability="coding", policy=policy(max_attempts=2), adapters=[
            adapter(provider="openai", model="model-a", executor="api-a", kind="api", cost=0.5, outcome="rate_limited"),
            adapter(cost=1.0),
        ], observed_at="2026-09-28T02:00:00Z")
        self.assertEqual(result["provider"], "manual")
        self.assertEqual([x["outcome"] for x in result["route_trace"]], ["rate_limited", "success"])

    def test_fallback_never_violates_minimum_quality_or_security(self):
        result = execute_capability(item(), capability="coding", policy=policy(min_quality=80, min_security=90), adapters=[
            adapter(provider="openai", model="model-a", executor="api-a", kind="api", cost=0.5, outcome="unavailable", quality=90, security=95),
            adapter(model="weak", executor="weak", cost=0.6, quality=20, security=95),
            adapter(model="safe", executor="safe", cost=0.7, quality=85, security=95),
        ], observed_at="2026-09-28T02:00:00Z")
        self.assertEqual(result["model"], "safe")
        self.assertIn({"provider": "manual", "model": "weak", "reason": "quality-below-minimum"}, result["rejected"])

    def test_coding_adapter_is_governed_not_parallel(self):
        codex = adapter(provider="codex", model="coding-agent", executor="codex-cli", kind="codex", cost=0.2, workspace="pl0n3r/Factory")
        self.assertEqual(route_capability(item(), capability="coding", policy=policy(), adapters=[codex])["eligible"][0].kind, "codex")
        with self.assertRaisesRegex(AIGatewayError, "codex-outside-factory"):
            route_capability(item(), capability="coding", policy=policy(), adapters=[{**codex, "governed": False}])

    def test_e2e_workitem_routing_execution_cost_feedback(self):
        work = item()
        result = execute_capability(work, capability="coding", policy=policy(), adapters=[
            adapter(provider="openai", model="model-a", executor="api-a", kind="api", cost=0.31)
        ], observed_at="2026-09-28T02:00:00Z")
        feedback = validate_execution_feedback(result["feedback"], work, now=datetime(2026, 9, 28, 2, 1, tzinfo=timezone.utc))
        self.assertEqual(result["actual_cost"], 0.31)
        self.assertEqual((feedback["work_id"], feedback["status"]), ("work-ai-1", "success"))


if __name__ == "__main__":
    unittest.main()
