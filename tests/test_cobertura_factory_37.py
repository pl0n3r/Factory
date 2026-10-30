#!/usr/bin/env python3
"""Factory #1828: 14 contratos reales y 6 límites explícitos de cobertura.

No lee la matriz. Ejecuta planes puros de etiquetas y el pipeline de preview
con runners sintéticos; nunca usa GitHub, claves, servidores o datos reales.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.labels_kit import (
    LabelError, catalog_for_language, closing_issue_reference,
    validation_plan,
)
from scripts.pr_label_governance import (
    GovernanceError, audit_repository, merged_pr_alert_plan,
    uniform_ruleset_payload,
)
from scripts.deploy_kit import DeployError
from scripts.preview_kit import PreviewError, _adapter_path, run_preview


G = "docs/pr-label-governance.md"
P = "docs/preview-preproduccion.md"
A = {
    f"{G}:L7-U1", f"{G}:L56-U1", f"{G}:L57-U1",
    f"{G}:L58-U1", f"{G}:L59-U1", f"{G}:L63-U1",
    f"{P}:L10-U1", f"{P}:L11-U1", f"{P}:L12-U1",
    f"{P}:L13-U1", f"{P}:L15-U1", f"{P}:L29-U1",
    f"{P}:L30-U1", f"{P}:L31-U1",
}
LIMITS = {
    f"{G}:L38-U1": ("C", "Aplicación administrativa owner-only: la prueba "
                    "offline no autoriza ni ejecuta operaciones de rulesets."),
    f"{G}:L50-U1": ("C", "Releer y revisar un ruleset equivalente requiere "
                    "un acto del dueño y evidencia autenticada de GitHub."),
    f"{G}:L54-U1": ("D", "El reusable etiquetas-pr.yml todavía solicita "
                    "pull-requests: write; no acredita el permiso mínimo descrito."),
    f"{G}:L54-U2": ("D", "No existe en el código ejercitado un sweep de siete "
                    "repos con check-runs REST anónimo y validación exacta de SHA."),
    f"{P}:L17-U1": ("B", "El cumplimiento por los adapters de cada consumidor "
                    "requiere evidencia de esos repos; el kit solo aísla su entorno."),
    f"{P}:L37-U1": ("B", "La dependencia efectiva de Validar respecto de CI y "
                    "preview reside en los workflows de cada consumidor."),
}
assert len(A) == 14 and len(LIMITS) == 6 and len(A | set(LIMITS)) == 20


def _labels():
    catalog = catalog_for_language("es")
    names = {
        kind: [row["name"] for row in catalog if row["key"].startswith(kind)]
        for kind in ("type_", "priority_", "state_")
    }
    return catalog, names


def _alert(*, conclusion="failure"):
    return {
        "pr": {"number": 37, "merged_at": "2026-10-01T10:00:00Z",
               "head": {"sha": "a" * 40}},
        "check_runs": [
            {"name": "validar-pr / Labels", "status": "completed",
             "conclusion": conclusion, "id": 1,
             "completed_at": "2026-10-01T10:00:01Z"}
        ],
        "comments": [],
    }


def _preview(*, fail_stage=None, migration_mode="additive"):
    stages = []
    envs = []

    def runner(stage):
        stages.append(stage)
        envs.append({
            "preview": os.environ.get("FACTORY_PREVIEW"),
            "synthetic": os.environ.get("FACTORY_SYNTHETIC_DATA"),
            "root": os.environ.get("FACTORY_PREVIEW_ROOT"),
            "version": os.environ.get("FACTORY_EXPECTED_VERSION"),
            "sha": os.environ.get("FACTORY_EXPECTED_SHA"),
            "schema": os.environ.get("FACTORY_REQUIRE_SCHEMA"),
            "live_token": os.environ.get("DEPLOY_TOKEN"),
        })
        return 7 if stage == fail_stage else 0

    before = dict(os.environ)
    # Prevent any ambient runner credentials from reaching this synthetic test.
    with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
        try:
            run_preview(
                version="1.2.3", sha="b" * 40,
                migration_mode=migration_mode,
                runner=runner, verification_runner=runner,
            )
        except DeployError:
            if fail_stage is None:
                raise
            failed = True
        else:
            failed = False
    if dict(os.environ) != before:
        raise AssertionError("preview cambió el entorno global")
    return stages, envs, failed


class CoberturaFactory37Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: aserciones independientes sobre 14 unidades implementadas."""
        catalog, names = _labels()
        state = next(row["name"] for row in catalog
                     if row["key"] == "state_review")
        classification = {names["type_"][0], names["priority_"][0]}
        missing_state = validation_plan(
            catalog, classification, is_pull_request=True,
        )
        inherited = validation_plan(
            catalog, set(), is_pull_request=True, body="Closes #314",
            linked_names={names["type_"][0], names["priority_"][0]},
        )
        ambiguous = validation_plan(
            catalog, {names["type_"][0], *names["priority_"][:2], state},
            is_pull_request=True,
        )
        privacy_plan = validation_plan(
            catalog, classification, is_pull_request=True,
        )
        # Real policy evaluation, including absence of branch-protection data.
        unknown = audit_repository(
            "Factory", rulesets=[], branch_protection=None,
        )
        payload = uniform_ruleset_payload()
        alert = merged_pr_alert_plan(_alert())
        already = _alert()
        already["comments"].append({"body": alert["body"]})
        suppressed = merged_pr_alert_plan(already)

        events, environments, failed = _preview()
        rollback, rollback_env, rollback_failed = _preview(
            fail_stage="preview-health", migration_mode="none",
        )
        normal = ["build", "backup", "migrate", "deploy",
                  "preview-health", "preview-smoke", "preview-e2e"]
        proofs = {
            f"{G}:L7-U1": (unknown["status"] == "unknown"
                            and unknown["branch_protection_visible"] is False),
            f"{G}:L56-U1": (missing_state["valid"] is True
                             and missing_state["add"] == [state]),
            f"{G}:L57-U1": (inherited["valid"] is True
                             and inherited["closing_issue"] == 314
                             and set(inherited["add"]) ==
                             {names["type_"][0], names["priority_"][0], state}),
            f"{G}:L58-U1": (ambiguous["valid"] is False
                             and "priority" in ambiguous["multiple"]),
            f"{G}:L59-U1": (privacy_plan == missing_state
                             and payload["bypass_actors"] == []
                             and all("content" not in key.lower()
                                     for key in privacy_plan)),
            f"{G}:L63-U1": (alert["action"] == "create"
                             and "pr=37" in alert["body"]
                             and suppressed["action"] == "noop"
                             and suppressed["reason"] == "already_alerted"),
            f"{P}:L10-U1": (events[1] == "backup"
                             and rollback[1] == "backup"),
            f"{P}:L11-U1": (events[2] == "migrate"
                             and "migrate" not in rollback),
            f"{P}:L12-U1": (events[3] == "deploy"
                             and rollback[2] == "deploy"),
            f"{P}:L13-U1": (rollback_failed is True
                             and rollback[-1] == "rollback"),
            f"{P}:L15-U1": (
                events == normal and failed is False
                and bool(environments)
                and all(e["preview"] == "1" and e["synthetic"] == "1"
                        and e["root"] and e["version"] == "1.2.3"
                        and e["sha"] == "b" * 40 and e["schema"] == "1"
                        and e["live_token"] is None for e in environments)
                and all(e["schema"] == "0" for e in rollback_env)
            ),
            f"{P}:L29-U1": ("preview-health" in events
                             and events.index("preview-health") >
                             events.index("deploy")),
            f"{P}:L30-U1": ("preview-smoke" in events
                             and events.index("preview-smoke") >
                             events.index("preview-health")),
            f"{P}:L31-U1": (events[-1] == "preview-e2e"
                             and events.index("preview-e2e") >
                             events.index("preview-smoke")),
        }
        self.assertEqual(set(proofs), A)
        self.assertEqual(set(proofs) | set(LIMITS), A | set(LIMITS))
        for row, verified in proofs.items():
            with self.subTest(row=row):
                self.assertIs(verified, True, "Contrato sin evidencia: " + row)

    def test_falla_cerrado(self):
        """AC-02: ambigüedad, permisos y fallos de preview no autorizan writes."""
        catalog, names = _labels()
        with self.assertRaises(GovernanceError):
            audit_repository("foreign", rulesets=[], branch_protection=None)
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets={}, branch_protection=None)
        self.assertEqual(closing_issue_reference("Closes #7; Fixes #8"), None)
        self.assertEqual(closing_issue_reference("Closes #7"), 7)
        with self.assertRaises(LabelError):
            validation_plan(
                catalog, {names["type_"][0]}, is_pull_request="yes",
            )
        invalid = validation_plan(
            catalog, {names["type_"][0], names["priority_"][0],
                      "prioridad: no-canónica"}, is_pull_request=True,
        )
        self.assertFalse(invalid["valid"])
        self.assertIn("prioridad: no-canónica", invalid["unknown"])
        incomplete_alert = _alert()
        incomplete_alert["check_runs"][0]["status"] = "queued"
        self.assertEqual(
            merged_pr_alert_plan(incomplete_alert)["action"], "noop",
        )
        no_red = merged_pr_alert_plan(_alert(conclusion="success"))
        self.assertEqual(no_red["reason"], "label_check_green")
        for malformed in ({"pr": {}, "comments": []}, [], None):
            with self.subTest(document=malformed):
                with self.assertRaises(GovernanceError):
                    merged_pr_alert_plan(malformed)

        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            with self.assertRaisesRegex(PreviewError, "construccion"):
                run_preview(version="1.2.3", sha="b" * 40,
                            migration_mode="none", phase="live",
                            runner=lambda stage: 0,
                            verification_runner=lambda stage: 0)
            with self.assertRaisesRegex(PreviewError, "SHA"):
                run_preview(version="1.2.3", sha="invalid",
                            migration_mode="none", runner=lambda stage: 0,
                            verification_runner=lambda stage: 0)
            with self.assertRaisesRegex(PreviewError, "credenciales"):
                with patch.dict(os.environ, {"DEPLOY_TOKEN": "synthetic-private"}):
                    run_preview(version="1.2.3", sha="b" * 40,
                                migration_mode="none", runner=lambda stage: 0,
                                verification_runner=lambda stage: 0)
        for failure in ("preview-smoke", "preview-e2e"):
            events, _, rejected = _preview(
                fail_stage=failure, migration_mode="none",
            )
            with self.subTest(stage=failure):
                self.assertTrue(rejected)
                self.assertIn(failure, events)
                if failure == "preview-smoke":
                    self.assertNotIn("preview-e2e", events)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(PreviewError):
                _adapter_path("unknown", root=root)
            link = root / "ops" / "factory" / "preview-health"
            link.parent.mkdir(parents=True)
            target = root / "target"
            target.write_text("synthetic", encoding="utf-8")
            link.symlink_to(target)
            with self.assertRaises(PreviewError):
                _adapter_path("preview-health", root=root)

    def test_sin_datos_reales(self):
        """AC-03: solo valores sintéticos y rutas efímeras; B/C/D declarados."""
        self.assertEqual(len(A), 14)
        self.assertEqual(len(LIMITS), 6)
        self.assertEqual(len(A | set(LIMITS)), 20)
        self.assertEqual(
            {row[0] for row in LIMITS.values()}, {"B", "C", "D"},
        )
        self.assertTrue(all(reason for _, reason in LIMITS.values()))
        before = dict(os.environ)
        events, captured, failed = _preview(migration_mode="none")
        self.assertEqual(dict(os.environ), before)
        self.assertFalse(failed)
        self.assertEqual(
            events, ["build", "backup", "deploy", "preview-health",
                     "preview-smoke", "preview-e2e"],
        )
        self.assertTrue(captured)
        self.assertTrue(all(not Path(e["root"]).exists() for e in captured))
        self.assertTrue(all(e["live_token"] is None for e in captured))


if __name__ == "__main__":
    unittest.main()
