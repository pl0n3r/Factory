"""#1807: pruebas de comportamiento reales de Factory Queue, sin servicios externos.

FactoryRunner/ControlBot hosting, adapters and MariaDB are B/C external,
not proof of production within this offline test.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import socket
import subprocess
import unittest
from unittest import mock
import urllib.request

from producto.feedback import (
    FeedbackValidationError, execution_feedback_identity,
    validate_execution_feedback,
)
from scripts.dispatcher_v2 import (
    WorkItemReadinessContext, candidate_from_work_item, select_next,
)
from scripts.work_origin import (
    WorkOriginError, idempotency_scope, validate_work_item, work_fingerprint,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _item(*, origin="factory", work_id="work-synthetic-1",
          producer="factory:synthetic"):
    return {
        "work_id": work_id, "origin_mode": "automatic",
        "origin_system": origin, "group_id": "synthetic-group",
        "venture_id": "synthetic-venture", "project_id": "synthetic-project",
        "work_type": "infrastructure",
        "requested_capabilities": ["python"], "required_roles": ["qa"],
        "authority_level": "medium", "producer_ref": producer,
        "priority_class": "medium", "depends_on": [],
        "claims": ["tests/synthetic-queue"], "policy_ref": "synthetic:policy",
        "evidence_refs": ["synthetic:work"],
        "observed_at": "2026-10-29T11:00:00Z",
        "idempotency_key": "synthetic-idempotency",
    }


def _feedback(item):
    return {
        "work_id": item["work_id"],
        "work_fingerprint": work_fingerprint(item),
        "idempotency_scope": idempotency_scope(item),
        "executor_ref": "runner:synthetic",
        "producer_ref": item["producer_ref"],
        "status": "success",
        "evidence_refs": ["synthetic:terminal", "synthetic:check"],
        "observed_at": "2026-10-29T11:55:00+00:00",
    }


def _ready(**overrides):
    flags = dict(authority_valid=True, policy_valid=True,
                 freshness_valid=True, evidence_valid=True)
    flags.update(overrides)
    return WorkItemReadinessContext(**flags)


class CoberturaFactory16Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: las 15 filas Factory Queue ejercen contratos locales reales."""
        item = _item()
        original = deepcopy(item)
        normalized = validate_work_item(item)
        scope = idempotency_scope(item)
        fingerprint = work_fingerprint(item)

        # L41-U1: las cinco dimensiones forman el scope; ni origin ni work_id.
        expected_scope = {
            "group_id": item["group_id"], "venture_id": item["venture_id"],
            "project_id": item["project_id"], "work_type": item["work_type"],
            "idempotency_key": item["idempotency_key"],
        }
        expected = hashlib.sha256(json.dumps(
            expected_scope, ensure_ascii=False, separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(expected, scope)
        for field in expected_scope:
            changed = deepcopy(item)
            changed[field] = (
                "engineering" if field == "work_type" else "synthetic-other"
            )
            with self.subTest(scope_dimension=field):
                self.assertNotEqual(scope, idempotency_scope(changed))

        other = _item(origin="controlbot", work_id="work-synthetic-2",
                      producer="controlbot:synthetic")
        self.assertEqual(scope, idempotency_scope(other))
        self.assertNotEqual(fingerprint, work_fingerprint(other))
        self.assertEqual(normalized["work_id"], item["work_id"])
        self.assertEqual(item, original)

        # L76-U1/L80-U1/L84-U1/L88-U1: readiness y Dispatcher V2,
        # dos orígenes equivalentes, una sola unidad ejecutable.
        first = candidate_from_work_item(item, _ready())
        duplicate = candidate_from_work_item(
            other, _ready(active_idempotency_scopes=frozenset({scope})))
        chosen = select_next([first, duplicate])
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.key, item["work_id"])
        self.assertEqual(chosen.metadata["work_fingerprint"], fingerprint)
        self.assertEqual(chosen.metadata["idempotency_scope"], scope)
        self.assertIsNone(select_next([duplicate]))

        # L55-U1/L63..L70-U1/L76-U2: feedback terminal atribuible a WorkItem.
        raw = _feedback(item)
        result = validate_execution_feedback(raw, item, now=NOW)
        self.assertEqual(result["work_id"], chosen.key)                 # L63
        self.assertEqual(result["work_fingerprint"], fingerprint)       # L64
        self.assertEqual(result["idempotency_scope"], scope)            # L65
        self.assertEqual(result["executor_ref"], "runner:synthetic")   # L66
        self.assertEqual(result["producer_ref"], item["producer_ref"]) # L67
        self.assertEqual(result["evidence_refs"],
                         ["synthetic:check", "synthetic:terminal"])     # L69
        self.assertEqual(result["observed_at"],
                         "2026-10-29T11:55:00+00:00")                   # L70
        self.assertEqual(result["status"], "success")
        self.assertEqual(set(result), {
            "work_id", "work_fingerprint", "idempotency_scope",
            "executor_ref", "producer_ref", "status", "evidence_refs",
            "observed_at",
        })
        self.assertNotIn("authority_level", result)
        self.assertNotIn("priority_class", result)
        reverse = deepcopy(raw)
        reverse["evidence_refs"].reverse()
        self.assertEqual(execution_feedback_identity(raw, item, now=NOW),
                         execution_feedback_identity(reverse, item, now=NOW))
        self.assertEqual("medium", chosen.priority)
        for terminal in ("success", "failed", "rejected", "cancelled"):
            with self.subTest(terminal=terminal):
                self.assertEqual(terminal, validate_execution_feedback(
                    {**raw, "status": terminal}, item, now=NOW)["status"])

    def test_falla_cerrado(self):
        """AC-02: identidad, autoridad, pruebas y freshness fallan cerrado."""
        item = _item()
        for broken in (
            {k: v for k, v in item.items() if k != "producer_ref"},
            {**item, "requested_by": "different:producer"},
            {**item, "api_token": "synthetic-placeholder"},
            {**item, "work_type": "unsupported"},
        ):
            with self.subTest(work_item=broken), self.assertRaises(WorkOriginError):
                validate_work_item(broken)
        for field in ("authority_valid", "policy_valid",
                      "freshness_valid", "evidence_valid"):
            with self.subTest(readiness=field):
                denied = candidate_from_work_item(item, _ready(**{field: False}))
                self.assertIsNone(select_next([denied]))
        suppressed = candidate_from_work_item(
            item, _ready(active_idempotency_scopes=frozenset({
                idempotency_scope(item)
            })))
        self.assertIsNone(select_next([suppressed]))

        original = _feedback(item)
        invalid = []
        for key, value in (
            ("work_id", "wrong-work"),
            ("work_fingerprint", "0" * 64),
            ("idempotency_scope", "0" * 64),
            ("executor_ref", ""),
            ("producer_ref", "other:producer"),
            ("status", "running"),
            ("evidence_refs", []),
            ("evidence_refs", ["synthetic:check", "synthetic:check"]),
            ("observed_at", "2026-10-29T11:55:00"),
            ("observed_at", (NOW - timedelta(hours=25)).isoformat()),
            ("observed_at", (NOW + timedelta(minutes=6)).isoformat()),
        ):
            invalid.append({**original, key: value})
        invalid.extend((
            {k: v for k, v in original.items() if k != "work_id"},
            {**original, "authority_level": "critical"},
        ))
        for payload in invalid:
            with self.subTest(feedback=payload), self.assertRaises(
                FeedbackValidationError
            ):
                validate_execution_feedback(payload, item, now=NOW)
        with self.assertRaises(FeedbackValidationError):
            validate_execution_feedback(
                original, item, now=NOW.replace(tzinfo=None))

    def test_sin_datos_reales(self):
        """AC-03: inputs sintéticos sin red, subprocesos ni datos reales."""
        item = _item()
        before = deepcopy(item)
        with (mock.patch.object(socket, "create_connection",
                                side_effect=AssertionError("no network")),
              mock.patch.object(urllib.request, "urlopen",
                                side_effect=AssertionError("no network")),
              mock.patch.object(subprocess, "run",
                                side_effect=AssertionError("no subprocess"))):
            validated = validate_work_item(item)
            outcome = validate_execution_feedback(_feedback(item), item, now=NOW)
            selected = select_next([
                candidate_from_work_item(item, _ready())
            ])
        self.assertEqual(item, before)
        self.assertEqual(validated["group_id"], "synthetic-group")
        self.assertEqual(outcome["executor_ref"], "runner:synthetic")
        self.assertEqual(selected.key, item["work_id"])
        self.assertTrue(all(ref.startswith("synthetic:")
                            for ref in item["evidence_refs"] +
                            outcome["evidence_refs"]))


if __name__ == "__main__":
    unittest.main()
