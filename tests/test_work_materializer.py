import copy
import json
import unittest
from scripts.work_inventory import project_inventory
from scripts.work_materializer import (
    WorkMaterializerError,
    materialization_fingerprint,
    materialize_leaf,
    validate_materialization_candidate,
)
COMPLETED = {"Factory#706"}


def acceptance_body() -> str:
    marker = json.dumps(
        {
            "version": 1,
            "criteria": [
                {
                    "id": "AC-01",
                    "kind": "test",
                    "target": (
                        "tests/test_work_materializer.py::WorkMaterializerTests::"
                        "test_leaf_requires_complete_executable_contract"
                    ),
                }
            ],
        },
        separators=(",", ":"),
    )
    return f"""### Contexto
Trabajo narrativo detectado por inventario.

### Alcance
Materializar un leaf puro y verificable.

### Fuera de alcance
No publicar en GitHub.

### Criterios de aceptación
- [ ] [AC-01] El contrato ejecutable es válido.

### Contrato ejecutable
<!-- factory-acceptance {marker} -->
"""


def candidate(*, kind: str = "executable", state: str = "available") -> dict:
    return {
        "identity": "roadmap:factory:materializer",
        "repository_ref": "pl0n3r/Factory",
        "leaf_key": "Factory#707",
        "title": "Materializar trabajo narrativo",
        "objective": "Convertir trabajo ejecutable oculto en un leaf canónico.",
        "scope": "Validación pura, fingerprint e idempotencia sin IO.",
        "acceptance_body": acceptance_body(),
        "depends_on": ["Factory#706"],
        "priority": "critical",
        "roles": ["qa", "arquitectura", "ingenieria-software", "producto"],
        "state": state,
        "kind": kind,
        "source_ref": "roadmap:Factory#701",
        "parent_ref": "Factory#701",
    }


class WorkMaterializerTests(unittest.TestCase):
    def test_leaf_requires_complete_executable_contract(self):
        valid = candidate()
        normalized = validate_materialization_candidate(valid)
        self.assertEqual(normalized["kind"], "executable")
        self.assertEqual(normalized["state"], "available")
        self.assertEqual(len(normalized["acceptance_sha256"]), 64)
        blocked_by_dependency = materialize_leaf(valid)
        self.assertFalse(blocked_by_dependency["materialized"])
        self.assertEqual(blocked_by_dependency["reason"], "open_dependencies")
        decision = materialize_leaf(valid, completed_dependencies=COMPLETED)
        self.assertTrue(decision["materialized"])
        self.assertEqual(decision["leaf"]["key"], "Factory#707")
        self.assertEqual(decision["leaf"]["source_identity"], valid["identity"])
        missing_scope = copy.deepcopy(valid)
        del missing_scope["scope"]
        with self.assertRaises(WorkMaterializerError):
            validate_materialization_candidate(missing_scope)
        invalid_acceptance = copy.deepcopy(valid)
        invalid_acceptance["acceptance_body"] = "sin contrato ejecutable"
        with self.assertRaises(WorkMaterializerError):
            validate_materialization_candidate(invalid_acceptance)
        mismatched_repository = copy.deepcopy(valid)
        mismatched_repository["leaf_key"] = "AutoFactory#707"
        with self.assertRaises(WorkMaterializerError):
            validate_materialization_candidate(mismatched_repository)
        for field, value in (("priority", "urgent"), ("state", "reserved"), ("kind", "unknown")):
            invalid = copy.deepcopy(valid); invalid[field] = value
            with self.assertRaises(WorkMaterializerError):
                validate_materialization_candidate(invalid)

    def test_materialization_is_idempotent(self):
        first = candidate()
        reordered = copy.deepcopy(first)
        reordered["roles"] = list(reversed(reordered["roles"]))
        reordered["depends_on"] = list(reversed(reordered["depends_on"]))
        self.assertEqual(
            materialization_fingerprint(first),
            materialization_fingerprint(reordered),
        )
        materialized = materialize_leaf(first, completed_dependencies=COMPLETED)
        self.assertTrue(materialized["materialized"])
        retry = materialize_leaf(
            first,
            existing_leaves=[materialized["leaf"]],
            completed_dependencies=COMPLETED,
        )
        self.assertFalse(retry["materialized"])
        self.assertEqual(retry["reason"], "already_materialized")
        self.assertEqual(retry["fingerprint"], materialized["fingerprint"])
        same_identity_other_key = candidate()
        same_identity_other_key["leaf_key"] = "Factory#999"
        duplicate_identity = materialize_leaf(
            same_identity_other_key,
            existing_leaves=[materialized["leaf"]],
            completed_dependencies=COMPLETED,
        )
        self.assertFalse(duplicate_identity["materialized"])
        self.assertEqual(duplicate_identity["reason"], "already_materialized")
        with self.assertRaises(WorkMaterializerError):
            materialize_leaf(
                first,
                existing_leaves=[{"key": None}],
                completed_dependencies=COMPLETED,
            )

    def test_future_decision_and_live_gated_work_stays_fail_closed(self):
        for kind in ("future_idea", "decision_required", "live_only"):
            with self.subTest(kind=kind):
                result = materialize_leaf(candidate(kind=kind, state="available"))
                self.assertFalse(result["materialized"])
                self.assertEqual(result["reason"], f"gated:{kind}")
                self.assertIsNone(result["leaf"])

    def test_e2e_hidden_roadmap_work_becomes_valid_ready_leaf(self):
        payload = candidate()
        snapshot = {
            "repository_ref": "pl0n3r/Factory",
            "leaves": [],
            "narrative": [
                {
                    "identity": payload["identity"],
                    "title": payload["title"],
                    "kind": "executable",
                    "source_ref": payload["source_ref"],
                    "expected_leaf_key": payload["leaf_key"],
                }
            ],
        }
        before = project_inventory(snapshot)
        self.assertEqual(before["state"], "UNMATERIALIZED_WORK")
        self.assertEqual(before["counts"]["unmaterialized"], 1)
        result = materialize_leaf(payload, completed_dependencies=COMPLETED)
        self.assertTrue(result["materialized"])
        snapshot["leaves"].append(result["leaf"])
        after = project_inventory(snapshot)
        self.assertEqual(after["state"], "READY")
        self.assertEqual(after["next_work"], "Factory#707")
        self.assertEqual(after["counts"]["unmaterialized"], 0)
        self.assertEqual(after["counts"]["already_materialized"], 1)


if __name__ == "__main__":
    unittest.main()
