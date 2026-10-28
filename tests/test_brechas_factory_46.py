"""Factory #1664: pruebas offline del contrato labels y preview.

Evidencia sintética no equivale a rulesets aplicados ni producción validada.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from scripts.deploy_kit import DeployError
from scripts.labels_kit import catalog_for_language, closing_issue_reference, validation_plan
from scripts.pr_label_governance import (
    GovernanceError, audit_repository, merged_pr_alert_plan, owner_commands,
    uniform_ruleset_payload,
)
from scripts.preview_kit import PreviewError, _safe_environment, run_preview

ROOT = Path(__file__).resolve().parents[1]
G = "docs/pr-label-governance.md"
P = "docs/preview-preproduccion.md"
IDS = tuple(f"{G}:L{x}-U{y}" for x, y in (
    (7, 1), (50, 1), (54, 1), (54, 2), (56, 1), (57, 1),
    (58, 1), (59, 1), (63, 1),
)) + tuple(f"{P}:L{x}-U1" for x in (10, 11, 12, 13, 15, 17, 29))
UNKNOWN = "UNKNOWN"
# Son invariantes no verificables por tests de un repositorio consumidor.
GAPS = {
    f"{G}:L50-U1": "UNKNOWN: no hay comprobación externa de rulesets antes del POST",
    f"{G}:L54-U1": "UNKNOWN: etiquetas-pr.yml todavía pide pull-requests: write",
    f"{P}:L17-U1": "UNKNOWN: los adapters de cada consumidor no están auditados",
}


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def rows(raw):
    if not isinstance(raw, str):
        raise ValueError("Matriz ilegible")
    found = {}
    for line in raw.splitlines():
        cells = tuple(p.strip() for p in line.strip().strip("|").split("|"))
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in found or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("Fila ambigua: " + key)
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError("Promoción no acreditada: " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("Fila faltante")
    return found


def assess(matrix, evidence):
    verdicts = {key: UNKNOWN for key in IDS}
    try:
        rows(matrix)
    except ValueError:
        return verdicts
    if type(evidence) is not dict or set(evidence) != set(IDS):
        return verdicts
    if any(type(value) is not bool for value in evidence.values()):
        return verdicts
    return {
        unit: "OFFLINE_VERIFIED" if evidence[unit] and unit not in GAPS else UNKNOWN
        for unit in IDS
    }


def governance_evidence():
    catalog = catalog_for_language("es")
    current = {"tipo: pruebas", "prioridad: media"}
    state = validation_plan(catalog, current, is_pull_request=True, body="Closes #1664")
    inherited = validation_plan(
        catalog, set(), is_pull_request=True, body="Fixes #1664",
        linked_names=current,
    )
    duplicate = validation_plan(
        catalog, current | {"tipo: mejora", "estado: en revisión"},
        is_pull_request=True,
    )
    incomplete = validation_plan(catalog, set(), is_pull_request=True)
    unknown = validation_plan(
        catalog, current | {"estado: inexistente"}, is_pull_request=True,
    )
    commands = owner_commands()
    ruleset = uniform_ruleset_payload()
    alert = {
        "pr": {"number": 46, "merged_at": "2026-10-01T00:00:00Z",
               "head": {"sha": "a" * 40}},
        "check_runs": [{
            "id": 77, "name": "Etiquetas", "status": "completed",
            "conclusion": "failure", "completed_at": "2026-10-01T00:00:01Z",
        }],
        "comments": [],
    }
    first = merged_pr_alert_plan(alert)
    alert["comments"] = [{"body": first["body"]}]
    second = merged_pr_alert_plan(alert)
    alert["check_runs"][0]["conclusion"] = "success"
    green = merged_pr_alert_plan(alert)
    workflow = read(".github/workflows/etiquetas.yml")
    dedicated = read(".github/workflows/etiquetas-pr.yml")
    template = read("template/.github/workflows/etiquetas.yml")
    return {
        f"{G}:L7-U1": audit_repository(
            "Factory", rulesets=[], branch_protection=None,
        )["status"] == "unknown",
        f"{G}:L50-U1": (
            ruleset["bypass_actors"] == []
            and all("--method POST" in c for c in commands[1:])
            and not any("--method PATCH" in c or "--method DELETE" in c
                        for c in commands)
        ),
        f"{G}:L54-U1": (
            'gh api --method POST "repos/$REPOSITORIO/issues/$ISSUE_NUMBER/labels"'
            in workflow and "issues: write" in workflow
            and "pull-requests: read" in workflow
            and "pull-requests: write" in dedicated
        ),
        f"{G}:L54-U2": (
            "[:25]" in workflow and '^[0-9a-f]{40}$' in workflow
            and 'curl --fail --silent --show-error' in workflow
            and "/commits/$head_sha/check-runs?per_page=100" in workflow
            and "--header 'Authorization:" not in workflow
        ),
        f"{G}:L56-U1": (
            state["valid"] is True and state["add"] == ["estado: en revisión"]
        ),
        f"{G}:L57-U1": (
            closing_issue_reference("Fixes #1664") == 1664
            and closing_issue_reference("Closes #1664 Resolves #1665") is None
            and inherited["valid"] is True
            and set(inherited["add"]) == current | {"estado: en revisión"}
        ),
        f"{G}:L58-U1": (
            duplicate["valid"] is False and "type" in duplicate["multiple"]
            and incomplete["valid"] is False
            and set(incomplete["missing"]) == {"type", "priority"}
            and unknown["valid"] is False
            and "estado: inexistente" in unknown["unknown"]
        ),
        f"{G}:L59-U1": (
            set(state) == {"add", "closing_issue", "missing",
                           "multiple", "unknown", "valid"}
            and "contents: read" in workflow and "issues: write" in template
            and 'gh api --method POST "repos/$REPOSITORIO/issues/$ISSUE_NUMBER/labels"'
            in workflow
        ),
        f"{G}:L63-U1": (
            first["action"] == "create"
            and "factory-pr-label-governance-alert" in first["body"]
            and "failure" in first["body"]
            and second["reason"] == "already_alerted"
            and green["reason"] == "label_check_green"
        ),
    }


def preview_evidence():
    events, environments = [], []

    def run(stage):
        events.append(stage)
        environments.append(dict(os.environ))
        return 0

    with patch.dict(os.environ, {}, clear=True):
        run_preview(
            version="1.2.3", sha="b"*40, migration_mode="additive",
            runner=run, verification_runner=run,
        )
    failures = []

    def fail_health(stage):
        failures.append(stage)
        return 2 if stage == "preview-health" else 0

    with patch.dict(os.environ, {}, clear=True):
        with_failure = False
        try:
            run_preview(
                version="1.2.3", sha="b"*40, migration_mode="none",
                runner=fail_health, verification_runner=fail_health,
            )
        except DeployError:
            with_failure = True

    adapters = {
        stage: read(f"template/ops/factory/{stage}")
        for stage in ("backup", "migrate", "deploy", "rollback", "preview-health")
    }
    health = adapters["preview-health"]
    roots = {e["FACTORY_PREVIEW_ROOT"] for e in environments}
    ctx = environments[0]
    restricted = _safe_environment(
        {"PATH": "/usr/bin", "CUSTOM_CONTEXT": "disallowed"},
        preview_root="/tmp/factory-1664-test", version="1.2.3",
        sha="b"*40, migration_mode="additive",
    )
    return {
        f"{P}:L10-U1": (
            events.count("backup") == 1
            and events.index("backup") < events.index("deploy")
            and "FACTORY_PREVIEW_ROOT" in adapters["backup"]
        ),
        f"{P}:L11-U1": (
            events.count("migrate") == 1
            and events.index("migrate") < events.index("deploy")
            and "FACTORY_PREVIEW_ROOT" in adapters["migrate"]
        ),
        f"{P}:L12-U1": (
            events.count("deploy") == 1
            and events.index("deploy") < events.index("preview-health")
            and "FACTORY_PREVIEW_ROOT" in adapters["deploy"]
        ),
        f"{P}:L13-U1": (
            with_failure and failures[-1] == "rollback"
            and failures.index("deploy") < failures.index("rollback")
            and "FACTORY_PREVIEW_ROOT" in adapters["rollback"]
        ),
        f"{P}:L15-U1": (
            events == ["build", "backup", "migrate", "deploy",
                       "preview-health", "preview-smoke", "preview-e2e"]
            and len(roots) == 1
            and ctx["FACTORY_PREVIEW"] == "1"
            and ctx["FACTORY_SYNTHETIC_DATA"] == "1"
            and ctx["FACTORY_REQUIRE_SCHEMA"] == "1"
            and ctx["FACTORY_EXPECTED_SHA"] == "b"*40
            and "CUSTOM_CONTEXT" not in restricted
            and not Path(next(iter(roots))).exists()
        ),
        f"{P}:L17-U1": all(
            "FACTORY_PREVIEW_ROOT" in text
            and "FACTORY_SYNTHETIC_DATA" in text
            and "FACTORY_PREVIEW" in text
            for text in adapters.values()
        ),
        f"{P}:L29-U1": (
            events.index("preview-health") < events.index("preview-smoke")
            and all(s in health for s in (
                "FACTORY_EXPECTED_VERSION", "FACTORY_EXPECTED_SHA",
                "FACTORY_REQUIRE_SCHEMA", "schema_up_to_date",
                "payload.get('version')", "payload.get('release_sha')",
            ))
            and with_failure
        ),
    }


class BrechasFactory46Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read("docs/matriz-cobertura.md")
        extracted = rows(matrix)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        self.assertEqual(len(extracted), 16)
        evidence = {**governance_evidence(), **preview_evidence()}
        self.assertEqual(set(evidence), set(IDS))
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(extracted[unit][2], "NO_VERIFICABLE")
                self.assertTrue((ROOT / unit.split(":")[0]).is_file())
                self.assertTrue(evidence[unit], unit)
        verdicts = assess(matrix, evidence)
        self.assertEqual({u for u in IDS if verdicts[u] == UNKNOWN}, set(GAPS))
        self.assertEqual({u for u in IDS if verdicts[u] == "OFFLINE_VERIFIED"},
                         set(IDS) - set(GAPS))

    def test_falla_cerrado(self):
        matrix = read("docs/matriz-cobertura.md")
        original = next(l for l in matrix.splitlines()
                        if chr(96)+IDS[0]+chr(96) in l)
        for corrupt in (
            None, "", matrix.replace(original, "", 1),
            matrix + "\n" + original,
            matrix.replace(original, original.replace(
                "NO_VERIFICABLE", "CUBIERTO", 1
            )),
        ):
            with self.subTest(sample=str(corrupt)[:30]):
                with self.assertRaises(ValueError):
                    rows(corrupt)
                self.assertEqual(
                    set(assess(corrupt, {u: True for u in IDS}).values()),
                    {UNKNOWN},
                )
        for invalid in (
            None, {}, {IDS[0]: True}, {u: 1 for u in IDS},
            {**{u: True for u in IDS}, "unknown-id": True},
        ):
            self.assertEqual(set(assess(matrix, invalid).values()), {UNKNOWN})
        with self.assertRaises(GovernanceError):
            merged_pr_alert_plan({"pr": {}, "check_runs": []})
        with patch.dict(os.environ, {}, clear=True):
            for bad in (
                {"version": "bad", "sha": "b"*40, "migration_mode": "none"},
                {"version": "1.2.3", "sha": "bad", "migration_mode": "none"},
                {"version": "1.2.3", "sha": "b"*40, "migration_mode": "none",
                 "phase": "live"},
            ):
                with self.subTest(bad=bad), self.assertRaises(PreviewError):
                    run_preview(
                        **bad, runner=lambda _: 0, verification_runner=lambda _: 0,
                    )

    def test_sin_datos_reales(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {"DEPLOY_TOKEN": "synthetic-blocked"}):
                with self.assertRaises(PreviewError):
                    run_preview(
                        version="1.2.3", sha="b"*40, migration_mode="none",
                        runner=lambda _: 0, verification_runner=lambda _: 0,
                    )
        source = read("tests/test_brechas_factory_46.py")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0] for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        self.assertFalse(imports & {"requests", "socket", "subprocess", "urllib"})
        self.assertTrue(all(unit.startswith("docs/") for unit in IDS))
        self.assertTrue(all(s.startswith("UNKNOWN:") for s in GAPS.values()))

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        evidence = {**governance_evidence(), **preview_evidence()}
        verdicts = assess(matrix, evidence)
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertNotEqual(verdicts[unit], "PRODUCTION_GREEN")
                self.assertEqual(assess(matrix, {**evidence, unit: False})[unit],
                                 UNKNOWN)
                self.assertEqual(assess(matrix, {unit: True})[unit], UNKNOWN)
        self.assertEqual({u for u in IDS if verdicts[u] == UNKNOWN}, set(GAPS))
        self.assertEqual(
            audit_repository("Factory", rulesets=[],
                             branch_protection=None)["status"], "unknown",
        )


if __name__ == "__main__":
    unittest.main()
