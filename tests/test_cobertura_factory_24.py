#!/usr/bin/env python3
"""Factory #1815: real offline behavioral evidence for label colors and planned state.

Policy-only items have no executable assertion: no release, deploy, or label apply.
"""
from __future__ import annotations

import ast
import copy
import io
from pathlib import Path
import unittest
from unittest import mock

from scripts.labels_kit import (
    LabelError, catalog_for_language, planned_state_decision,
    planned_state_migration_plan, validate_selection,
)
from scripts.sync_label_colors import (
    GitHubLabelsClient, REPOSITORIES, REPOSITORY_LANGUAGE, SyncError,
    assert_safe_plan, execute, load_catalogs, plan_all, plan_repository,
    render_plan, validate_catalog_parity, main as sync_main,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
BT = chr(96)
PREFIX = "docs/label-color-sync.md:"
UNITS = (
    "L10-U1", "L11-U1", "L17-U1", "L18-U1", "L18-U2",
    "L20-U1", "L22-U1", "L22-U2", "L22-U3", "L24-U1",
    "L24-U2", "L28-U1", "L30-U1", "L30-U2", "L32-U1",
    "L36-U1", "L36-U2", "L38-U1", "L7-U1", "L7-U2",
)
# ControlBot adoption, publication order, historical commands: C, not a test.
POLICY_ONLY = frozenset(("L24-U1", "L24-U2", "L28-U1"))


def coverage_rows(raw: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, str) or not raw:
        raise ValueError("UNKNOWN: no matrix")
    rows: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        if not line.startswith("| " + BT + PREFIX):
            continue
        parts = tuple(part.strip() for part in line.strip("|").split("|"))
        if len(parts) != 5:
            raise ValueError("UNKNOWN: malformed source")
        key = parts[0].removeprefix(BT + PREFIX).removesuffix(BT)
        if key not in UNITS:
            continue
        if key in rows:
            raise ValueError("UNKNOWN: duplicate")
        if (parts[0] != BT + PREFIX + key + BT or not parts[1]
                or parts[2] != "NO_VERIFICABLE"
                or "Contraste #1571" not in parts[3] or parts[4] != "—"):
            raise ValueError("UNKNOWN: invalid matrix row")
        rows[key] = parts
    if set(rows) != set(UNITS):
        raise ValueError("UNKNOWN: missing unit")
    return rows


def synthetic_issue(dependencies=None) -> dict:
    return {
        "number": 42, "title": "Roadmap: fase ficticia", "body": "",
        "labels": [{"name": "tipo: mejora"}, {"name": "prioridad: media"},
                   {"name": "estado: bloqueado"}],
        "dependencies_open": [] if dependencies is None else dependencies,
    }


def snapshots(catalogs):
    return {
        repo: [{"name": x["name"], "color": x["color"]}
               for x in catalogs[REPOSITORY_LANGUAGE[repo]]]
        for repo in REPOSITORIES
    }


class CoberturaFactory24Tests(unittest.TestCase):
    def setUp(self):
        self.catalogs = load_catalogs(ROOT)
        self.es = catalog_for_language("es")
        self.en = catalog_for_language("en")

    def operation(self, repo="pl0n3r/Factory"):
        name = "priority: medium" if repo == "pl0n3r/brvtal" else "prioridad: media"
        items = plan_repository(repo, [{"name": name, "color": "FFFFFF",
                                        "description": "unchanged"}], self.catalogs)
        self.assertEqual(1, len(items))
        return items[0]

    def test_contrato_principal(self):
        """Each A unit exercises existing production code with synthetic inputs."""
        rows = coverage_rows(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 20)
        self.assertEqual(len(UNITS) - len(POLICY_ONLY), 17)
        for unit in UNITS:
            with self.subTest(unit=PREFIX + unit):
                self.assertTrue(rows[unit][1])
                if unit in POLICY_ONLY:
                    # A policy/future rollout must not become fake test coverage.
                    continue
                if unit == "L10-U1":
                    op = self.operation()
                    self.assertEqual("update_color", op["action"])
                    self.assertEqual(
                        {"action", "repository", "label", "color_before", "color_after"},
                        set(op),
                    )
                    writer = GitHubLabelsClient("fixture-only")
                    with mock.patch.object(writer, "_request", return_value={}) as call:
                        writer.update_color(op)
                    method, path, payload = call.call_args.args
                    self.assertEqual("PATCH", method)
                    self.assertIn("prioridad%3A%20media", path)
                    self.assertEqual({"color": op["color_after"]}, payload)
                elif unit == "L11-U1":
                    self.assertEqual("priority: medium",
                                     self.operation("pl0n3r/brvtal")["label"])
                    self.assertEqual([], plan_repository(
                        "pl0n3r/brvtal",
                        [{"name": "prioridad: media", "color": "FFFFFF"}],
                        self.catalogs,
                    ))
                elif unit == "L17-U1":
                    classified = planned_state_decision(
                        synthetic_issue(["Factory#994"]))
                    self.assertFalse(classified["planned"])
                    self.assertEqual("real_dependency_block", classified["reason"])
                elif unit == "L18-U1":
                    self.assertTrue(planned_state_decision(synthetic_issue())["planned"])
                    validate_selection(self.es, {
                        "tipo: mejora", "prioridad: media", "estado: planificado"})
                elif unit == "L18-U2":
                    already = synthetic_issue()
                    already["labels"][-1]["name"] = "estado: planificado"
                    blocked = synthetic_issue(["Factory#994"])
                    blocked["number"] = 43
                    self.assertEqual([], planned_state_migration_plan(
                        self.es, [already, blocked]))
                elif unit == "L20-U1":
                    with self.assertRaises(LabelError):
                        validate_selection(self.es, {
                            "tipo: mejora", "prioridad: media",
                            "estado: bloqueado", "estado: planificado"})
                    with self.assertRaises(LabelError):
                        validate_selection(self.en, {
                            "type: enhancement", "priority: medium",
                            "status: available", "status: planned"})
                elif unit == "L22-U1":
                    unknown = synthetic_issue()
                    del unknown["dependencies_open"]
                    self.assertEqual("execution_evidence_incomplete",
                                     planned_state_decision(unknown)["reason"])
                elif unit == "L22-U2":
                    for change in ({"executable": True},
                                   {"has_ready_leaf": True},
                                   {"dependencies_open": ["Factory#994"]}):
                        self.assertFalse(planned_state_decision(
                            {**synthetic_issue(), **change})["planned"])
                elif unit == "L22-U3":
                    plan = planned_state_migration_plan(
                        self.es, [synthetic_issue()])
                    self.assertEqual([{
                        "action": "relabel", "issue": 42, "from": "estado: bloqueado",
                        "to": "estado: planificado", "reason": "planning_title",
                    }], plan)
                    migrated = synthetic_issue()
                    migrated["labels"][-1]["name"] = "estado: planificado"
                    self.assertEqual([], planned_state_migration_plan(
                        self.es, [migrated]))
                elif unit == "L30-U1":
                    with mock.patch("scripts.sync_label_colors.execute",
                                    return_value=([], [])) as execute_call:
                        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                            self.assertEqual(0, sync_main(["--dry-run"]))
                    execute_call.assert_called_once_with(apply=False, token=None)
                    self.assertEqual("0 drifts\n", out.getvalue())
                elif unit == "L30-U2":
                    before = snapshots(self.catalogs)
                    before["pl0n3r/Factory"][0]["color"] = "FFFFFF"
                    before["pl0n3r/brvtal"][1]["color"] = "FFFFFF"
                    changes = plan_all(before, self.catalogs)
                    self.assertEqual(2, len(changes))
                    self.assertEqual({"update_color"}, {x["action"] for x in changes})
                    for op in changes:
                        for item in before[op["repository"]]:
                            if item["name"] == op["label"]:
                                item["color"] = op["color_after"]
                    self.assertEqual([], plan_all(before, self.catalogs))
                elif unit == "L32-U1":
                    with self.assertRaisesRegex(SyncError, "FACTORY_PROVISION_TOKEN"):
                        GitHubLabelsClient().update_color(self.operation())
                    class NoNetwork:
                        def list_labels(self, repo):
                            return snapshots(self_outer.catalogs)[repo]
                        def update_color(self, op):
                            raise AssertionError("No remote writes")
                    self_outer = self
                    with mock.patch("scripts.sync_label_colors.GitHubLabelsClient",
                                    return_value=NoNetwork()):
                        with self.assertRaisesRegex(SyncError, "FACTORY_PROVISION_TOKEN"):
                            execute(apply=True, token=None)
                elif unit == "L36-U1":
                    op = self.operation()
                    self.assertIn("FFFFFF -> FBCA04", render_plan([op]))
                    inverse = {**op, "color_before": op["color_after"],
                               "color_after": op["color_before"]}
                    assert_safe_plan([inverse])
                    self.assertIn("FBCA04 -> FFFFFF", render_plan([inverse]))
                elif unit == "L36-U2":
                    op = self.operation()
                    for action in ("create", "delete", "rename", "reassign"):
                        with self.assertRaises(SyncError):
                            assert_safe_plan([{**op, "action": action}])
                    with self.assertRaises(SyncError):
                        assert_safe_plan([{**op, "description": "changed"}])
                elif unit == "L38-U1":
                    with self.assertRaises(SyncError):
                        plan_repository("pl0n3r/Unknown", [], self.catalogs)
                    with self.assertRaises(SyncError):
                        plan_repository("pl0n3r/Factory", [
                            {"name": "tipo: error", "color": "FFFFFF"},
                            {"name": "tipo: error", "color": "000000"},
                        ], self.catalogs)
                    with self.assertRaises(SyncError):
                        validate_catalog_parity(
                            [{"key": "k", "color": "FFFFFF"}],
                            [{"key": "k", "color": "000000"}])
                    reader = GitHubLabelsClient()
                    with mock.patch.object(reader, "_request",
                                           return_value={"invalid": True}):
                        with self.assertRaises(SyncError):
                            reader.list_labels("pl0n3r/Factory")
                elif unit == "L7-U1":
                    expected = set(REPOSITORIES) - {"pl0n3r/brvtal"}
                    self.assertEqual(expected, {r for r in REPOSITORIES
                                                if REPOSITORY_LANGUAGE[r] == "es"})
                    self.assertEqual("estado: planificado", next(
                        x["name"] for x in self.catalogs["es"]
                        if x["key"] == "state_planned"))
                elif unit == "L7-U2":
                    self.assertEqual("en", REPOSITORY_LANGUAGE["pl0n3r/brvtal"])
                    self.assertEqual("status: planned", next(
                        x["name"] for x in self.catalogs["en"]
                        if x["key"] == "state_planned"))
                    self.assertEqual(
                        {x["key"]: x["color"] for x in self.catalogs["es"]},
                        {x["key"]: x["color"] for x in self.catalogs["en"]})
                else:
                    self.fail("Uncovered executable unit " + unit)

    def test_falla_cerrado(self):
        """Fail on missing/duplicate/altered matrix evidence or invalid state."""
        raw = MATRIX.read_text(encoding="utf-8")
        coverage_rows(raw)
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            coverage_rows(None)
        for unit in UNITS:
            line = next(x for x in raw.splitlines()
                        if x.startswith("| " + BT + PREFIX + unit + BT + " |"))
            for corrupted in (
                raw.replace(line, "", 1),
                raw + "\n" + line,
                raw.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(unit=unit):
                    with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                        coverage_rows(corrupted)
        with self.assertRaises(LabelError):
            planned_state_decision({**synthetic_issue(),
                                    "dependencies_open": "not-a-list"})
        with self.assertRaises(LabelError):
            planned_state_decision({**synthetic_issue(),
                                    "has_ready_leaf": "yes"})
        with self.assertRaises(LabelError):
            planned_state_migration_plan(self.es,
                                         [synthetic_issue(), synthetic_issue()])
        with self.assertRaises(SyncError):
            plan_all({}, self.catalogs)
        with self.assertRaises(SyncError):
            assert_safe_plan([{"action": "delete"}])

    def test_sin_datos_reales(self):
        """Simulate a real read-only dry-run; no secret or external I/O."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(imports & {
            "requests", "httpx", "socket", "selenium", "playwright", "subprocess"})
        existing = snapshots(self.catalogs)
        class ReadOnlyClient:
            def list_labels(self, repo):
                return copy.deepcopy(existing[repo])
            def update_color(self, op):
                raise AssertionError("No remote writes")
        with mock.patch("scripts.sync_label_colors.GitHubLabelsClient",
                        return_value=ReadOnlyClient()) as client:
            plan, residual = execute(apply=False, token="discarded")
        client.assert_called_once_with(None)
        self.assertEqual([], plan)
        self.assertEqual([], residual)
        self.assertEqual(20, len(coverage_rows(MATRIX.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    unittest.main()
