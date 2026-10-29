#!/usr/bin/env python3
"""Factory #1637: sixteen coverage gaps, exercised offline and fail-closed.

A LOCAL_CONTRACT is not an approval to migrate callers, publish, deploy or
claim Living Software production. No GitHub, secrets or real customer data.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lab.factory_lab import FactoryLabError, evaluate_shadow, promotion_contract
from producto.feedback import FeedbackValidationError, validate_execution_feedback
from scripts import f2_caller_preflight as f2
from scripts.work_origin import (
    WorkOriginError, canonical_payload, idempotency_scope,
    validate_work_item, work_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
F2 = "docs/f2-caller-migration.md"
QUEUE = "docs/factory-queue.md"
LAB = "docs/factory-lab.md"
LIVING = "docs/factory-living-software.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
NOW = datetime(2026, 9, 27, 23, 0, tzinfo=timezone.utc)

# ID -> original source document and a source/matrix fragment. Do not silently
# promote the matrix; another issue owns its reconciliation.
CLAUSES = {
    "docs/f2-caller-migration.md:L16-U1": (F2, "Preservar CI, privacidad"),
    "docs/f2-caller-migration.md:L16-U2": (F2, "Ni el preflight ni su"),
    "docs/f2-caller-migration.md:L17-U1": (F2, "Un reporte `BLOCKED`"),
    "docs/f2-caller-migration.md:L17-U2": (F2, "la migración corresponde"),
    "docs/f2-caller-migration.md:L3-U1": (F2, "Esta prueba **solo lee**"),
    "docs/factory-lab.md:B06": (LAB, "laboratorio"),
    "docs/factory-living-software.md:B05": (LIVING, "lifecycle"),
    "docs/factory-living-software.md:B06": (LIVING, "puertas humanas"),
    "docs/factory-queue.md:L3-U1": (QUEUE, "Este documento describe únicamente"),
    "docs/factory-queue.md:L35-U1": (QUEUE, "El validador falla cerrado"),
    "docs/factory-queue.md:L39-U1": (QUEUE, "canonical_payload()"),
    "docs/factory-queue.md:L40-U1": (QUEUE, "work_fingerprint()"),
    "docs/factory-queue.md:L41-U1": (QUEUE, "idempotency_scope()"),
    "docs/factory-queue.md:L55-U1": (QUEUE, "Factory Queue v1 cierra"),
    "docs/factory-queue.md:L63-U1": (QUEUE, "`work_id`"),
    "docs/factory-queue.md:L64-U1": (QUEUE, "`work_fingerprint`"),
}
# Only assertions which exercise the pure production modules earn a local verdict.
# Remote adoption, external workflow inventory, deployment and full 11-phase
# lifecycle all remain UNKNOWN, even with a green CI check.
LOCAL_KEYS = {
    "docs/f2-caller-migration.md:L3-U1",
    "docs/factory-queue.md:L35-U1", "docs/factory-queue.md:L39-U1",
    "docs/factory-queue.md:L40-U1", "docs/factory-queue.md:L41-U1",
    "docs/factory-queue.md:L55-U1", "docs/factory-queue.md:L63-U1",
    "docs/factory-queue.md:L64-U1",
}


def sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8")
            for p in (MATRIX, F2, QUEUE, LAB, LIVING)}


def matrix_rows(raw: object) -> dict[str, str]:
    """Exactly 16 distinct original, unpromoted rows, no silent omissions."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: missing matrix")
    found: dict[str, str] = {}
    for key, (path, phrase) in CLAUSES.items():
        prefix = "| `" + key + "` |"
        matches = [line for line in raw.splitlines() if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError("UNKNOWN: missing/duplicate " + key)
        line = matches[0]
        # Some row descriptions contain pipes, so partition by the exact state.
        before, sep, after = line.partition(" | NO_VERIFICABLE | ")
        if not sep or not before.startswith(prefix) or not after.endswith(" |"):
            raise ValueError("UNKNOWN: promoted/malformed " + key)
        desc = before[len(prefix):].strip()
        evidence, sep2, origin = after[:-2].rpartition(" | ")
        if (not sep2 or not evidence.strip() or not origin.strip()
                or phrase.casefold() not in desc.casefold()
                or ("No se confirmó test + PR fusionado" not in evidence
                    and "Contrastado:" not in evidence)):
            raise ValueError("UNKNOWN: incomplete evidence " + key)
        found[key] = desc
    return found


def source_matches(key: str, docs: dict[str, str]) -> bool:
    if key not in CLAUSES or type(docs) is not dict:
        return False
    path, phrase = CLAUSES[key]
    raw = docs.get(path)
    if type(raw) is not str or not raw:
        return False
    line_anchor = key.split(":L", 1)
    if len(line_anchor) == 2:
        number = int(line_anchor[1].split("-", 1)[0])
        lines = raw.splitlines()
        return 0 < number <= len(lines) and phrase.casefold() in lines[number-1].casefold()
    # B-tags are scenario groups, not line numbers. Never infer runtime coverage.
    return phrase.casefold() in raw.casefold()


def item(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "work_id": "work-1637", "origin_mode": "directed",
        "origin_system": "human", "group_id": "group-synthetic",
        "venture_id": "venture-synthetic", "project_id": "factory",
        "work_type": "engineering", "requested_capabilities": ["python", "qa"],
        "required_roles": ["qa"], "authority_level": "operational",
        "producer_ref": "owner:synthetic", "priority_class": "medium",
        "depends_on": [], "claims": ["fixture:test"],
        "policy_ref": "factory:synthetic", "evidence_refs": ["fixture:origin"],
        "idempotency_key": "request-1637",
    }
    data.update(changes)
    return data


def feedback(record: dict[str, object], **changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "work_id": record["work_id"],
        "work_fingerprint": work_fingerprint(record),
        "idempotency_scope": idempotency_scope(record),
        "executor_ref": "runner:synthetic", "producer_ref": record["producer_ref"],
        "status": "success", "evidence_refs": ["artifact:synthetic"],
        "observed_at": "2026-09-27T22:58:00Z",
    }
    data.update(changes)
    return data


def proof() -> dict[str, bool]:
    """Re-exercise real source modules. False never becomes acceptance."""
    work = item()
    alt = item(origin_mode="automatic", origin_system="controlbot",
               work_id="work-other", producer_ref="controlbot:synthetic")
    normalized = validate_work_item(work)
    canonical = canonical_payload(work)
    fp = work_fingerprint(work)
    scope = idempotency_scope(work)
    equivalent = item(requested_capabilities=["qa", "python", "qa"])
    verified = validate_execution_feedback(feedback(work), work, now=NOW)

    def invalid_item(**overrides: object) -> bool:
        try:
            validate_work_item(item(**overrides))
            return False
        except WorkOriginError:
            return True

    def invalid_feedback(**overrides: object) -> bool:
        try:
            validate_execution_feedback(feedback(work, **overrides), work, now=NOW)
            return False
        except FeedbackValidationError:
            return True

    with TemporaryDirectory(prefix="factory-1637-") as scratch:
        root = Path(scratch)
        for name in f2.CONSUMERS:
            (root / name / ".github/workflows").mkdir(parents=True)
        safe = f2.audit(root, ["readme.yml"])
        caller = root / f2.CONSUMERS[0] / ".github/workflows" / "fixture.yml"
        caller.write_text(
            "jobs:\n  test:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n",
            encoding="utf-8",
        )
        blocked = f2.audit(root, ["readme.yml"])
        caller.unlink()
        (root / f2.CONSUMERS[-1] / ".github/workflows").rmdir()
        incomplete = f2.audit(root, ["readme.yml"])
    # All F2 results concern only the six synthetic checkouts, never other repos.
    f2_valid = (safe["status"] == "SAFE" and len(safe["scanned_consumers"]) == 6
                and blocked["status"] == "BLOCKED"
                and len(blocked["references"]) == 1
                and blocked["references"][0]["ref"] == "v1"
                and incomplete["status"] == "BLOCKED"
                and f2.CONSUMERS[-1] in incomplete["missing_consumers"])
    invalids = (
        invalid_item(unknown_field="synthetic"),
        invalid_item(claims=["fixture:one"] * 51),
        invalid_item(work_id=""),
        invalid_item(policy_ref="Bearer abcdefghijklmnopqrstuvwxyz"),
    )
    bad_feedback = (
        invalid_feedback(work_id="work-foreign"),
        invalid_feedback(work_fingerprint="0" * 64),
        invalid_feedback(idempotency_scope="0" * 64),
        invalid_feedback(status="running"),
        invalid_feedback(evidence_refs=[]),
        invalid_feedback(observed_at="2026-09-27T22:58:00"),
        invalid_feedback(observed_at=(NOW - timedelta(hours=25)).isoformat()),
    )
    return {
        "docs/f2-caller-migration.md:L3-U1": f2_valid,
        "docs/factory-queue.md:L35-U1": all(invalids),
        "docs/factory-queue.md:L39-U1": canonical == canonical_payload(equivalent),
        "docs/factory-queue.md:L40-U1": (
            len(fp) == 64 and fp == work_fingerprint(equivalent)
            and work_fingerprint(item(priority_class="high")) != fp),
        "docs/factory-queue.md:L41-U1": (
            scope == idempotency_scope(alt)
            and scope != idempotency_scope(item(project_id="other"))),
        "docs/factory-queue.md:L55-U1": (
            all(bad_feedback) and verified["work_fingerprint"] == fp
            and verified["idempotency_scope"] == scope),
        "docs/factory-queue.md:L63-U1": (
            normalized["work_id"] == verified["work_id"] == "work-1637"
            and bad_feedback[0]),
        "docs/factory-queue.md:L64-U1": (
            verified["work_fingerprint"] == work_fingerprint(work)
            and bad_feedback[1]),
    }


def assess(docs: object, checks: object) -> dict[str, str]:
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if type(docs) is not dict or type(checks) is not dict:
        return result
    if any(type(docs.get(p)) is not str or not docs[p]
           for p in (MATRIX, F2, QUEUE, LAB, LIVING)):
        return result
    try:
        matrix_rows(docs[MATRIX])
    except ValueError:
        return result
    if (set(checks) != LOCAL_KEYS or
            any(type(v) is not bool for v in checks.values()) or
            not all(source_matches(k, docs) for k in CLAUSES)):
        return result
    for key in LOCAL_KEYS:
        if checks[key]:
            result[key] = LOCAL
    return result


class BrechasFactory19Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs, checks = sources(), proof()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(LOCAL_KEYS, set(checks))
        self.assertTrue(all(checks.values()))
        self.assertTrue(all(source_matches(k, docs) for k in CLAUSES))
        result = assess(docs, checks)
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual(LOCAL if key in LOCAL_KEYS else UNKNOWN,
                                 result[key])

    def test_falla_cerrado(self) -> None:
        docs, checks = sources(), proof()
        for key in CLAUSES:
            row = next(line for line in docs[MATRIX].splitlines()
                       if line.startswith("| `" + key + "` |"))
            for bad in (docs[MATRIX].replace(row, "", 1),
                        docs[MATRIX] + "\n" + row,
                        docs[MATRIX].replace(row, row.replace(
                            "NO_VERIFICABLE", "CUBIERTO", 1), 1)):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(bad)
                self.assertEqual(set(assess({**docs, MATRIX: bad}, checks).values()), {UNKNOWN})
        for key in LOCAL_KEYS:
            self.assertEqual(UNKNOWN, assess(docs, {**checks, key: None})[key])
        self.assertEqual(set(assess({}, checks).values()), {UNKNOWN})
        self.assertEqual(set(assess(docs, {}).values()), {UNKNOWN})
        self.assertEqual(UNKNOWN, assess({**docs, QUEUE: ""}, checks)[
            "docs/factory-queue.md:L40-U1"])
        self.assertEqual(UNKNOWN, assess({**docs, F2: "corrupt"}, checks)[
            "docs/f2-caller-migration.md:L3-U1"])

    def test_sin_datos_reales(self) -> None:
        path = Path(__file__)
        module = ast.parse(path.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(module)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(module)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imported & {"requests", "urllib", "httpx", "socket",
                                     "subprocess", "pymysql", "mysql", "playwright"})
        self.assertTrue(all(value.startswith("artifact:") for value in
                            feedback(item())["evidence_refs"]))
        self.assertEqual("runner:synthetic", feedback(item())["executor_ref"])
        self.assertFalse(any("@" in str(v) for v in item().values()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, checks = sources(), proof()
        result = assess(docs, checks)
        self.assertEqual(UNKNOWN, assess(docs, {**checks, "CI": True})[
            "docs/factory-queue.md:L55-U1"])
        for key in set(CLAUSES) - LOCAL_KEYS:
            self.assertEqual(UNKNOWN, result[key])
        self.assertEqual(UNKNOWN, assess(docs, {**checks, "production": True})[
            "docs/factory-living-software.md:B05"])
        # A ready shadow is never authorized release or full 11-stage live run.
        candidate = {"version": 1,
                     "changes": [{"path": "evolution_state.heuristics.synthetic",
                                  "operation": "add", "value": {"state": "candidate"}}],
                     "evidence": ["pl0n3r/factory#1637"],
                     "rollback": {"reversible": True, "strategy": "revert"}}
        baseline = {name: {"value": 1.0, "direction": "higher"}
                    for name in ("security", "privacy", "traceability",
                                 "reversibility", "authority")}
        metrics = {**baseline, "reliability": {"value": 0.9, "direction": "higher"}}
        improved = {**baseline, "reliability": {"value": 0.95, "direction": "higher"}}
        args = {"stable_sha": "a" * 40, "candidate_sha": "b" * 40,
                "stable_metrics": metrics, "candidate_metrics": improved,
                "constitution_candidate": candidate}
        shadow = evaluate_shadow(**args)
        contract = promotion_contract(shadow_result=shadow, **args)
        self.assertEqual("shadow", shadow["mode"])
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual([], shadow["external_writes"])
        self.assertTrue(contract["requires_human_or_authorized_promotion"])
        self.assertEqual("not-performed", contract["execution"])
        bad = deepcopy(candidate)
        bad["changes"][0]["path"] = "stable_authority.sources"
        with self.assertRaises(FactoryLabError):
            evaluate_shadow(**{**args, "constitution_candidate": bad})
        self.assertEqual(UNKNOWN, result["docs/factory-lab.md:B06"])
        self.assertEqual(UNKNOWN, result["docs/factory-living-software.md:B06"])


if __name__ == "__main__":
    unittest.main()
