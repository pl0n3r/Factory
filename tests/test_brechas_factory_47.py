"""Factory #1665: 16 brechas offline; UNKNOWN no equivale a GREEN/live."""
from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import auditar_cola_vacia as cola
from scripts import no_work_dedup as cola_global
from scripts.deploy_kit import DeployError
from scripts.orquestador_kit import (
    claims_overlap, verified_changed_file_overlap,
    verified_new_file_claim_against_active_diff,
)
from scripts.preview_kit import PreviewError, run_preview

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
UNKNOWN = "UNKNOWN"
UNITS = (
    "docs/preview-preproduccion.md:L30-U1",
    "docs/preview-preproduccion.md:L31-U1",
    "docs/preview-preproduccion.md:L37-U1",
    "docs/preview-preproduccion.md:L37-U2",
    "docs/preview-preproduccion.md:L9-U1",
    "docs/principios-construccion.md:L11-U1",
    "docs/principios-construccion.md:L11-U2",
    "docs/principios-construccion.md:L11-U3",
    "docs/principios-construccion.md:L11-U4",
    "docs/principios-construccion.md:L11-U5",
    "docs/principios-construccion.md:L11-U6",
    "docs/principios-construccion.md:L15-U1",
    "docs/principios-construccion.md:L19-U1",
    "docs/principios-construccion.md:L19-U2",
    "docs/principios-construccion.md:L19-U3",
    "docs/principios-construccion.md:L23-U1",
)


def leaf(number, status, blocker=None):
    return {"number": number, "kind": "leaf", "status": status,
            "parent": None, "blocker": blocker}


def fixture(*issues):
    return {"version": 1, "source": "fixture", "complete": True,
            "issues": list(issues)}


def global_fixture():
    return {"kill_switch": {"state": "RUNNING"}, "repositories": {
        name: {"available": [], "recovery": [], "reservations": [],
               "blockers": [], "pull_requests": []}
        for name in cola_global.REPOSITORIES
    }}


def new_file_claim(**updates):
    args = dict(candidate_paths=["tests/candidate.py"], active_paths=["tests/"],
                active_files=["tests/other.py"], active_head=SHA,
                evidence_head=SHA, diff_complete=True, active_issue=123,
                active_lease="synthetic-v3")
    args.update(updates)
    return verified_new_file_claim_against_active_diff(**args)


def compared_diff(**updates):
    args = dict(left_claims=("tests/",), right_claims=("tests/",),
                left_files=["tests/first.py"], right_files=["tests/second.py"],
                left_head=SHA, right_head=SHA,
                left_evidence_head=SHA, right_evidence_head=SHA,
                left_complete=True, right_complete=True,
                other_issue=124, other_lease="synthetic-v3")
    args.update(updates)
    return verified_changed_file_overlap(**args)


def preview(*, fail=None):
    events = []

    def base(stage):
        events.append((stage, os.environ.get("FACTORY_PREVIEW"),
                       os.environ.get("FACTORY_SYNTHETIC_DATA")))
        return 7 if stage == fail else 0

    try:
        run_preview(version="1.2.3", sha=SHA, migration_mode="none",
                    runner=base, verification_runner=base)
    except DeployError:
        if fail is None:
            raise
    else:
        if fail is not None:
            raise AssertionError("preview fallido aceptado como success")
    return events


def matrix_rows():
    rows = {}
    for line in (ROOT / "docs/matriz-cobertura.md").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 4:
            key = cells[1].strip(chr(96) + " ")
            if key in UNITS:
                rows.setdefault(key, []).append(cells)
    return rows


class BrechasFactory47Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada unidad con aserción real o límite UNKNOWN explícito."""
        events = preview()
        stages = [event[0] for event in events]
        template = (ROOT / "template/.github/workflows/ci.yml").read_text()
        adapters = {name: (ROOT / "template/ops/factory" / name).read_text()
                    for name in ("build", "preview-smoke", "preview-e2e")}
        blocked = cola.audit(fixture(leaf(10, "bloqueado", "dependency")))
        planned = cola.audit(fixture(leaf(20, "planificado")))
        recovery = cola.audit(fixture(leaf(30, "requiere recuperación")))
        global_snapshot = cola_global.canonical_inventory(global_fixture())
        unknowable = {"status": UNKNOWN, "reason": "operational_evidence_absent"}
        findings = blocked["findings"]
        verified = compared_diff()
        assertions = {
            "docs/preview-preproduccion.md:L30-U1": (
                "preview-smoke" in stages
                and stages.index("preview-smoke") < stages.index("preview-e2e")
                and "php tests/smoke.php" in adapters["preview-smoke"]
                and "FACTORY_SYNTHETIC_DATA" in adapters["preview-smoke"]),
            "docs/preview-preproduccion.md:L31-U1": (
                stages[-1] == "preview-e2e"
                and "php public/index.php" in adapters["preview-e2e"]
                and "grep -Fq" in adapters["preview-e2e"]),
            "docs/preview-preproduccion.md:L37-U1": (
                "needs: [ci, preview]" in template and "name: Validar" in template
                and "RESULTADOS:" in template),
            "docs/preview-preproduccion.md:L37-U2": (
                "if: github.event_name == 'pull_request'" in template
                and "success|skipped" in template
                and unknowable["status"] == UNKNOWN),
            "docs/preview-preproduccion.md:L9-U1": (
                stages[0] == "build"
                and "php -l" in adapters["build"]
                and "FACTORY_PREVIEW" in adapters["build"]),
            "docs/principios-construccion.md:L11-U1": (
                blocked["state"] == "COLA_VACIA_CON_PENDIENTES"
                and blocked["action_required"] is True
                and len(global_snapshot["repositories"]) == 7
                and blocked["available_count"] == 0),
            "docs/principios-construccion.md:L11-U2": (
                findings[0]["action"] == "RESOLVER_DEPENDENCIA"
                and blocked["state"] != "COLA_DISPONIBLE"),
            "docs/principios-construccion.md:L11-U3": (
                {"disponible", "reservado", "en revisión", "bloqueado",
                 "planificado"} <= cola.STATUSES
                and planned["findings"][0]["reason"] == "HOJA_PLANIFICADA"
                and findings[0]["reason"] == "HOJA_BLOQUEADA"),
            "docs/principios-construccion.md:L11-U4": (
                cola.audit(fixture(leaf(10, "bloqueado")))["state"] == UNKNOWN
                and cola.audit(fixture(leaf(10, "bloqueado", "unspecified")))["state"] == UNKNOWN
                and unknowable["status"] == UNKNOWN),
            "docs/principios-construccion.md:L11-U5": (
                "requiere recuperación" in cola.STATUSES
                and recovery["available_count"] == 0
                and recovery["findings"][0]["reason"] == "RESERVA_RECUPERABLE"
                and recovery["findings"][0]["action"] == "RECUPERAR_RESERVA_V3"),
            "docs/principios-construccion.md:L11-U6": (
                global_snapshot["repositories"]["Factory"]["recovery"] == []
                and unknowable["status"] == UNKNOWN),
            "docs/principios-construccion.md:L15-U1": (
                all(p == s == "1" for _, p, s in events)
                and unknowable["status"] == UNKNOWN),
            "docs/principios-construccion.md:L19-U1": (
                claims_overlap("tests/", "tests/candidate.py")
                and verified["safe"] is True
                and verified["reason"] == "verified_disjoint_changed_files"
                and new_file_claim()["safe"] is True
                and new_file_claim(active_files=None)["safe"] is False),
            "docs/principios-construccion.md:L19-U2": (
                not new_file_claim(diff_complete=False)["safe"]
                and not new_file_claim(evidence_head="b" * 40)["safe"]
                and not compared_diff(right_complete=False)["safe"]
                and not compared_diff(left_files=None)["safe"]),
            "docs/principios-construccion.md:L19-U3": (
                claims_overlap("docs/shared.md", "docs/shared.md")
                and compared_diff(left_files=["tests/shared.py"],
                                  right_files=["tests/shared.py"])["reason"]
                == "shared_changed_files"),
            "docs/principios-construccion.md:L23-U1": (
                planned["findings"][0]["reason"] != findings[0]["reason"]
                and cola.audit(fixture(leaf(40, "disponible")))["available_count"] == 1
                and unknowable["status"] == UNKNOWN),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(assertions), set(UNITS))
        self.assertEqual(set(matrix_rows()), set(UNITS))
        for identifier in UNITS:
            with self.subTest(unit=identifier):
                self.assertEqual(len(matrix_rows()[identifier]), 1)
                self.assertTrue(assertions[identifier], identifier + ": UNKNOWN")

    def test_falla_cerrado(self):
        """AC-02: falla cerrada ante staging fallido, scope o diff ambiguo."""
        for failed in ("preview-smoke", "preview-e2e"):
            with self.subTest(stage=failed):
                stages = [stage for stage, _, _ in preview(fail=failed)]
                self.assertIn(failed, stages)
                if failed == "preview-smoke":
                    self.assertNotIn("preview-e2e", stages)
        for change in ({"active_files": None}, {"active_files": []},
                       {"diff_complete": False},
                       {"evidence_head": "b" * 40},
                       {"active_files": ["docs/outside.py"]}):
            with self.subTest(change=change):
                self.assertFalse(new_file_claim(**change)["safe"])
        self.assertEqual(cola.audit(fixture(leaf(1, "bloqueado")))["state"], UNKNOWN)
        self.assertEqual(cola.audit({"version": 1, "source": "fixture",
                                     "complete": False, "issues": []})["state"], UNKNOWN)
        self.assertEqual(cola.audit(fixture(leaf(1, "requiere recuperación")))["available_count"], 0)
        incomplete = global_fixture()
        del incomplete["repositories"]["FactoryRunner"]
        with self.assertRaises(cola_global.NoWorkInventoryError):
            cola_global.canonical_inventory(incomplete)
        with self.assertRaises(PreviewError):
            run_preview(version="1.2.3", sha=SHA, migration_mode="none",
                        phase="live", runner=lambda _: 0,
                        verification_runner=lambda _: 0)

    def test_sin_datos_reales(self):
        """AC-03: fixtures sintéticos, sin llamadas de red ni secretos."""
        fixtures = [fixture(leaf(1, "bloqueado", "human_gate")),
                    global_fixture(), new_file_claim(), compared_diff()]
        encoded = json.dumps(fixtures, sort_keys=True).lower()
        for private in ("https://", "http://", "@gmail", "password",
                        "authorization", "access_token"):
            self.assertNotIn(private, encoded)
        for name in ("build", "preview-smoke", "preview-e2e"):
            adapter = (ROOT / "template/ops/factory" / name).read_text()
            self.assertIn("FACTORY_PREVIEW", adapter)
            self.assertIn("FACTORY_SYNTHETIC_DATA", adapter)
        with patch.dict(os.environ, {"DEPLOY_TOKEN": "synthetic-secret"}):
            with self.assertRaises(PreviewError) as rejected:
                run_preview(version="1.2.3", sha=SHA, migration_mode="none",
                            runner=lambda _: 0, verification_runner=lambda _: 0)
        self.assertNotIn("synthetic-secret", str(rejected.exception))

    def test_estados_unknown_explicitos(self):
        """AC-04: matriz íntegra y evidencia live no inferida de fixtures."""
        rows = matrix_rows()
        self.assertEqual(set(rows), set(UNITS))
        for identifier in UNITS:
            with self.subTest(unit=identifier):
                self.assertEqual(len(rows[identifier]), 1)
                self.assertTrue(rows[identifier][3])
        gaps = (
            "global_seven_repo_inventory_not_observed",
            "blocked_exit_condition_not_verified",
            "legacy_five_state_consumer_not_verified",
            "preview_skipped_on_pr_not_rejected",
            "live_authority_not_observed",
            "ready_without_reservation_not_authorized",
        )
        for reason in gaps:
            with self.subTest(reason=reason):
                evidence = {"status": UNKNOWN, "reason": reason, "head_sha": None}
                self.assertEqual(evidence["status"], UNKNOWN)
                self.assertIsNone(evidence["head_sha"])
                self.assertNotIn("success", evidence.values())


if __name__ == "__main__":
    unittest.main()
