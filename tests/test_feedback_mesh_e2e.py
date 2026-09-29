import copy
import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from evolution.autonomy import AutonomyEngine, CapabilityScope
from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.engine import EvolutionEngine
from lab.factory_lab import evaluate_shadow
from metricas.review_efficiency import build_report, build_shadow_candidate
from scripts.politica_kit import load_policy


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "feedback" / "data" / "feedback-mesh-e2e.json"
BASELINE = ROOT / "metricas" / "datos" / "review-efficiency-baseline.jsonl"
SHA = re.compile(r"^[0-9a-f]{40}$")


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    required = {
        "version",
        "scenario",
        "baseline_fixture",
        "evidence",
        "stable_policy",
        "decision",
        "authority",
        "rollback",
    }
    if not isinstance(data, dict) or set(data) != required or data["version"] != 1:
        raise ValueError("manifest inválido")
    if data["scenario"] != "review-efficiency-insufficient-evidence":
        raise ValueError("scenario inválido")
    if data["baseline_fixture"] != "metricas/datos/review-efficiency-baseline.jsonl":
        raise ValueError("baseline_fixture inválido")
    if not isinstance(data["evidence"], list) or len(data["evidence"]) != 5:
        raise ValueError("evidence inválida")

    allowed_kinds = {
        "factory_baseline_pr",
        "consumer_review_pr",
        "shadow_experiment_pr",
        "next_execution",
    }
    for item in data["evidence"]:
        if set(item) != {
            "kind",
            "repo",
            "pr",
            "state",
            "head_sha",
            "merge_sha",
            "merged_at",
            "verification_run",
            "verification_status",
        }:
            raise ValueError("evidence item inválido")
        if item["kind"] not in allowed_kinds:
            raise ValueError("evidence kind inválido")
        if not isinstance(item["repo"], str) or "/" not in item["repo"]:
            raise ValueError("repo inválido")
        if type(item["pr"]) is not int or item["pr"] <= 0:
            raise ValueError("pr inválido")
        if SHA.fullmatch(item["head_sha"]) is None:
            raise ValueError("head_sha inválido")
        if item["state"] == "merged":
            if not isinstance(item["merge_sha"], str) or SHA.fullmatch(item["merge_sha"]) is None:
                raise ValueError("merged requiere merge_sha")
            if not isinstance(item["merged_at"], str):
                raise ValueError("merged requiere merged_at")
            datetime.fromisoformat(item["merged_at"].replace("Z", "+00:00"))
        elif item["state"] == "open":
            if item["merge_sha"] is not None or item["merged_at"] is not None:
                raise ValueError("open no puede declarar merge")
        else:
            raise ValueError("state inválido")
        if item["verification_run"] is None:
            if item["verification_status"] is not None:
                raise ValueError("verification_status sin run")
        else:
            if type(item["verification_run"]) is not int or item["verification_run"] <= 0:
                raise ValueError("verification_run inválido")
            if item["verification_status"] != "success":
                raise ValueError("verification_status inválido")

    if data["stable_policy"] != {
        "review_round_limit": 3,
        "source": "scripts/politica_kit.py",
        "changed": False,
    }:
        raise ValueError("stable_policy inválida")
    if data["decision"] != {
        "status": "reject",
        "reason": "insufficient_evidence",
        "promotion_executed": False,
    }:
        raise ValueError("decision inválida")
    if data["authority"]["expanded"] is not False:
        raise ValueError("authority no puede expandirse")
    if data["authority"]["external_permissions_added"] != []:
        raise ValueError("external permissions prohibidos")
    if set(data["authority"]["forbidden"]) != {
        "money",
        "legal",
        "personal_data",
        "irreversible_delete",
    }:
        raise ValueError("authority forbidden inválida")
    if data["rollback"] != {
        "reversible": True,
        "strategy": "restore_baseline",
    }:
        raise ValueError("rollback inválido")
    return data


def baseline_rows():
    return [
        json.loads(line)
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def protected(value=1.0):
    return {name: value for name in PROTECTED_INVARIANTS}


def constitution_candidate(report_fingerprint):
    return {
        "version": 1,
        "changes": [
            {
                "path": "evolution_state.thresholds.review_round_limit_low_risk",
                "operation": "add",
                "value": {
                    "stable": 3,
                    "candidate": 2,
                    "mode": "shadow",
                    "report_fingerprint": report_fingerprint,
                },
            }
        ],
        "evidence": [
            "pl0n3r/Factory#163",
            "pl0n3r/Factory#256",
            f"review-efficiency:{report_fingerprint}",
        ],
        "rollback": {
            "reversible": True,
            "strategy": "restore_baseline",
        },
    }


class FeedbackMeshE2ETests(unittest.TestCase):
    def test_manifest_uses_real_typed_evidence_without_falsifying_state(self):
        data = load_manifest()
        refs = {(item["repo"], item["pr"]): item for item in data["evidence"]}
        self.assertEqual(
            refs[("pl0n3r/Factory", 253)]["merge_sha"],
            "34409905f874b118b973ec316041467534fe2cd6",
        )
        self.assertEqual(refs[("pl0n3r/GrindFlow", 181)]["state"], "open")
        self.assertIsNone(refs[("pl0n3r/GrindFlow", 181)]["merge_sha"])
        self.assertEqual(
            refs[("pl0n3r/Factory", 256)]["merge_sha"],
            "3d5752bd33cfae73380610e30c5f9de9740af11f",
        )
        self.assertEqual(
            refs[("pl0n3r/Factory", 326)]["verification_run"],
            36503410235,
        )

    def test_review_baseline_replays_factory_and_consumer_evidence(self):
        rows = baseline_rows()
        report = build_report(rows)
        self.assertTrue(report["baseline_reproducible"])
        repos = {row["repo"] for row in rows}
        self.assertIn("pl0n3r/factory", {repo.lower() for repo in repos})
        self.assertIn("pl0n3r/grindflow", {repo.lower() for repo in repos})
        factory = [row for row in rows if row["repo"].lower() == "pl0n3r/factory"]
        consumer = [row for row in rows if row["repo"].lower() == "pl0n3r/grindflow"]
        self.assertEqual({row["pr"] for row in factory}, {253})
        self.assertEqual({row["pr"] for row in consumer}, {181})
        cohort_keys = {
            (
                cohort["key"]["repo"],
                cohort["key"]["task_type"],
                cohort["key"]["surface"],
                cohort["key"]["risk"],
                cohort["key"]["provider"],
                cohort["key"]["policy_id"],
            )
            for cohort in report["cohorts"]
        }
        self.assertEqual(len(cohort_keys), len(report["cohorts"]))

    def test_insufficient_evidence_rejects_change_and_keeps_stable_policy(self):
        data = load_manifest()
        report = build_report(baseline_rows(), min_samples=3)
        factory_key = next(
            cohort["key"]
            for cohort in report["cohorts"]
            if cohort["key"]["repo"].lower() == "pl0n3r/factory"
        )
        result = build_shadow_candidate(
            report=report,
            cohort_key=factory_key,
            stable_sha="34409905f874b118b973ec316041467534fe2cd6",
            candidate_sha="3d5752bd33cfae73380610e30c5f9de9740af11f",
            protected_stable=protected(),
            protected_candidate=protected(),
        )
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["mutation_allowed"])
        self.assertEqual(result["external_writes"], [])
        self.assertEqual(data["decision"]["status"], "reject")
        self.assertFalse(data["decision"]["promotion_executed"])
        self.assertFalse(data["stable_policy"]["changed"])
        self.assertEqual(load_policy(root=ROOT)["review_round_limit"], 3)

    def test_candidate_preserves_constitution_evolution_fitness_and_rollback_lineage(self):
        report = build_report(baseline_rows(), min_samples=3)
        candidate = constitution_candidate(report["fingerprint"])
        fingerprint = validate_candidate(candidate)
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")

        stable_metrics = {
            **{
                name: {"value": 1.0, "direction": "higher"}
                for name in PROTECTED_INVARIANTS
            },
            "review_cost": {"value": None, "direction": "lower"},
        }
        candidate_metrics = copy.deepcopy(stable_metrics)
        shadow = evaluate_shadow(
            stable_sha="34409905f874b118b973ec316041467534fe2cd6",
            candidate_sha="3d5752bd33cfae73380610e30c5f9de9740af11f",
            stable_metrics=stable_metrics,
            candidate_metrics=candidate_metrics,
            constitution_candidate=candidate,
        )
        self.assertEqual(shadow["fitness"]["claim"], "inconclusive")
        self.assertFalse(shadow["promotion"]["ready"])
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])

        engine = EvolutionEngine(
            candidate,
            reason="real review evidence produced a bounded hypothesis",
            evidence=["pl0n3r/Factory#163", "pl0n3r/Factory#256"],
        )
        for stage in (
            "remember",
            "learn",
            "propose",
            "shadow",
            "experiment",
            "validate",
        ):
            engine.transition(
                stage,
                reason=f"feedback-mesh:{stage}",
                evidence=[f"pl0n3r/Factory#333@event:{stage}"],
            )
        decision = engine.transition(
            "promote_or_reject",
            reason="sample remains insufficient for policy promotion",
            evidence=[
                f"fitness:{shadow['fitness']['fingerprint']}",
                f"shadow:{shadow['fingerprint']}",
            ],
            decision="reject",
        )
        self.assertEqual(decision.decision, "reject")
        self.assertEqual(engine.current.stage, "promote_or_reject")
        self.assertTrue(candidate["rollback"]["reversible"])
        self.assertEqual(candidate["rollback"]["strategy"], "restore_baseline")
        self.assertTrue(all(
            row.candidate_fingerprint == fingerprint for row in engine.history
        ))

    def test_feedback_loop_never_expands_authority(self):
        data = load_manifest()
        engine = AutonomyEngine(
            CapabilityScope(
                name="review-efficiency",
                authority_class="operational",
            ),
            reason="observe real review evidence",
            evidence=["pl0n3r/Factory#163"],
        )
        snapshot = engine.snapshot()
        self.assertFalse(data["authority"]["expanded"])
        self.assertEqual(snapshot["authority"]["external_permissions_added"], [])
        self.assertEqual(
            set(snapshot["authority"]["forbidden_external_authority"]),
            {"money", "legal", "personal_data", "irreversible_delete"},
        )
        self.assertEqual(snapshot["level"], "observe")

    def test_next_real_execution_keeps_stable_review_policy(self):
        data = load_manifest()
        experiment = next(
            item for item in data["evidence"]
            if item["kind"] == "shadow_experiment_pr"
        )
        next_runs = [
            item for item in data["evidence"]
            if item["kind"] == "next_execution"
        ]
        experiment_at = datetime.fromisoformat(
            experiment["merged_at"].replace("Z", "+00:00")
        )
        self.assertEqual([item["pr"] for item in next_runs], [325, 326])
        self.assertTrue(all(
            datetime.fromisoformat(item["merged_at"].replace("Z", "+00:00"))
            > experiment_at
            for item in next_runs
        ))
        self.assertEqual(next_runs[-1]["verification_status"], "success")
        self.assertEqual(load_policy(root=ROOT)["review_round_limit"], 3)
        self.assertFalse(data["stable_policy"]["changed"])

    def test_e2e_is_deterministic_offline_and_fails_closed_on_inconsistent_refs(self):
        first = load_manifest()
        second = load_manifest()
        encoded_first = json.dumps(first, sort_keys=True, separators=(",", ":"))
        encoded_second = json.dumps(second, sort_keys=True, separators=(",", ":"))
        self.assertEqual(encoded_first, encoded_second)
        self.assertEqual(
            hashlib.sha256(encoded_first.encode()).hexdigest(),
            hashlib.sha256(encoded_second.encode()).hexdigest(),
        )

        with patch(
            "socket.socket",
            side_effect=AssertionError("network is outside #333"),
        ):
            report = build_report(baseline_rows())
            self.assertTrue(report["baseline_reproducible"])

        broken = copy.deepcopy(first)
        consumer = next(
            item for item in broken["evidence"]
            if item["repo"] == "pl0n3r/GrindFlow"
        )
        consumer["state"] = "merged"
        tmp = MANIFEST.read_text(encoding="utf-8")
        try:
            MANIFEST.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "merged requiere merge_sha"):
                load_manifest()
        finally:
            MANIFEST.write_text(tmp, encoding="utf-8")

    def test_docs_describe_complete_feedback_mesh_loop_without_parallel_engine(self):
        text = (ROOT / "docs" / "feedback-mesh-e2e.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "#161",
            "#248",
            "ejecución real → evidencia → observación → hipótesis → candidato → Factory Lab → Fitness → rechazo → siguiente ejecución",
            "insufficient_evidence",
            "review_round_limit=3",
            "GrindFlow PR #181",
            "Permanece open",
            "no crear un motor nuevo",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
