#!/usr/bin/env python3
"""Factory #1638: cobertura sintética y fail-closed de 16 cláusulas.

Las pruebas offline no verifican ejecución remota, hosting ni MariaDB.
Un resultado LOCAL_CONTRACT nunca equivale a CI, deploy, live o producción.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from producto.feedback import (
    FeedbackValidationError,
    execution_feedback_identity,
    validate_execution_feedback,
)
from scripts.dispatcher_v2 import (
    WorkItemReadinessContext,
    candidate_from_work_item,
    select_next,
)
from scripts.work_origin import (
    WorkOriginError,
    idempotency_scope,
    validate_work_item,
    work_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
QUEUE = "docs/factory-queue.md"
RUNNER = "docs/factoryrunner-execution-plane.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
NOW = datetime(2026, 9, 27, 23, 0, tzinfo=timezone.utc)

CLAUSES = {
    "docs/factory-queue.md:L65-U1": "idempotency_scope",
    "docs/factory-queue.md:L66-U1": "executor_ref",
    "docs/factory-queue.md:L67-U1": "producer_ref",
    "docs/factory-queue.md:L69-U1": "evidence_refs",
    "docs/factory-queue.md:L70-U1": "observed_at",
    "docs/factory-queue.md:L72-U1": "validación falla cerrada",
    "docs/factory-queue.md:L76-U1": "WorkItem válido",
    "docs/factory-queue.md:L76-U2": "work_fingerprint",
    "docs/factory-queue.md:L80-U1": "extremo a extremo",
    "docs/factory-queue.md:L84-U1": "idempotency_scope",
    "docs/factory-queue.md:L88-U1": "composición coherente",
    "docs/factoryrunner-execution-plane.md:B01": "Factory gobierna",
    "docs/factoryrunner-execution-plane.md:B02": "hosting compartido",
    "docs/factoryrunner-execution-plane.md:B03": "secret-free",
    "docs/factoryrunner-execution-plane.md:B04": "fencing",
    "docs/factoryrunner-execution-plane.md:B05": "estado durable",
}
RUNNER_GAPS = {
    "docs/factoryrunner-execution-plane.md:B01": "external_authority_not_observed",
    "docs/factoryrunner-execution-plane.md:B02": "shared_hosting_runtime_smoke_missing",
    "docs/factoryrunner-execution-plane.md:B03": "all_remote_adapters_not_verified",
    "docs/factoryrunner-execution-plane.md:B04": "remote_side_effect_fencing_not_observed",
    "docs/factoryrunner-execution-plane.md:B05": "mariadb_atomic_ownership_not_observed",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw: object) -> dict[str, str]:
    """Exige las 16 filas originales, únicas y sin promoción ficticia."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matriz ausente o ilegible")
    found: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.startswith("| `"):
            continue
        for clause, expected in CLAUSES.items():
            prefix = f"| `{clause}` |"
            if not line.startswith(prefix):
                continue
            # La propia descripción podría contener barras; delimitamos por
            # el estado de matriz y preservamos texto de la cláusula.
            left, separator, right = line.partition(" | NO_VERIFICABLE | ")
            evidence, source_separator, source = right.rpartition(" | ")
            if (not separator or not right.strip().endswith("|")
                    or not source_separator or not evidence.strip()
                    or not source.strip(" |")):
                raise ValueError(f"UNKNOWN: fila sin evidencia o fuente: {clause}")
            description = left[len(prefix):].strip()
            if (clause in found or not description
                    or expected.casefold() not in description.casefold()):
                raise ValueError(f"UNKNOWN: fila incompleta o duplicada: {clause}")
            found[clause] = description
            break
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: faltan filas o cambió su estado")
    return found


def assess(raw: object, checks: object) -> dict[str, str]:
    """No eleva evidencia parcial, ambigua ni comprobación operativa externa."""
    try:
        matrix_rows(raw)
    except ValueError:
        return dict.fromkeys(CLAUSES, UNKNOWN)
    if type(checks) is not dict or set(checks) != set(CLAUSES):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    if any(type(value) is not bool for value in checks.values()):
        return dict.fromkeys(CLAUSES, UNKNOWN)
    return {
        clause: (LOCAL if checks[clause] and clause not in RUNNER_GAPS
                 else UNKNOWN)
        for clause in CLAUSES
    }


def work_item(origin: str = "factory", work_id: str = "work-1638") -> dict:
    return {
        "work_id": work_id,
        "origin_mode": "automatic",
        "origin_system": origin,
        "group_id": "test-group",
        "project_id": "queue-synthetic",
        "repository_ref": "pl0n3r/Factory",
        "work_type": "infrastructure",
        "requested_capabilities": ["python"],
        "required_roles": ["qa"],
        "authority_level": "standard",
        "producer_ref": f"{origin}:fixture",
        "priority_class": "medium",
        "depends_on": [],
        "claims": ["tests/synthetic.py"],
        "policy_ref": "factory:synthetic",
        "evidence_refs": ["fixture:queue"],
        "observed_at": "2026-09-27T22:50:00Z",
        "idempotency_key": "same-logical-work-1638",
    }


def feedback(item: dict) -> dict:
    return {
        "work_id": item["work_id"],
        "work_fingerprint": work_fingerprint(item),
        "idempotency_scope": idempotency_scope(item),
        "executor_ref": "runner:fixture",
        "producer_ref": item["producer_ref"],
        "status": "success",
        "evidence_refs": ["check:fixture", "artifact:fixture"],
        "observed_at": "2026-09-27T22:58:00+00:00",
    }


def rejected(item: dict, changes: dict) -> bool:
    candidate = feedback(item)
    candidate.update(changes)
    try:
        validate_execution_feedback(candidate, item, now=NOW)
    except FeedbackValidationError:
        return True
    return False


def evidence() -> dict[str, bool]:
    """Cada resultado se deriva de un contrato real o de una brecha explícita."""
    item = work_item()
    same = work_item("controlbot", "work-other-origin-1638")
    context = WorkItemReadinessContext(
        authority_valid=True, policy_valid=True,
        freshness_valid=True, evidence_valid=True,
    )
    selected = select_next([candidate_from_work_item(item, context)])
    scope = idempotency_scope(item)
    duplicate = candidate_from_work_item(
        same, WorkItemReadinessContext(
            authority_valid=True, policy_valid=True,
            freshness_valid=True, evidence_valid=True,
            active_idempotency_scopes=frozenset({scope}),
        )
    )
    normalized = validate_execution_feedback(feedback(item), item, now=NOW)
    reversed_refs = feedback(item)
    reversed_refs["evidence_refs"] = list(reversed(reversed_refs["evidence_refs"]))
    queue_docs, runner_docs = read(QUEUE), read(RUNNER)

    # Una evidencia falsa o incompatible no es reemplazable por texto de docs.
    negative = {
        "wrong_work": rejected(item, {"work_id": "other"}),
        "wrong_scope": rejected(item, {"idempotency_scope": "0" * 64}),
        "wrong_fingerprint": rejected(item, {"work_fingerprint": "0" * 64}),
        "wrong_producer": rejected(item, {"producer_ref": "other:fixture"}),
        "no_executor": rejected(item, {"executor_ref": ""}),
        "no_evidence": rejected(item, {"evidence_refs": []}),
        "duplicate_evidence": rejected(
            item, {"evidence_refs": ["same:ref", "same:ref"]}),
        "nonterminal": rejected(item, {"status": "running"}),
        "stale": rejected(item, {
            "observed_at": (NOW - timedelta(hours=25)).isoformat()}),
        "no_timezone": rejected(item, {"observed_at": "2026-09-27T22:58:00"}),
        "future": rejected(item, {
            "observed_at": (NOW + timedelta(minutes=6)).isoformat()}),
        "extra_authority": rejected(item, {"authority_level": "critical"}),
    }
    no_double_dispatch = select_next([duplicate]) is None
    queue = "docs/factory-queue.md:"
    runner = "docs/factoryrunner-execution-plane.md:"
    return {
        queue + "L65-U1": (
            scope == normalized["idempotency_scope"]
            == idempotency_scope(same) and negative["wrong_scope"]),
        queue + "L66-U1": (
            normalized["executor_ref"] == "runner:fixture"
            and negative["no_executor"]),
        queue + "L67-U1": (
            normalized["producer_ref"] == item["producer_ref"]
            and negative["wrong_producer"]),
        queue + "L69-U1": (
            normalized["evidence_refs"] == ["artifact:fixture", "check:fixture"]
            and negative["no_evidence"] and negative["duplicate_evidence"]
            and execution_feedback_identity(feedback(item), item, now=NOW)
            == execution_feedback_identity(reversed_refs, item, now=NOW)),
        queue + "L70-U1": (
            normalized["observed_at"].endswith("+00:00")
            and all(negative[key] for key in ("stale", "no_timezone", "future"))),
        queue + "L72-U1": all(negative.values()),
        queue + "L76-U1": (
            selected is not None and selected.key == item["work_id"]
            and normalized["work_id"] == selected.key),
        queue + "L76-U2": (
            selected is not None
            and normalized["work_fingerprint"] == selected.metadata["work_fingerprint"]
            and normalized["idempotency_scope"] == selected.metadata["idempotency_scope"]
            and all(negative[k] for k in (
                "wrong_fingerprint", "wrong_scope", "stale"))),
        queue + "L80-U1": (
            selected is not None and normalized["status"] == "success"
            and "WorkItem → readiness → Dispatcher V2" in queue_docs),
        queue + "L84-U1": (
            scope == idempotency_scope(same) and no_double_dispatch),
        queue + "L88-U1": (
            no_double_dispatch and negative["extra_authority"]
            and "No añade una cola nueva" in queue_docs),
        runner + "B01": all(s in runner_docs for s in (
            "**Factory gobierna**", "**ControlBot decide**",
            "**FactoryRunner ejecuta**",
            "FactoryRunner no puede crear trabajo")),
        runner + "B02": all(s in runner_docs for s in (
            "Shared/Web Hosting", "sin presuponer:", "acceso root",
            "Docker", "procesos persistentes ilimitados")),
        runner + "B03": (
            "Las órdenes son **secret-free**" in runner_docs
            and "vault/secret store" in runner_docs
            and _work_rejects_secret()),
        runner + "B04": all(s in runner_docs for s in (
            "`attempt_id`", "`generation`", "`fencing_token`",
            "attempt stale")),
        runner + "B05": all(s in runner_docs for s in (
            "ControlBot/MariaDB es la fuente de verdad durable",
            "nunca permiten dos owners efectivos simultáneos",
            "estados terminales tienen precedencia durable")),
    }


def _work_rejects_secret() -> bool:
    invalid = work_item()
    invalid["password"] = "placeholder"
    try:
        validate_work_item(invalid)
    except WorkOriginError:
        return True
    return False


def operational_status(_clause: str, _claim: object = None) -> str:
    """Sin observación autenticada del runtime externo: siempre UNKNOWN."""
    return UNKNOWN


class BrechasFactory20Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read(MATRIX)
        clauses = matrix_rows(matrix)
        proof = evidence()
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(set(clauses), set(CLAUSES))
        self.assertEqual(set(proof), set(CLAUSES))
        for clause in CLAUSES:
            with self.subTest(clause=clause):
                self.assertTrue(proof[clause], f"{clause}: regresión offline")
                self.assertEqual(
                    assess(matrix, proof)[clause],
                    UNKNOWN if clause in RUNNER_GAPS else LOCAL,
                )

    def test_falla_cerrado(self):
        matrix = read(MATRIX)
        first = next(line for line in matrix.splitlines()
                     if line.startswith(f"| `{next(iter(CLAUSES))}` |"))
        proof = evidence()
        prefix, delimiter, right = first.partition(" | NO_VERIFICABLE | ")
        _evidence, final_delimiter, source = right.rpartition(" | ")
        self.assertTrue(delimiter and final_delimiter)
        missing_evidence = prefix + " | NO_VERIFICABLE |  | " + source
        for bad in (
            None, "", matrix.replace(first, "", 1),
            matrix + "\n" + first,
            matrix.replace(first, missing_evidence, 1),
            matrix.replace(first, first.replace(
                "NO_VERIFICABLE", "CUBIERTO", 1), 1),
        ):
            with self.subTest(bad=repr(bad)[:40]):
                self.assertEqual(set(assess(bad, proof).values()), {UNKNOWN})
        for bad in (
            None, {}, {next(iter(CLAUSES)): True},
            dict.fromkeys(CLAUSES, 1),
            {**proof, "unexpected": True},
        ):
            self.assertEqual(set(assess(matrix, bad).values()), {UNKNOWN})
        self.assertTrue(rejected(work_item(), {"status": "running"}))
        self.assertTrue(rejected(work_item(), {"evidence_refs": []}))

    def test_sin_datos_reales(self):
        data = str((work_item(), feedback(work_item()))).lower()
        for prohibited in (
            "authorization", "access_token", "secret_key", "private_key",
            "http://", "https://", "@gmail", "password"):
            self.assertNotIn(prohibited, data)
        tree = ast.parse(read("tests/test_brechas_factory_20.py"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(n.name.split(".")[0] for n in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & {
            "requests", "urllib", "socket", "subprocess", "httpx", "smtplib"})
        self.assertTrue(_work_rejects_secret())

    def test_estados_unknown_explicitos(self):
        matrix = read(MATRIX)
        proof = evidence()
        report = assess(matrix, proof)
        self.assertEqual(set(RUNNER_GAPS), {
            key for key, status in report.items() if status == UNKNOWN})
        for clause, reason in RUNNER_GAPS.items():
            with self.subTest(clause=clause):
                self.assertEqual(report[clause], UNKNOWN, reason)
                self.assertTrue(reason.endswith(("_observed", "_missing",
                                                 "_verified")))
        for clause in CLAUSES:
            with self.subTest(clause=clause):
                self.assertEqual(
                    assess(matrix, {**proof, clause: False})[clause], UNKNOWN)
                for claim in (None, True, "success",
                              {"ci": "success"}, {"live": True}):
                    self.assertEqual(operational_status(clause, claim), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
