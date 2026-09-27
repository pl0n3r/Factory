"""Baseline sanitizado y shadow para eficiencia marginal de revisión."""
from __future__ import annotations
import hashlib
import json
import re
from collections import defaultdict
from statistics import mean
from typing import Any
from evolution.constitution import PROTECTED_INVARIANTS
from lab.factory_lab import evaluate_shadow
from scripts.politica_kit import review_counts_as_round
STABLE_REVIEW_ROUND_LIMIT = 3
CANDIDATE_REVIEW_ROUND_LIMIT = 2
FINDING_CLASSES = frozenset({
    "valid_fixed", "valid_no_change", "duplicate", "administrative",
    "false_positive", "deferred", "unknown",
})
SEVERITIES = ("none", "low", "medium", "high", "critical")
OBS_FIELDS = frozenset({
    "repo", "pr", "issue", "sha", "task_type", "surface", "risk", "provider",
    "review_state", "round", "findings", "rework_commits", "added_minutes",
    "tokens", "ci_minutes", "escaped_defect", "incident_after",
    "rollback_after", "result_ref",
})
FINDING_FIELDS = frozenset({"id", "classification", "severity", "material", "change_ref"})
SLUG = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REF = re.compile(r"^[A-Za-z0-9._:/#@-]{1,180}$")
class ReviewEfficiencyError(ValueError):
    pass
def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()
def _number(value: Any, field: str, optional: bool = False) -> int | float | None:
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ReviewEfficiencyError(f"{field}: número >= 0 o null requerido")
    return value
def _tri(value: Any, field: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ReviewEfficiencyError(f"{field}: booleano o null requerido")
def _finding(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != FINDING_FIELDS:
        raise ReviewEfficiencyError("finding: esquema inválido")
    if not isinstance(raw["id"], str) or SLUG.fullmatch(raw["id"]) is None:
        raise ReviewEfficiencyError("finding.id inválido")
    if raw["classification"] not in FINDING_CLASSES:
        raise ReviewEfficiencyError("finding.classification inválida")
    if raw["severity"] not in SEVERITIES or not isinstance(raw["material"], bool):
        raise ReviewEfficiencyError("finding: severity/material inválidos")
    ref = raw["change_ref"]
    if ref is not None and (not isinstance(ref, str) or REF.fullmatch(ref) is None):
        raise ReviewEfficiencyError("finding.change_ref inválida")
    return dict(raw)
def _validate_identity(raw: dict[str, Any]) -> None:
    if not isinstance(raw["repo"], str) or REPO.fullmatch(raw["repo"]) is None:
        raise ReviewEfficiencyError("repo inválido")
    invalid_number = lambda value: isinstance(value, bool) or not isinstance(value, int) or value < 1
    if any(invalid_number(raw[name]) for name in ("pr", "issue")):
        raise ReviewEfficiencyError("pr/issue inválidos")
    if not isinstance(raw["sha"], str) or SHA.fullmatch(raw["sha"]) is None:
        raise ReviewEfficiencyError("sha inválido")
def _validate_context(raw: dict[str, Any]) -> None:
    for name in ("task_type", "surface", "provider"):
        if not isinstance(raw[name], str) or SLUG.fullmatch(raw[name]) is None:
            raise ReviewEfficiencyError(f"{name} inválido")
    if raw["risk"] not in {"low", "medium", "high", "critical", "unknown"}:
        raise ReviewEfficiencyError("risk inválido")
    if raw["review_state"] not in {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}:
        raise ReviewEfficiencyError("review_state inválido")
    number = raw["round"]
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= STABLE_REVIEW_ROUND_LIMIT:
        raise ReviewEfficiencyError("round inválida")
    if not isinstance(raw["result_ref"], str) or REF.fullmatch(raw["result_ref"]) is None:
        raise ReviewEfficiencyError("result_ref inválida")
def _validate_findings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    values = raw["findings"]
    if not isinstance(values, list) or len(values) > 50:
        raise ReviewEfficiencyError("findings inválidos")
    findings = [_finding(row) for row in values]
    if len({row["id"] for row in findings}) != len(findings):
        raise ReviewEfficiencyError("finding.id duplicado")
    return findings
def validate_observation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != OBS_FIELDS:
        raise ReviewEfficiencyError("observation: esquema inválido")
    _validate_identity(raw)
    _validate_context(raw)
    row = dict(raw)
    row["findings"] = _validate_findings(raw)
    row["rework_commits"] = _number(raw["rework_commits"], "rework_commits", optional=True)
    for name in ("added_minutes", "tokens", "ci_minutes"):
        row[name] = _number(raw[name], name, optional=True)
    for name in ("escaped_defect", "incident_after", "rollback_after"):
        row[name] = _tri(raw[name], name)
    return row
def is_substantive_review(observation: dict[str, Any]) -> bool:
    row = validate_observation(observation)
    return review_counts_as_round({"state": row["review_state"], "body": "sanitized-finding" if row["findings"] else ""})
def _complete_mean(values: list[int | float | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return round(mean(value for value in values if value is not None), 4)
def _rate(values: list[bool | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return round(sum(bool(value) for value in values) / len(values), 4)
def _dimensions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    findings = [finding for row in rows for finding in row["findings"]]
    counts = {name: sum(f["classification"] == name for f in findings) for name in FINDING_CLASSES}
    material = [f["severity"] for f in findings if f["material"] and f["classification"] in {"valid_fixed", "valid_no_change"}]
    return {
        "quality": {"findings": len(findings), "valid_fixed": counts["valid_fixed"], "material_valid": len(material), "escaped_defect_rate": _rate([r["escaped_defect"] for r in rows])},
        "cost": {"rework_commits_avg": _complete_mean([r["rework_commits"] for r in rows]), "added_minutes_avg": _complete_mean([r["added_minutes"] for r in rows]), "tokens_avg": _complete_mean([r["tokens"] for r in rows]), "ci_minutes_avg": _complete_mean([r["ci_minutes"] for r in rows])},
        "risk": {"max_material_severity": max(material, key=SEVERITIES.index) if material else None, "incident_rate": _rate([r["incident_after"] for r in rows]), "rollback_rate": _rate([r["rollback_after"] for r in rows])},
        "noise": {name: counts[name] for name in ("duplicate", "administrative", "false_positive", "deferred", "unknown")},
    }
def build_report(records: list[dict[str, Any]], min_samples: int = 3) -> dict[str, Any]:
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 1:
        raise ReviewEfficiencyError("min_samples inválido")
    rows = [validate_observation(row) for row in records]
    substantive = [row for row in rows if is_substantive_review(row)]
    repos = {row["repo"].lower() for row in substantive}
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["repo"], row["task_type"], row["surface"], row["risk"], row["provider"])].append(row)
    cohorts = []
    for key, items in sorted(grouped.items()):
        useful = [row for row in items if is_substantive_review(row)]
        by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in useful:
            by_round[row["round"]].append(row)
        samples = len({(row["repo"], row["pr"]) for row in useful})
        lineage = [{"pr": f"{row['repo']}#{row['pr']}", "sha": row["sha"], "round": row["round"], "finding": f["id"], "classification": f["classification"], "change": f["change_ref"], "result": row["result_ref"]} for row in sorted(useful, key=lambda item: (item["pr"], item["round"], item["sha"])) for f in row["findings"]]
        cohorts.append({
            "key": dict(zip(("repo", "task_type", "surface", "risk", "provider"), key)),
            "samples": samples,
            "sample_status": "eligible" if samples >= min_samples else "insufficient_data",
            "administrative_events": len(items) - len(useful),
            "rounds": {str(n): _dimensions(group) for n, group in sorted(by_round.items())},
            "policy_recommendation": None,
            "lineage": lineage,
        })
    report = {"version": 1, "min_samples": min_samples, "records": len(rows), "baseline_reproducible": "pl0n3r/factory" in repos and any(repo != "pl0n3r/factory" for repo in repos), "cohorts": cohorts}
    report["fingerprint"] = _hash(report)
    return report
def _sum_cost(cohort: dict[str, Any], rounds: range, field: str) -> float | None:
    values = [cohort["rounds"].get(str(number), {}).get("cost", {}).get(field) for number in rounds]
    return None if any(value is None for value in values) else round(sum(values), 4)
def build_shadow_candidate(*, report: dict[str, Any], cohort_key: dict[str, str], stable_sha: str, candidate_sha: str, protected_stable: dict[str, float | int | None], protected_candidate: dict[str, float | int | None]) -> dict[str, Any]:
    cohort = next((item for item in report["cohorts"] if item["key"] == cohort_key), None)
    base = {"stable_review_round_limit": 3, "candidate_review_round_limit": 2, "mutation_allowed": False, "external_writes": []}
    if cohort is None or not report["baseline_reproducible"] or cohort["sample_status"] != "eligible" or cohort["key"]["risk"] != "low" or "3" not in cohort["rounds"]:
        return {"status": "insufficient_evidence", **base}
    if set(protected_stable) != set(PROTECTED_INVARIANTS) or set(protected_candidate) != set(PROTECTED_INVARIANTS):
        raise ReviewEfficiencyError("protected metrics incompletas")
    stable_metrics = {name: {"value": protected_stable[name], "direction": "higher"} for name in PROTECTED_INVARIANTS}
    candidate_metrics = {name: {"value": protected_candidate[name], "direction": "higher"} for name in PROTECTED_INVARIANTS}
    for field, dimension in (("rework_commits_avg", "review_rework"), ("added_minutes_avg", "review_minutes"), ("tokens_avg", "review_tokens"), ("ci_minutes_avg", "review_ci_minutes")):
        stable_metrics[dimension] = {"value": _sum_cost(cohort, range(1, 4), field), "direction": "lower"}
        candidate_metrics[dimension] = {"value": _sum_cost(cohort, range(1, 3), field), "direction": "lower"}
    constitution_candidate = {
        "version": 1,
        "changes": [{"path": "evolution_state.thresholds.review_round_limit_low_risk", "operation": "add", "value": {"stable": 3, "candidate": 2, "mode": "shadow", "cohort": cohort["key"], "report_fingerprint": report["fingerprint"]}}],
        "evidence": ["pl0n3r/factory#163", f"review-efficiency:{report['fingerprint']}"],
        "rollback": {"reversible": True, "strategy": "restore_baseline"},
    }
    shadow = evaluate_shadow(stable_sha=stable_sha, candidate_sha=candidate_sha, stable_metrics=stable_metrics, candidate_metrics=candidate_metrics, constitution_candidate=constitution_candidate)
    if shadow["fitness"]["protected_regressions"]:
        status = "blocked"
    elif shadow["promotion"]["ready"]:
        status = "shadow_candidate"
    else:
        status = "insufficient_evidence"
    return {"status": status, **base, "constitution_candidate": constitution_candidate, "lab": shadow}
