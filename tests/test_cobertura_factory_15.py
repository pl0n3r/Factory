"""Factory #1806: pruebas conductuales con datos sintéticos y sin red.

No inspecciona ni exige el estado de docs/matriz-cobertura*.md.
Las filas de política y operativa externa se clasifican en el Issue y PR.
"""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution.constitution import ConstitutionError, validate_candidate
from evolution.experience_guardrails import (
    ExperienceGuardrailError, compile_guardrail_candidates,
)
from lab.factory_lab import FactoryLabError, evaluate_shadow, promotion_contract
from scripts.f2_caller_preflight import CONSUMERS, audit, main as f2_main
from scripts.work_origin import (
    WorkOriginError, canonical_payload, validate_work_item, work_fingerprint,
)


def lesson(number, source=None):
    return {
        "id": f"synthetic-{number:03d}", "project": "pl0n3r/factory",
        "kind": "process", "occurred_at": "2026-09-20T12:00:00Z",
        "what": "Synthetic duplicated CI drift", "why": "Synthetic repeated drift",
        "prevention": "Revert the proposed change",
        "source": f"pl0n3r/factory#{source if source is not None else 200 + number}",
    }


def work(**values):
    base = {
        "work_id": "synthetic-001", "origin_mode": "directed",
        "origin_system": "human", "group_id": "synthetic-group",
        "work_type": "engineering", "requested_capabilities": ["coding", "review"],
        "required_roles": ["qa", "ingenieria-software"],
        "authority_level": "operational", "producer_ref": "fixture:synthetic",
        "priority_class": "medium", "depends_on": [], "claims": [],
        "policy_ref": "fixture:policy", "evidence_refs": ["fixture:evidence"],
        "idempotency_key": "synthetic-key",
    }
    base.update(values)
    return base


def fitness(reliability):
    return {
        **{name: {"value": 1.0, "direction": "higher"} for name in (
            "security", "privacy", "traceability", "reversibility", "authority")},
        "reliability": {"value": reliability, "direction": "higher"},
    }


def candidate():
    return {
        "version": 1,
        "changes": [{"path": "evolution_state.heuristics.synthetic",
                     "operation": "add", "value": {"status": "candidate"}}],
        "evidence": ["pl0n3r/factory#1806"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


class CoberturaFactory15Tests(unittest.TestCase):
    """AC-01..03: tests de código real, sin validación textual de matriz."""

    def test_contrato_principal(self):
        # experience L5/L49/L50/L53/L54: evidencia sin mutación,
        # rollback constitucional, sólo candidato, no autoridad stable.
        originals = [lesson(1), lesson(2)]
        preserved = copy.deepcopy(originals)
        compiled = compile_guardrail_candidates(originals)
        self.assertEqual(originals, preserved)
        self.assertEqual(len(compiled), 1)
        record = compiled[0]
        change = record["candidate"]["changes"][0]
        self.assertEqual(record["candidate"]["rollback"],
                         {"reversible": True, "strategy": "revert"})
        self.assertEqual(validate_candidate(record["candidate"]),
                         record["candidate_fingerprint"])
        self.assertTrue(change["path"].startswith("evolution_state.heuristics."))
        self.assertEqual(change["value"]["status"], "candidate")
        self.assertEqual(change["value"]["lifecycle"]["state"], "candidate")
        self.assertEqual(len(change["value"]["origins"]), 2)
        self.assertNotIn("stable_authority", record["candidate"])
        self.assertEqual(compiled,
                         compile_guardrail_candidates(list(reversed(originals))))

        # F2 L3/L11: seis checkouts sintéticos, SAFE sólo observa esos
        # consumidores y nunca autoriza borrado o movimiento Factory@v1.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in CONSUMERS:
                (root / name / ".github" / "workflows").mkdir(parents=True)
            other = root / "unobserved-fork" / ".github" / "workflows"
            other.mkdir(parents=True)
            (other / "reader.yml").write_text(
                "jobs:\n  x:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n",
                encoding="utf-8")
            safe = audit(root, ["readme.yml"])
            self.assertEqual(safe["status"], "SAFE")
            self.assertEqual(safe["scanned_consumers"], list(CONSUMERS))
            self.assertEqual(safe["references"], [])
            self.assertIn("no autoriza", safe["scope"])
            self.assertTrue((other / "reader.yml").exists())
            with patch("sys.argv", ["preflight", "--root", str(root),
                                    "--target", "readme.yml"]), (
                    redirect_stdout(StringIO()) as output):
                self.assertEqual(f2_main(), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "SAFE")

        # factory-lab B06: Fitness improved produce evaluación read-only,
        # no despliegue, incluso cuando la promoción queda ready.
        stable, improved, draft = fitness(0.80), fitness(0.92), record["candidate"]
        shadow = evaluate_shadow(
            stable_sha="a" * 40, candidate_sha="b" * 40,
            stable_metrics=stable, candidate_metrics=improved,
            constitution_candidate=draft)
        self.assertEqual(shadow["fitness"]["claim"], "improved")
        self.assertTrue(shadow["promotion"]["ready"])
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        contract = promotion_contract(
            shadow_result=shadow, stable_sha="a" * 40,
            candidate_sha="b" * 40, stable_metrics=stable,
            candidate_metrics=improved, constitution_candidate=draft)
        self.assertTrue(contract["requires_human_or_authorized_promotion"])
        self.assertEqual(contract["execution"], "not-performed")

        # factory-queue L35/L39/L40: validador, JSON y SHA del WorkItem real.
        first = work(requested_capabilities=["review", "coding", "review"])
        second = copy.deepcopy(first)
        second["requested_capabilities"] = ["coding", "review"]
        self.assertEqual(validate_work_item(first)["requested_capabilities"],
                         ["coding", "review"])
        self.assertEqual(canonical_payload(first), canonical_payload(second))
        self.assertEqual(work_fingerprint(first), work_fingerprint(second))
        self.assertEqual(work_fingerprint(first), hashlib.sha256(
            canonical_payload(first).encode("utf-8")).hexdigest())
        self.assertNotEqual(work_fingerprint(first), work_fingerprint(
            work(priority_class="high")))
        self.assertEqual(json.loads(canonical_payload(first))["work_id"],
                         "synthetic-001")

    def test_falla_cerrado(self):
        # Experience: evidencia de fuente única/duplicada o cambio
        # constitucional prohibido nunca promocionan reglas.
        self.assertEqual(compile_guardrail_candidates([lesson(1)]), [])
        self.assertEqual(compile_guardrail_candidates([
            lesson(1, 201), lesson(2, 201)]), [])
        with self.assertRaises(ExperienceGuardrailError):
            compile_guardrail_candidates([lesson(1), lesson(1)])
        with self.assertRaises(ExperienceGuardrailError):
            compile_guardrail_candidates([lesson(1), lesson(2)],
                                         min_occurrences=1)
        forbidden = candidate()
        forbidden["changes"][0]["path"] = "stable_authority.grants"
        with self.assertRaises(ConstitutionError):
            validate_candidate(forbidden)

        # F2: no desplazar callers de ramas ajenas para obtener SAFE.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in CONSUMERS:
                (root / name / ".github" / "workflows").mkdir(parents=True)
            caller = root / "Condor" / ".github" / "workflows" / "caller.yml"
            contents = (
                "jobs:\n  x:\n"
                "    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n"
            )
            caller.write_text(contents, encoding="utf-8")
            blocked = audit(root, ["readme.yml"])
            self.assertEqual(blocked["status"], "BLOCKED")
            self.assertEqual(blocked["references"][0]["consumer"], "Condor")
            self.assertEqual(caller.read_text(encoding="utf-8"), contents)
            with patch("sys.argv", ["preflight", "--root", str(root),
                                    "--target", "readme.yml"]), (
                    redirect_stdout(StringIO()) as output):
                self.assertEqual(f2_main(), 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
            with self.assertRaises(ValueError):
                audit(root, ["../invalid.yml"])
            (root / "ControlBot" / ".github" / "workflows").rmdir()
            self.assertIn("ControlBot", audit(root, ["readme.yml"])["missing_consumers"])

        # Factory Queue: campos extra, desbordamiento, referencias
        # inválidas y solicitudes de permisos ausentes fallan cerrado.
        for invalid in [
            work(provider="unauthorized"),
            work(claims=[f"claim-{i}" for i in range(51)]),
            work(work_id="?invalid" * 40),
            work(policy_ref="x" * 241),
            work(unknown="forbidden"),
        ]:
            with self.subTest(keys=list(invalid)):
                with self.assertRaises(WorkOriginError):
                    validate_work_item(invalid)
        with self.assertRaises(FactoryLabError):
            evaluate_shadow(stable_sha="a" * 40, candidate_sha="a" * 40,
                            stable_metrics=fitness(0.8),
                            candidate_metrics=fitness(0.9),
                            constitution_candidate=candidate())

    def test_sin_datos_reales(self):
        # Datos artificiales; ningún repositorio, token o cliente real.
        item = work()
        self.assertEqual(validate_work_item(item)["producer_ref"],
                         "fixture:synthetic")
        self.assertNotIn("password", canonical_payload(item))
        with self.assertRaises(WorkOriginError):
            validate_work_item(work(password="placeholder"))
        with self.assertRaises(WorkOriginError):
            validate_work_item(work(policy_ref="Bearer " + "x" * 24))
        self.assertEqual(compile_guardrail_candidates([
            lesson(5), lesson(6)])[0]["candidate"]["changes"][0]
            ["value"]["status"], "candidate")


if __name__ == "__main__":
    unittest.main()
