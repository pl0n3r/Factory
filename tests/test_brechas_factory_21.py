#!/usr/bin/env python3
"""Factory #1639: sixteen explicit offline gaps, no claims of remote readiness."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

from evolution.constitution import ConstitutionError, PROTECTED_INVARIANTS, validate_candidate
from lab.factory_lab import evaluate_shadow
from metricas.review_efficiency import build_report, build_shadow_candidate
from scripts.politica_kit import load_policy

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
MESH = "docs/feedback-mesh-e2e.md"
RUNNER = "docs/factoryrunner-execution-plane.md"
MANIFEST = "feedback/data/feedback-mesh-e2e.json"
BASELINE = "metricas/datos/review-efficiency-baseline.jsonl"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
TICK = chr(96)
IDS = ("L3-U1", "L10-U1", "L11-U1", "L12-U1", "L12-U2",
       "L20-U1", "L21-U1", "L22-U1", "L23-U1", "L24-U1",
       "L25-U1", "L25-U2", "L26-U1", "L27-U1", "L31-U1")
RUNNER_ID = RUNNER + ":B06"
CLAUSES = (RUNNER_ID,) + tuple(MESH + ":" + suffix for suffix in IDS)
EXTERNAL = {RUNNER_ID} | {MESH + ":" + key for key in
                        ("L10-U1", "L11-U1", "L12-U1", "L12-U2", "L27-U1")}
PROOF_FOR = {MESH + ":" + key: name for key, name in (
    ("L3-U1", "authority"), ("L20-U1", "baseline"),
    ("L21-U1", "hypothesis"), ("L22-U1", "constitution"),
    ("L23-U1", "shadow"), ("L24-U1", "fitness"),
    ("L25-U1", "insufficient"), ("L25-U2", "rejected"),
    ("L26-U1", "stable"), ("L31-U1", "authority"),
)}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def sources() -> dict[str, str]:
    return {p: read(p) for p in (MATRIX, MESH, RUNNER, MANIFEST, BASELINE)}


def matrix_rows(raw: object) -> dict[str, str]:
    """Each exact ID must occur once with original NO_VERIFICABLE state."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: matriz ilegible")
    rows = {}
    for key in CLAUSES:
        prefix = f"| {TICK}{key}{TICK} |"
        matches = [x for x in raw.splitlines() if x.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError("UNKNOWN: fila ausente o duplicada: " + key)
        before, separator, after = matches[0].partition(" | NO_VERIFICABLE | ")
        if not separator or not after.endswith(" |"):
            raise ValueError("UNKNOWN: estado ficticiamente promovido: " + key)
        evidence, sep2, origin = after[:-2].rpartition(" | ")
        description = before[len(prefix):].strip()
        if (not sep2 or not description or not evidence.strip() or not origin.strip()
                or ("No se confirmó test + PR fusionado" not in evidence
                    and "Contrastado:" not in evidence)):
            raise ValueError("UNKNOWN: evidencia inconsistente: " + key)
        rows[key] = description
    return rows


def document_contract(data: object) -> bool:
    if type(data) is not dict or any(
        type(data.get(p)) is not str or not data[p] for p in (MATRIX, MESH, RUNNER)
    ):
        return False
    try:
        rows = matrix_rows(data[MATRIX])
    except ValueError:
        return False
    lines = data[MESH].splitlines()
    for key, description in rows.items():
        if key == RUNNER_ID:
            if not all(t in data[RUNNER] for t in (
                "fallback de última opción", "evidencia técnica concreta",
                "mismo protocolo ControlBot", "no reutiliza ni transforma AutoFactory",
            )):
                return False
        else:
            line = int(key.split(":L", 1)[1].split("-U", 1)[0])
            if not 0 < line <= len(lines) or description not in lines[line - 1]:
                return False
    return True


def manifest_contract(raw: object) -> bool:
    """Validate fixed historical snapshot, never a live Github state."""
    if type(raw) is not str:
        return False
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    if (type(data) is not dict or data.get("version") != 1
            or data.get("scenario") != "review-efficiency-insufficient-evidence"
            or data.get("baseline_fixture") != BASELINE
            or type(data.get("evidence")) is not list
            or len(data["evidence"]) != 5):
        return False
    refs = {}
    for row in data["evidence"]:
        if type(row) is not dict or type(row.get("pr")) is not int:
            return False
        ref = (row.get("repo"), row["pr"])
        if (ref in refs or type(row.get("head_sha")) is not str
                or not re.fullmatch(r"[0-9a-f]{40}", row["head_sha"])):
            return False
        if row.get("state") == "open":
            if row.get("merge_sha") is not None or row.get("merged_at") is not None:
                return False
        elif row.get("state") == "merged":
            if (type(row.get("merge_sha")) is not str
                    or not re.fullmatch(r"[0-9a-f]{40}", row["merge_sha"])
                    or type(row.get("merged_at")) is not str):
                return False
        else:
            return False
        refs[ref] = row
    if set(refs) != {
        ("pl0n3r/Factory", 253), ("pl0n3r/GrindFlow", 181),
        ("pl0n3r/Factory", 256), ("pl0n3r/Factory", 325),
        ("pl0n3r/Factory", 326),
    }:
        return False
    return bool(
        refs[("pl0n3r/GrindFlow", 181)]["state"] == "open"
        and refs[("pl0n3r/GrindFlow", 181)]["head_sha"]
            == "4a85df7dffb667a476afc3103c268e5f46f0e79a"
        and refs[("pl0n3r/Factory", 256)]["merge_sha"]
            == "3d5752bd33cfae73380610e30c5f9de9740af11f"
        and refs[("pl0n3r/Factory", 326)]["merge_sha"]
            == "3b99efa32ba4fe931f053f1023b34943fe63bf14"
        and refs[("pl0n3r/Factory", 326)]["verification_run"] == 36503410235
        and refs[("pl0n3r/Factory", 326)]["verification_status"] == "success"
        and data.get("stable_policy") == {
            "review_round_limit": 3, "source": "scripts/politica_kit.py",
            "changed": False,
        }
        and data.get("decision") == {
            "status": "reject", "reason": "insufficient_evidence",
            "promotion_executed": False,
        }
        and data.get("rollback") == {
            "reversible": True, "strategy": "restore_baseline",
        }
        and data.get("authority") == {
            "expanded": False, "external_permissions_added": [],
            "forbidden": ["money", "legal", "personal_data", "irreversible_delete"],
        }
    )


def replay() -> dict[str, bool]:
    """Exercise real pure contracts using sanitized checked-in observations."""
    rows = [json.loads(line) for line in read(BASELINE).splitlines() if line.strip()]
    report = build_report(rows, min_samples=3)
    factory = next(c for c in report["cohorts"]
                   if c["key"]["repo"].lower() == "pl0n3r/factory")
    consumer = [c for c in report["cohorts"]
                if c["key"]["repo"].lower() == "pl0n3r/grindflow"]
    shadow = build_shadow_candidate(
        report=report, cohort_key=factory["key"],
        stable_sha="34409905f874b118b973ec316041467534fe2cd6",
        candidate_sha="3d5752bd33cfae73380610e30c5f9de9740af11f",
        protected_stable={name: 1.0 for name in PROTECTED_INVARIANTS},
        protected_candidate={name: 1.0 for name in PROTECTED_INVARIANTS},
    )
    candidate = {
        "version": 1,
        "changes": [{
            "path": "evolution_state.thresholds.review_round_limit_low_risk",
            "operation": "add",
            "value": {"stable": 3, "candidate": 2, "mode": "shadow",
                      "report_fingerprint": report["fingerprint"]},
        }],
        "evidence": ["pl0n3r/Factory#163", "pl0n3r/Factory#256",
                     f"review-efficiency:{report['fingerprint']}"],
        "rollback": {"reversible": True, "strategy": "restore_baseline"},
    }
    fingerprint = validate_candidate(candidate)
    metrics = {name: {"value": 1.0, "direction": "higher"}
               for name in PROTECTED_INVARIANTS}
    metrics["review_cost"] = {"value": None, "direction": "lower"}
    fitness = evaluate_shadow(
        stable_sha="34409905f874b118b973ec316041467534fe2cd6",
        candidate_sha="3d5752bd33cfae73380610e30c5f9de9740af11f",
        stable_metrics=metrics, candidate_metrics=deepcopy(metrics),
        constitution_candidate=candidate,
    )
    return {
        "baseline": report["baseline_reproducible"] is True and
                    factory["samples"] == 1 and bool(consumer),
        "hypothesis": candidate["changes"][0]["value"]["candidate"] == 2,
        "constitution": len(fingerprint) == 64 and
                        candidate["rollback"]["reversible"] is True,
        "shadow": shadow["external_writes"] == [] and
                  shadow["mutation_allowed"] is False,
        "fitness": fitness["fitness"]["claim"] == "inconclusive" and
                   fitness["promotion"]["ready"] is False and
                   fitness["external_writes"] == [],
        "insufficient": shadow["status"] == "insufficient_evidence",
        "rejected": shadow["mutation_allowed"] is False,
        "stable": load_policy(root=ROOT)["review_round_limit"] == 3,
        "authority": fitness["mutation_allowed"] is False,
    }


def assess(data: object, proof: object) -> dict[str, str]:
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if (type(data) is not dict
            or set(data) != {MATRIX, MESH, RUNNER, MANIFEST, BASELINE}
            or not document_contract(data) or not manifest_contract(data.get(MANIFEST))
            or type(data.get(BASELINE)) is not str or not data[BASELINE]
            or type(proof) is not dict or set(proof) != set(PROOF_FOR.values())
            or any(type(value) is not bool for value in proof.values())):
        return result
    return {key: (LOCAL if key in PROOF_FOR and proof[PROOF_FOR[key]]
                  else UNKNOWN) for key in CLAUSES}


class BrechasFactory21Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: all 16 exact rows earn local evidence or explicit UNKNOWN."""
        data, proof = sources(), replay()
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(len(set(CLAUSES)), 16)
        self.assertEqual(set(matrix_rows(data[MATRIX])), set(CLAUSES))
        self.assertTrue(document_contract(data))
        self.assertTrue(manifest_contract(data[MANIFEST]))
        self.assertTrue(all(proof.values()), proof)
        for key, outcome in assess(data, proof).items():
            with self.subTest(clause=key):
                self.assertEqual(outcome, UNKNOWN if key in EXTERNAL else LOCAL)
                self.assertNotEqual(outcome, "CUBIERTO")

    def test_falla_cerrado(self) -> None:
        """AC-02: missing/duplicated/promoted evidence cannot claim success."""
        data, proof = sources(), replay()
        for key in CLAUSES:
            prefix = f"| {TICK}{key}{TICK} |"
            line = next(x for x in data[MATRIX].splitlines() if x.startswith(prefix))
            for bad in (
                data[MATRIX].replace(line, "", 1),
                data[MATRIX] + "\n" + line,
                data[MATRIX].replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(clause=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(bad)
                    self.assertEqual(set(assess({**data, MATRIX: bad}, proof).values()),
                                     {UNKNOWN})
        for key, name in PROOF_FOR.items():
            self.assertEqual(assess(data, {**proof, name: False})[key], UNKNOWN)
        for fake in (None, {}, {"status": "success"}, {**proof, "extra": True}):
            self.assertEqual(set(assess(data, fake).values()), {UNKNOWN})
        for filename in (MESH, RUNNER, MANIFEST, BASELINE):
            self.assertEqual(set(assess({**data, filename: ""}, proof).values()),
                             {UNKNOWN})
        forged = json.loads(data[MANIFEST])
        next(x for x in forged["evidence"]
             if x["repo"] == "pl0n3r/GrindFlow")["state"] = "merged"
        self.assertFalse(manifest_contract(json.dumps(forged)))
        with self.assertRaises(ConstitutionError):
            validate_candidate({
                "version": 1,
                "changes": [{"path": "decisiones.review_round_limit",
                             "operation": "replace", "value": 2}],
                "evidence": ["synthetic:local"],
                "rollback": {"reversible": True, "strategy": "restore_baseline"},
            })

    def test_sin_datos_reales(self) -> None:
        """AC-03: no network/process APIs or live tenants."""
        tree = ast.parse(read("tests/test_brechas_factory_21.py"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imported & {
            "socket", "urllib", "requests", "httpx", "subprocess",
            "playwright", "selenium", "pymysql", "mysql",
        })
        rows = [json.loads(x) for x in read(BASELINE).splitlines() if x.strip()]
        self.assertGreater(len(rows), 1)
        self.assertTrue(all(row["review_state"] in
                            {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}
                            for row in rows))
        self.assertNotIn("password", read(MANIFEST).lower())

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04: external PR, CI and macOS handoff are unverified."""
        data, proof = sources(), replay()
        result = assess(data, proof)
        self.assertEqual(len(EXTERNAL), 6)
        for key in EXTERNAL:
            self.assertEqual(result[key], UNKNOWN)
        self.assertEqual(load_policy(root=ROOT)["review_round_limit"], 3)
        for invented in (
            {"status": "success"}, {"production": "GREEN"},
            {"handoff": "verified", "macos": True},
            {"review": "APPROVED", "head_sha": "f" * 40},
        ):
            self.assertEqual(set(assess(data, invented).values()), {UNKNOWN})
        self.assertEqual(set(result.values()), {LOCAL, UNKNOWN})


if __name__ == "__main__":
    unittest.main()
