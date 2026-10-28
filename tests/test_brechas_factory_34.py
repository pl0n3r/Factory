"""Factory #1652: 16 unidades de cobertura offline (Living, memoria y NO_WORK).

Fixturas sintéticas; la evidencia histórica no prueba disponibilidad en producción.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lecciones.memoria import (
    LessonValidationError, load_lessons, summarize, token_comparison, validate_lesson,
)
from scripts.no_work_dedup import (
    CANONICAL_SINK, REPOSITORIES, NoWorkInventoryError, NoWorkPublicationState,
    decide_no_work, inventory_fingerprint, revalidate_no_work_application,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
CHANGE = "2026-09-15T00:00:00Z"
UNITS = (
    "docs/living-software-operational-e2e.md:L66-U1",
    "docs/living-software-operational-e2e.md:L9-U1",
    "docs/memoria-institucional.md:L10-U1",
    "docs/memoria-institucional.md:L10-U2",
    "docs/memoria-institucional.md:L11-U1",
    "docs/memoria-institucional.md:L11-U2",
    "docs/memoria-institucional.md:L12-U1",
    "docs/memoria-institucional.md:L12-U2",
    "docs/memoria-institucional.md:L16-U1",
    "docs/memoria-institucional.md:L18-U1",
    "docs/memoria-institucional.md:L5-U1",
    "docs/memoria-institucional.md:L5-U2",
    "docs/memoria-institucional.md:L9-U1",
    "docs/no-work-dedup.md:B01",
    "docs/no-work-dedup.md:B02",
    "docs/no-work-dedup.md:B03",
)
EVIDENCE_GAPS = {
    "docs/memoria-institucional.md:L10-U2": (
        "UNKNOWN: el esquema no demuestra sanitización universal de PII/secretos"
    ),
    "docs/living-software-operational-e2e.md:L66-U1": (
        "UNKNOWN: un manifiesto histórico no verifica GitHub productivo en esta prueba"
    ),
}


def lesson(ident="factory-synthetic", project="pl0n3r/Factory", **updates):
    row = {
        "id": ident, "project": project, "kind": "rework",
        "occurred_at": "2026-09-13T00:00:00Z",
        "what": "Una validación de ejemplo falló.",
        "why": "Faltaba un contrato explícito en el fixture.",
        "prevention": "Comprobar el contrato antes de procesar.",
        "source": "pl0n3r/Factory#1652",
    }
    row.update(updates)
    return row


def inventory():
    repos = {
        name: {"available": [], "recovery": [], "reservations": [],
               "blockers": [], "pull_requests": []}
        for name in REPOSITORIES
    }
    repos["Factory"]["available"] = [1652]
    repos["ControlBot"]["reservations"] = [{
        "issue": 42, "reservation_id": "synthetic-lease",
        "owner": "pl0n3r", "branch": "trabajo/issue-42", "active": True,
    }]
    repos["Condor"]["blockers"] = [{"issue": 43, "reason": "requires-evidence"}]
    repos["GrindFlow"]["pull_requests"] = [
        {"number": 44, "state": "open", "head_sha": "a" * 40}
    ]
    return {"kill_switch": {"state": "RUNNING"}, "repositories": repos}


def metric_rows(after=True, cross_project=False):
    rows = []
    for number, stamp, tokens in (
        (100, "2026-09-01T00:00:00Z", 100),
        (101, "2026-09-02T00:00:00Z", 120),
        (102, "2026-09-16T00:00:00Z", 50),
        (103, "2026-09-17T00:00:00Z", 60),
    ):
        if after or number < 102:
            rows.append({
                "task_type": "agent-bootstrap",
                "task_id": f"pl0n3r/Factory#{number}",
                "tokens_input": tokens, "completed_at": stamp,
            })
    if cross_project:
        for number, stamp, tokens in (
            (200, "2026-09-01T00:00:00Z", 20),
            (201, "2026-09-02T00:00:00Z", 30),
            (202, "2026-09-16T00:00:00Z", 700),
            (203, "2026-09-17T00:00:00Z", 800),
        ):
            rows.append({
                "task_type": "agent-bootstrap",
                "task_id": f"pl0n3r/Condor#{number}",
                "tokens_input": tokens, "completed_at": stamp,
            })
    return rows


def measure(rows):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic.jsonl"
        path.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
        return token_comparison(path, CHANGE, "pl0n3r/Factory")


class BrechasFactory34Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """Mapeo exhaustivo ID → regresión o incertidumbre reconocida."""
        manifest = json.loads(
            (ROOT / "feedback/data/living-software-operational-e2e.json")
            .read_text(encoding="utf-8")
        )
        doc = (ROOT / "docs/living-software-operational-e2e.md").read_text(
            encoding="utf-8"
        )
        runs = {x["run_id"]: x for x in manifest["coordination_attempts"]}
        local = validate_lesson(lesson(), "synthetic")
        foreign = validate_lesson(
            lesson("condor-synthetic", "pl0n3r/Condor"), "synthetic"
        )
        context = summarize([local, foreign], "pl0n3r/Factory", max_chars=800)
        recent = validate_lesson(
            lesson("factory-oversized", occurred_at="2026-09-14T00:00:00Z",
                   what="x" * 260, why="y" * 260, prevention="z" * 260),
            "synthetic",
        )
        bounded = summarize([local, recent], "pl0n3r/Factory", max_chars=400)
        metric = measure(metric_rows(cross_project=True))
        incomplete = measure(metric_rows(after=False))
        snapshot = inventory()
        fingerprint = inventory_fingerprint(snapshot)
        created = decide_no_work(snapshot, None, now=2000)
        published = NoWorkPublicationState(904, fingerprint, 2000, observed_at=2000)
        omitted = decide_no_work(snapshot, published, now=2100)
        refreshed = decide_no_work(snapshot, published, now=3800)
        changed = inventory()
        changed["repositories"]["Factory"]["available"].append(1660)
        updated = decide_no_work(
            changed, published, now=2200, observed_at=2150
        )
        newer = NoWorkPublicationState(904, fingerprint, 2190, observed_at=2180)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lessons.jsonl"
            path.write_text(json.dumps(lesson()), encoding="utf-8")
            loaded = load_lessons([path])
        checks = {
            "docs/living-software-operational-e2e.md:L66-U1": (
                manifest["origin"]["unsolicited"] is True
                and manifest["shadow_candidate"]["mode"] == "shadow"
                and manifest["shadow_candidate"]["external_writes"] == []
                and manifest["posterior_execution"]["pr"] == 339
                and manifest["posterior_execution"]["exact_main"]["ci_conclusion"] == "success"
                and "adopción" in doc.lower()
            ),
            "docs/living-software-operational-e2e.md:L9-U1": (
                runs[36507015627]["conclusion"] == "failure"
                and runs[36507015627]["effect"] == "acceptance_contract_rejected"
                and "run:36507015627" in manifest["origin"]["provenance"]
            ),
            "docs/memoria-institucional.md:L10-U1": (
                local["why"] == "Faltaba un contrato explícito en el fixture."
                and local["prevention"].startswith("Comprobar")
                and local["source"] == "pl0n3r/Factory#1652"
            ),
            "docs/memoria-institucional.md:L10-U2": UNKNOWN,
            "docs/memoria-institucional.md:L11-U1": (
                "factory-synthetic" in context
                and "condor-synthetic" not in context
                and context.startswith("# Contexto rápido — pl0n3r/Factory")
            ),
            "docs/memoria-institucional.md:L11-U2": (
                "factory-synthetic" in bounded
                and "factory-oversized" not in bounded
                and len(bounded) <= 400
            ),
            "docs/memoria-institucional.md:L12-U1": (
                metric["task_type"] == "agent-bootstrap"
                and metric["change_at"] == "2026-09-15T00:00:00+00:00"
                and metric["status"] == "measured"
                and metric["before_samples"] == 2
                and metric["after_samples"] == 2
            ),
            "docs/memoria-institucional.md:L12-U2": (
                metric["project"] == "pl0n3r/Factory"
                and metric["before_avg_tokens"] == 110
                and metric["after_avg_tokens"] == 55
                and metric["reduction_pct"] == 50.0
            ),
            "docs/memoria-institucional.md:L16-U1": (
                len(loaded) == 1
                and "factory-synthetic" in summarize(loaded, "pl0n3r/Factory")
                and (ROOT / "decisiones.yml").is_file()
            ),
            "docs/memoria-institucional.md:L18-U1": (
                incomplete["status"] == "insufficient-data"
                and incomplete["after_samples"] == 0
                and incomplete["reduction_pct"] is None
            ),
            "docs/memoria-institucional.md:L5-U1": (
                "factory-synthetic" in context
                and "Fuente: pl0n3r/Factory#1652" in context
                and "condor-synthetic" not in context
            ),
            "docs/memoria-institucional.md:L5-U2": (
                metric["status"] == "measured"
                and incomplete["status"] == "insufficient-data"
            ),
            "docs/memoria-institucional.md:L9-U1": (
                local["kind"] == "rework"
                and local["source"] == "pl0n3r/Factory#1652"
            ),
            "docs/no-work-dedup.md:B01": (
                len(REPOSITORIES) == 7
                and len(fingerprint) == 64
                and fingerprint != inventory_fingerprint(changed)
            ),
            "docs/no-work-dedup.md:B02": (
                created.action == "create"
                and created.sink == CANONICAL_SINK
                and omitted.action == "omit"
                and refreshed.action == "update"
                and updated.action == "update" and updated.comment_id == 904
            ),
            "docs/no-work-dedup.md:B03": (
                revalidate_no_work_application(updated, published).action == "apply"
                and revalidate_no_work_application(updated, newer).action == "recompute"
                and revalidate_no_work_application(omitted, published).action == "omit"
            ),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(checks), set(UNITS))
        for unit in UNITS:
            with self.subTest(unit=unit):
                if checks[unit] == UNKNOWN:
                    self.assertIn(unit, EVIDENCE_GAPS)
                    self.assertTrue(EVIDENCE_GAPS[unit].startswith("UNKNOWN:"))
                else:
                    self.assertTrue(checks[unit], f"{unit}: sin evidencia offline")

    def test_falla_cerrado(self):
        """No publicar snapshots incompletos ni aceptar trazabilidad ambigua."""
        incomplete = inventory()
        del incomplete["repositories"]["FactoryRunner"]
        with self.assertRaises(NoWorkInventoryError):
            inventory_fingerprint(incomplete)
        paused = inventory()
        paused["kill_switch"]["state"] = "PAUSED"
        with self.assertRaises(NoWorkInventoryError):
            decide_no_work(paused, None, now=1)
        with self.assertRaises(LessonValidationError):
            validate_lesson(lesson(prevention=""), "synthetic")
        with self.assertRaises(LessonValidationError):
            validate_lesson(lesson(source="no-trace"), "synthetic")
        ambiguous = metric_rows()
        ambiguous[0]["task_id"] = "ambiguous#123"
        with self.assertRaises(LessonValidationError):
            measure(ambiguous)
        decision = decide_no_work(inventory(), None, now=2000)
        state = NoWorkPublicationState(904, decision.fingerprint, 2000)
        self.assertEqual(
            revalidate_no_work_application(decision, state).action, "recompute"
        )

    def test_sin_datos_reales(self):
        """Fixturas deterministas y temporales; no hay secretos ni I/O de red."""
        self.assertEqual(
            inventory_fingerprint(inventory()), inventory_fingerprint(inventory())
        )
        self.assertEqual(lesson(), lesson())
        self.assertTrue(all(
            x["task_id"].startswith("pl0n3r/Factory#") for x in metric_rows()
        ))
        with self.assertRaises(LessonValidationError):
            validate_lesson(lesson(email="test@example.invalid"), "synthetic")

    def test_estados_unknown_explicitos(self):
        """No inferir éxito de ausencia de métricas o evidencia externa."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = token_comparison(
                Path(tmp) / "absent.jsonl", CHANGE, "pl0n3r/Factory"
            )
        self.assertEqual(missing["status"], "insufficient-data")
        self.assertIsNone(missing["reduction_pct"])
        for gap in EVIDENCE_GAPS.values():
            self.assertTrue(gap.startswith("UNKNOWN:"))


if __name__ == "__main__":
    unittest.main()
