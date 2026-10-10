"""AC-01..04, fixtures puros de Factory #1112."""
import json
import unittest
from scripts.plan_incidente_cola import (
    CAUSES, REPOSITORIES, IncidentPlanError, plan_incidente_cola,
    report_from_diagnosis,
)


def report(*, state="queue_empty", available=0, capacity=4, remaining=5000):
    rows = [{"name": n, "open_issues": 1, "available": 0, "blocked": 1}
            for n in REPOSITORIES]
    causes = {c: 0 for c in CAUSES}
    causes["dependency"] = 7
    if available:
        rows[0]["available"] = available
        rows[0]["open_issues"] = available + 1
        causes["dependency"] = 7
    return {"version": 1, "state": state, "complete": True,
            "available_total": available, "open_total": 7 + available,
            "agent_capacity": capacity, "rate_limit": {"limit": 5000, "remaining": remaining},
            "blocked_cause_totals": causes,
            "roadmap_candidates": ([] if state == "budget_deferred" else
                [{"repository": "Factory", "issue": 42, "cause": "dependency"}]),
            "repositories": rows}


def upstream_diagnosis(*, state="queue_empty", available=0, capacity=4):
    """Forma exacta de salida #1098, con evidencias sinteticas y privadas."""
    sample = report(state=state, available=available, capacity=capacity)
    repositories = {}
    for row in sample["repositories"]:
        name = row["name"]
        causes = {c: 0 for c in CAUSES}
        causes["dependency"] = row["blocked"]
        counts = {"available": row["available"], "reserved": 0,
                  "blocked": row["blocked"], "planned": 0, "in_review": 0}
        repositories[name] = {
            "open_issues": row["open_issues"],
            "counts": counts,
            "blocked_reasons": [{
                "issue": 42 if name == "Factory" else 100 + REPOSITORIES.index(name),
                "cause": "dependency", "roadmap": name == "Factory",
            }],
            "blocked_cause_counts": causes,
        }
    reason = {"queue_empty": "zero_available",
              "below_capacity": "fewer_ready_than_capacity",
              "healthy": "reported_capacity_sufficient",
              "unknown_capacity": "capacity_not_observed",
              "budget_deferred": "rate_limit_below_20_percent"}[state]
    return {"version": 1, "state": state, "reason": reason,
            "available_total": available, "open_total": 7 + available,
            "agent_capacity": capacity,
            "blocked_cause_totals": sample["blocked_cause_totals"],
            "repositories": repositories,
            "roadmap_candidates": ([] if state == "budget_deferred" else sample["roadmap_candidates"]),
            "omitted_candidates": 0,
            "can_dispatch": (state != "budget_deferred" and available > 0
                             and capacity is not None and capacity > 0),
            "publication_allowed": False}


class PlanIncidenteColaTests(unittest.TestCase):
    def test_queue_empty_generates_offline_proposal(self):
        one = plan_incidente_cola(report())
        two = plan_incidente_cola(report())
        self.assertEqual(one, two)
        self.assertEqual(one["action"], "create")
        self.assertEqual(one["reason"], "new_incident_proposal")
        self.assertEqual(one["available_total"], 0)
        self.assertEqual(one["roadmap_candidates"], [
            {"repository": "Factory", "issue": 42, "cause": "dependency"}])
        self.assertFalse(one["can_publish"])
        self.assertNotIn("body", one)
        envelope = report_from_diagnosis(
            upstream_diagnosis(), {"limit": 5000, "remaining": 5000})
        self.assertEqual(plan_incidente_cola(envelope), one)
        self.assertEqual(set(envelope["repositories"][0]),
                         {"name", "open_issues", "available", "blocked"})
        # #1098 preserva roadmap=True en causas no accionables, pero
        # jamás las promueve a roadmap_candidates ni a capacidad disponible.
        for cause in ("human_gate", "planned", "unknown"):
            with self.subTest(non_actionable_cause=cause):
                diagnostic = upstream_diagnosis()
                item = diagnostic["repositories"]["Factory"]
                item["blocked_reasons"][0]["cause"] = cause
                item["blocked_cause_counts"]["dependency"] = 0
                item["blocked_cause_counts"][cause] = 1
                diagnostic["blocked_cause_totals"]["dependency"] = 6
                diagnostic["blocked_cause_totals"][cause] = 1
                diagnostic["roadmap_candidates"] = []
                adapted = report_from_diagnosis(
                    diagnostic, {"limit": 5000, "remaining": 5000})
                plan = plan_incidente_cola(adapted)
                self.assertEqual(plan["action"], "create")
                self.assertEqual(plan["roadmap_candidates"], [])
                self.assertEqual(plan["blocked_cause_totals"][cause], 1)
                self.assertFalse(plan["can_publish"])

    def test_deduplicates_previous_incident_without_writes(self):
        original = plan_incidente_cola(report())
        prev = {"issue_number": 204, "fingerprint": original["fingerprint"]}
        same = plan_incidente_cola(report(), prev)
        self.assertEqual(same["action"], "noop")
        self.assertEqual(same["reason"], "unchanged_incident")
        self.assertEqual(same["previous_issue_number"], 204)
        changed = report()
        changed["roadmap_candidates"] = []
        updated = plan_incidente_cola(changed, prev)
        self.assertEqual(updated["action"], "update")
        self.assertFalse(updated["can_publish"])

    def test_low_budget_and_unknown_state_fail_closed(self):
        deferred = report(state="budget_deferred", remaining=999)
        plan = plan_incidente_cola(deferred)
        self.assertEqual(plan["action"], "deferred")
        self.assertFalse(plan["can_publish"])
        self.assertEqual(plan["roadmap_candidates"], [])
        altered = report(state="budget_deferred", remaining=999)
        altered["roadmap_candidates"] = [{
            "repository": "Factory", "issue": 42, "cause": "dependency",
        }]
        with self.assertRaisesRegex(IncidentPlanError, "inconsistent_candidate_budget"):
            plan_incidente_cola(altered)
        envelope = report_from_diagnosis(
            upstream_diagnosis(state="budget_deferred"),
            {"limit": 5000, "remaining": 999})
        self.assertEqual(plan_incidente_cola(envelope)["action"], "deferred")
        for invalid in (report(state="unknown"), report(remaining=999),
                        report(state="budget_deferred", remaining=1000)):
            with self.subTest(invalid=invalid["state"]), self.assertRaises(IncidentPlanError):
                plan_incidente_cola(invalid)
        healthy = report(state="healthy", available=1, capacity=1)
        self.assertEqual(plan_incidente_cola(healthy)["action"], "noop")
        below = report(state="below_capacity", available=1, capacity=4)
        self.assertEqual(plan_incidente_cola(below)["action"], "create")
        unknown_cap = report(state="unknown_capacity", available=1, capacity=None)
        self.assertEqual(plan_incidente_cola(unknown_cap)["action"], "noop")

    def test_invalid_evidence_and_privacy_fail_closed(self):
        bad_cases = []
        sample = report()
        sample["secret"] = "private-value"
        bad_cases.append(sample)
        sample = report()
        sample["repositories"][0]["open_issues"] = 200
        bad_cases.append(sample)
        sample = report()
        sample["blocked_cause_totals"]["claims"] = True
        bad_cases.append(sample)
        sample = report()
        sample["roadmap_candidates"][0]["cause"] = "human_gate"
        bad_cases.append(sample)
        sample = report()
        sample["repositories"][1]["name"] = "Factory"
        bad_cases.append(sample)
        sample = report()
        sample["repositories"][0].update(open_issues=0, blocked=0)
        sample["repositories"][1].update(open_issues=2, blocked=2)
        # Totales globales consistentes, pero candidato Factory sin bloqueos.
        bad_cases.append(sample)
        for case in bad_cases:
            with self.subTest(case=str(case)[:75]), self.assertRaises(IncidentPlanError):
                plan_incidente_cola(case)
        for old in ({"issue_number": True, "fingerprint": "a"*64},
                    {"issue_number": 5, "fingerprint": "my-secret"}):
            with self.assertRaisesRegex(IncidentPlanError, "invalid_previous"):
                plan_incidente_cola(report(), old)
        private = plan_incidente_cola(report())
        self.assertEqual(set(private), {"version", "action", "reason", "fingerprint",
            "previous_issue_number", "available_total", "open_total",
            "blocked_cause_totals", "roadmap_candidates", "can_publish"})
        self.assertNotIn("private", json.dumps(private))
        self.assertFalse(private["can_publish"])
        invalid = upstream_diagnosis()
        invalid["roadmap_candidates"][0]["issue"] = 999999
        with self.assertRaisesRegex(IncidentPlanError, "unverified_candidate"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        invalid = upstream_diagnosis()
        invalid["can_dispatch"] = True
        with self.assertRaisesRegex(IncidentPlanError, "inconsistent_dispatch_signal"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        # Una lista truncada y orden alterado no puede pasar como inventario
        # completo, aunque todos los elementos pertenezcan a blockers reales.
        invalid = upstream_diagnosis()
        invalid["roadmap_candidates"] = []
        with self.assertRaisesRegex(IncidentPlanError, "incomplete_candidates"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        invalid = upstream_diagnosis()
        invalid["repositories"]["Condor"]["blocked_reasons"][0]["roadmap"] = True
        invalid["roadmap_candidates"].append({
            "repository": "Condor", "issue": 101, "cause": "dependency",
        })
        invalid["roadmap_candidates"].reverse()
        with self.assertRaisesRegex(IncidentPlanError, "incomplete_candidates"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        # 33 candidatos legítimos => los 32 primeros y un único omitido.
        valid = upstream_diagnosis()
        factory = valid["repositories"]["Factory"]
        factory["blocked_reasons"] = [
            {"issue": n, "cause": "dependency", "roadmap": True}
            for n in range(1, 34)
        ]
        factory["counts"]["blocked"] = 33
        factory["open_issues"] = 33
        factory["blocked_cause_counts"]["dependency"] = 33
        valid["blocked_cause_totals"]["dependency"] = 39
        valid["open_total"] = 39
        valid["roadmap_candidates"] = [
            {"repository": "Factory", "issue": n, "cause": "dependency"}
            for n in range(1, 33)
        ]
        valid["omitted_candidates"] = 1
        envelope = report_from_diagnosis(valid, {"limit": 5000, "remaining": 5000})
        self.assertEqual(len(plan_incidente_cola(envelope)["roadmap_candidates"]), 32)
        invalid = upstream_diagnosis()
        invalid["omitted_candidates"] = 1
        with self.assertRaisesRegex(IncidentPlanError, "incomplete_candidates"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        invalid = upstream_diagnosis()
        invalid["blocked_cause_totals"]["claims"] = False  # False == 0 in Python
        with self.assertRaisesRegex(IncidentPlanError, "inconsistent_diagnosis_causes"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        # A malicious diagnostic reason may raise in __ne__; only fixed
        # private error codes are allowed at the trust boundary.
        class HostileReason:
            def __ne__(self, other):
                raise RuntimeError("private-reason-sentinel")
        invalid = upstream_diagnosis()
        invalid["reason"] = HostileReason()
        with self.assertRaisesRegex(IncidentPlanError, "invalid_diagnosis_state"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        invalid = upstream_diagnosis()
        invalid["available_total"] = "private-value"
        with self.assertRaisesRegex(IncidentPlanError, "invalid_diagnosis"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})
        invalid = upstream_diagnosis()
        invalid["roadmap_candidates"][0]["issue"] = []
        with self.assertRaisesRegex(IncidentPlanError, "unverified_candidate"):
            report_from_diagnosis(invalid, {"limit": 5000, "remaining": 5000})


if __name__ == "__main__":
    unittest.main()
