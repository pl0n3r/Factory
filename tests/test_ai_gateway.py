#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from intelligence.ai_gateway import AIGatewayError, execute_capability, route_capability
from producto.feedback import validate_execution_feedback


def work_item(**overrides):
    payload = {
        "work_id": "work-ai-1",
        "origin_mode": "automatic",
        "origin_system": "factory",
        "group_id": "group-ai",
        "work_type": "engineering",
        "requested_capabilities": ["coding", "code_review"],
        "required_roles": ["ingenieria-software"],
        "authority_level": "standard",
        "producer_ref": "factory#274",
        "priority_class": "high",
        "depends_on": [],
        "claims": ["scripts/example.py"],
        "policy_ref": "aegis/ai-gateway-v1",
        "evidence_refs": ["evidence/source-1"],
        "idempotency_key": "ai-gateway-e2e",
        "venture_id": "factory",
        "project_id": "ai-gateway",
        "repository_ref": "pl0n3r/Factory",
        "budget_ref": "capital/factory-ai",
    }
    payload.update(overrides)
    return payload


def policy(**overrides):
    value = {
        "max_cost": 2.0,
        "data_classification": "internal",
        "min_quality": 70,
        "min_security": 80,
        "allowed_providers": ["manual", "openai", "codex"],
        "max_attempts": 2,
    }
    value.update(overrides)
    return value


def adapter(
    provider="manual",
    model="human-assisted",
    executor="chatgpt-web",
    kind="manual",
    **overrides,
):
    value = {
        "provider": provider,
        "model": model,
        "executor": executor,
        "kind": kind,
        "capabilities": ["coding"],
        "authority_levels": ["standard"],
        "max_data_classification": "internal",
        "estimated_cost": 0.0,
        "quality": 80,
        "security": 90,
        "latency_ms": 500,
        "available": True,
        "fallback_allowed": True,
        "outcome": "success",
        "actual_cost": 0.0,
        "governed_by_factory": True,
        "workspace_ref": None,
    }
    value.update(overrides)
    return value


class AIGatewayTests(unittest.TestCase):
    def test_routes_capability_without_hardcoded_model(self):
        routed = route_capability(
            work_item(),
            capability="coding",
            policy=policy(),
            adapters=[
                adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=1.0),
                adapter(provider="manual", model="human-assisted", executor="chatgpt-web", estimated_cost=0.0),
            ],
        )
        self.assertEqual(routed["capability"], "coding")
        self.assertEqual(routed["eligible"][0].provider, "manual")
        self.assertNotIn("model", work_item())

    def test_manual_and_provider_share_execution_contract(self):
        manual = execute_capability(
            work_item(), capability="coding", policy=policy(),
            adapters=[adapter()],
            observed_at="2026-09-28T02:00:00Z",
        )
        api = execute_capability(
            work_item(), capability="coding", policy=policy(),
            adapters=[adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=1.0, actual_cost=0.8)],
            observed_at="2026-09-28T02:00:00Z",
        )
        contract = {"status", "work_id", "capability", "provider", "model", "executor", "kind", "estimated_cost", "actual_cost", "feedback"}
        self.assertTrue(contract <= set(manual))
        self.assertTrue(contract <= set(api))

    def test_execution_evidence_is_attributable(self):
        result = execute_capability(
            work_item(), capability="coding", policy=policy(), adapters=[adapter()],
            observed_at="2026-09-28T02:00:00Z",
        )
        self.assertEqual(result["venture_id"], "factory")
        self.assertEqual(result["project_id"], "ai-gateway")
        self.assertEqual(result["feedback"]["executor_ref"], "manual/chatgpt-web")
        self.assertTrue(result["evidence_refs"])

    def test_budget_gate_fails_closed(self):
        with self.assertRaisesRegex(AIGatewayError, "budget-blocked"):
            route_capability(
                work_item(), capability="coding", policy=policy(max_cost=0.1),
                adapters=[adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=1.0)],
            )

    def test_data_policy_and_authority_fail_closed(self):
        with self.assertRaisesRegex(AIGatewayError, "data-policy-blocked"):
            route_capability(
                work_item(), capability="coding",
                policy=policy(data_classification="confidential"),
                adapters=[adapter(max_data_classification="internal")],
            )
        with self.assertRaisesRegex(AIGatewayError, "authority-not-allowed"):
            route_capability(
                work_item(authority_level="production-write"), capability="coding",
                policy=policy(), adapters=[adapter(authority_levels=["standard"])],
            )
        with self.assertRaises(AIGatewayError):
            route_capability(
                {**work_item(), "api_key": "sk-" + "x" * 24},
                capability="coding", policy=policy(), adapters=[adapter()],
            )

    def test_provider_failure_uses_bounded_auditable_fallback(self):
        result = execute_capability(
            work_item(), capability="coding", policy=policy(max_attempts=2),
            adapters=[
                adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=0.5, outcome="rate_limited"),
                adapter(provider="manual", model="human-assisted", executor="chatgpt-web", estimated_cost=1.0),
            ],
            observed_at="2026-09-28T02:00:00Z",
        )
        self.assertEqual(result["provider"], "manual")
        self.assertEqual([row["outcome"] for row in result["route_trace"]], ["rate_limited", "success"])
        self.assertEqual(len(result["route_trace"]), 2)

    def test_fallback_never_violates_minimum_quality_or_security(self):
        result = execute_capability(
            work_item(), capability="coding",
            policy=policy(min_quality=80, min_security=90, max_attempts=2),
            adapters=[
                adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=0.5, outcome="unavailable", quality=90, security=95),
                adapter(provider="manual", model="weak", executor="weak", estimated_cost=0.6, quality=20, security=95),
                adapter(provider="manual", model="safe", executor="safe", estimated_cost=0.7, quality=85, security=95),
            ],
            observed_at="2026-09-28T02:00:00Z",
        )
        self.assertEqual(result["model"], "safe")
        rejected = {entry["model"]: entry["reason"] for entry in result["rejected"]}
        self.assertEqual(rejected["weak"], "quality-below-minimum")

    def test_coding_adapter_is_governed_not_parallel(self):
        codex = adapter(
            provider="codex", model="coding-agent", executor="codex-cli", kind="codex",
            estimated_cost=0.2, workspace_ref="pl0n3r/Factory", governed_by_factory=True,
        )
        routed = route_capability(work_item(), capability="coding", policy=policy(), adapters=[codex])
        self.assertEqual(routed["eligible"][0].kind, "codex")
        with self.assertRaisesRegex(AIGatewayError, "codex-outside-factory"):
            route_capability(
                work_item(), capability="coding", policy=policy(),
                adapters=[{**codex.__dict__, "capabilities": list(codex.capabilities), "authority_levels": list(codex.authority_levels), "governed_by_factory": False}],
            )

    def test_e2e_workitem_routing_execution_cost_feedback(self):
        item = work_item()
        result = execute_capability(
            item, capability="coding", policy=policy(),
            adapters=[adapter(provider="openai", model="model-a", executor="api-a", kind="api", estimated_cost=0.4, actual_cost=0.31)],
            observed_at="2026-09-28T02:00:00Z",
        )
        feedback = validate_execution_feedback(
            result["feedback"],
            item,
            now=datetime(2026, 9, 28, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(result["actual_cost"], 0.31)
        self.assertEqual(feedback["work_id"], item["work_id"])
        self.assertEqual(feedback["status"], "success")


if __name__ == "__main__":
    unittest.main()
