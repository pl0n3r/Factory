#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from scripts.sync_label_colors import (
    GitHubLabelsClient,
    REPOSITORIES,
    SyncError,
    assert_safe_plan,
    collect_snapshots,
    execute,
    load_catalog,
    load_catalogs,
    main,
    plan_all,
    plan_repository,
    render_plan,
    validate_catalog_parity,
)

ROOT = Path(__file__).resolve().parents[1]


class SyncLabelColorsTests(unittest.TestCase):
    def setUp(self):
        self.catalogs = load_catalogs(ROOT)

    def _canonical_snapshot(self, repository):
        language = "en" if repository == "pl0n3r/brvtal" else "es"
        return [
            {"name": item["name"], "color": item["color"]}
            for item in self.catalogs[language]
        ]

    def test_es_and_en_catalogs_keep_color_parity_by_key(self):
        es = {item["key"]: item for item in self.catalogs["es"]}
        en = {item["key"]: item for item in self.catalogs["en"]}
        self.assertEqual(set(es), set(en))
        self.assertEqual(
            {key: item["color"] for key, item in es.items()},
            {key: item["color"] for key, item in en.items()},
        )

    def test_dry_run_is_deterministic_and_reports_only_color_drift(self):
        snapshots = {
            repository: self._canonical_snapshot(repository)
            for repository in REPOSITORIES
        }
        snapshots["pl0n3r/Factory"][0]["color"] = "FFFFFF"
        snapshots["pl0n3r/brvtal"][1]["color"] = "000000"
        snapshots["pl0n3r/Condor"] = snapshots["pl0n3r/Condor"][1:]
        snapshots["pl0n3r/Factory"].append(
            {"name": "custom: untouched", "color": "123456"}
        )

        first = plan_all(snapshots, self.catalogs)
        second = plan_all(
            {repository: list(reversed(labels)) for repository, labels in snapshots.items()},
            self.catalogs,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertTrue(all(item["action"] == "update_color" for item in first))
        output = render_plan(first)
        self.assertIn("pl0n3r/Factory + tipo: error + FFFFFF -> D73A4A", output)
        self.assertIn("pl0n3r/brvtal + type: enhancement + 000000 -> A2EEEF", output)
        self.assertNotIn("custom: untouched", output)

    def test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories(self):
        existing = [{"name": "prioridad: media", "color": "FFFFFF"}]
        plan = plan_repository("pl0n3r/Factory", existing, self.catalogs)
        self.assertEqual(
            plan,
            [{
                "action": "update_color",
                "repository": "pl0n3r/Factory",
                "label": "prioridad: media",
                "color_before": "FFFFFF",
                "color_after": "FBCA04",
            }],
        )
        self.assertFalse(any(item["action"] in {"create", "delete", "rename"} for item in plan))

        with self.assertRaises(SyncError):
            plan_repository("pl0n3r/Unknown", existing, self.catalogs)
        for action in ("create", "delete", "rename", "update"):
            with self.subTest(action=action), self.assertRaises(SyncError):
                assert_safe_plan([{
                    "action": action,
                    "repository": "pl0n3r/Factory",
                    "label": "prioridad: media",
                    "color_before": "FFFFFF",
                    "color_after": "FBCA04",
                }])

    def test_brvtal_uses_english_catalog_without_renaming_labels(self):
        existing = [
            {"name": "priority: medium", "color": "FFFFFF"},
            {"name": "prioridad: media", "color": "FFFFFF"},
        ]
        plan = plan_repository("pl0n3r/brvtal", existing, self.catalogs)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["label"], "priority: medium")
        self.assertEqual(plan[0]["color_after"], "FBCA04")
        self.assertNotIn("prioridad: media", render_plan(plan))
        self.assertTrue(all(item["action"] == "update_color" for item in plan))

    def test_identical_colors_produce_empty_idempotent_plan(self):
        snapshots = {
            repository: self._canonical_snapshot(repository)
            for repository in REPOSITORIES
        }
        self.assertEqual(plan_all(snapshots, self.catalogs), [])
        self.assertEqual(render_plan([]), "0 drifts")

    def test_workflow_is_owner_only_secret_safe_and_apply_is_explicit(self):
        workflow = (ROOT / ".github/workflows/sync-label-colors.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.issue.number == 874", workflow)
        self.assertIn("github.event.sender.login == github.event.repository.owner.login", workflow)
        self.assertEqual(workflow.count("/sync-label-colors dry-run"), 2)
        self.assertEqual(workflow.count("/sync-label-colors apply"), 2)
        self.assertIn("python3 scripts/sync_label_colors.py --dry-run", workflow)
        self.assertIn("python3 scripts/sync_label_colors.py --apply", workflow)
        self.assertIn("FACTORY_PROVISION_TOKEN: ${{ secrets.FACTORY_PROVISION_TOKEN }}", workflow)

        dry_run_block, apply_block = workflow.split("      - name: Aplicar colores", 1)
        self.assertNotIn("FACTORY_PROVISION_TOKEN", dry_run_block)
        self.assertIn("FACTORY_PROVISION_TOKEN", apply_block)
        self.assertNotIn("github.token", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("issues: write", workflow)
        workflow_prefix, jobs_block = workflow.split("jobs:", 1)
        self.assertNotIn("\nconcurrency:", workflow_prefix)
        self.assertIn("    concurrency:\n      group: factory-label-color-sync", jobs_block)


    def test_apply_prints_plan_before_first_patch_and_records_successes(self):
        snapshots = {
            repository: self._canonical_snapshot(repository)
            for repository in REPOSITORIES
        }
        snapshots["pl0n3r/Factory"][0]["color"] = "FFFFFF"
        snapshots["pl0n3r/Factory"][1]["color"] = "000000"

        class FailingClient:
            def __init__(self):
                self.calls = 0
            def list_labels(self, repository):
                return [dict(item) for item in snapshots[repository]]
            def update_color(self, operation):
                self.calls += 1
                if self.calls == 2:
                    raise SyncError("fallo controlado")
                for item in snapshots[operation["repository"]]:
                    if item["name"] == operation["label"]:
                        item["color"] = operation["color_after"]
                        return
                raise AssertionError("label missing")

        stdout = io.StringIO()
        with mock.patch(
            "scripts.sync_label_colors.GitHubLabelsClient",
            return_value=FailingClient(),
        ), mock.patch("sys.stdout", stdout):
            with self.assertRaisesRegex(SyncError, "fallo controlado"):
                execute(apply=True, token="token")

        output = stdout.getvalue()
        first = self.catalogs["es"][0]
        second = self.catalogs["es"][1]
        self.assertIn(
            f'pl0n3r/Factory + {first["name"]} + FFFFFF -> {first["color"]}',
            output,
        )
        self.assertIn(
            f'pl0n3r/Factory + {second["name"]} + 000000 -> {second["color"]}',
            output,
        )
        self.assertIn(f'applied: pl0n3r/Factory + {first["name"]}', output)
        self.assertNotIn(f'applied: pl0n3r/Factory + {second["name"]}', output)


    def test_catalog_and_snapshot_validation_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(SyncError):
                load_catalog(path)

            path.write_text(json.dumps([
                {"key": "a", "name": "x", "color": "FFFFFF"},
                {"key": "a", "name": "y", "color": "000000"},
            ]), encoding="utf-8")
            with self.assertRaises(SyncError):
                load_catalog(path)

            path.write_text(json.dumps([
                {"key": "a", "name": "x", "color": "BAD"},
            ]), encoding="utf-8")
            with self.assertRaises(SyncError):
                load_catalog(path)

        with self.assertRaises(SyncError):
            validate_catalog_parity(
                [{"key": "a", "name": "x", "color": "FFFFFF"}],
                [{"key": "b", "name": "y", "color": "FFFFFF"}],
            )
        with self.assertRaises(SyncError):
            validate_catalog_parity(
                [{"key": "a", "name": "x", "color": "FFFFFF"}],
                [{"key": "a", "name": "y", "color": "000000"}],
            )
        with self.assertRaises(SyncError):
            plan_repository(
                "pl0n3r/Factory",
                [
                    {"name": "prioridad: media", "color": "FFFFFF"},
                    {"name": "prioridad: media", "color": "000000"},
                ],
                self.catalogs,
            )
        with self.assertRaises(SyncError):
            plan_all({"pl0n3r/Factory": []}, self.catalogs)

    def test_github_request_is_secret_safe_and_fail_closed(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return self.payload

        client = GitHubLabelsClient(" secret-token ")
        with self.assertRaises(SyncError):
            client._request("GET", "/users/me")

        with mock.patch(
            "scripts.sync_label_colors.urlopen",
            return_value=Response(b'{"ok": true}'),
        ) as urlopen:
            self.assertEqual(client._request("GET", "/repos/pl0n3r/Factory/labels"), {"ok": True})
            request = urlopen.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")

        with mock.patch(
            "scripts.sync_label_colors.urlopen",
            return_value=Response(b""),
        ):
            self.assertIsNone(client._request("GET", "/repos/pl0n3r/Factory/labels"))

        with mock.patch(
            "scripts.sync_label_colors.urlopen",
            return_value=Response(b"{"),
        ):
            with self.assertRaises(SyncError):
                client._request("GET", "/repos/pl0n3r/Factory/labels")

        http_error = HTTPError("https://api.github.com/x", 500, "bad", {}, None)
        with mock.patch("scripts.sync_label_colors.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(SyncError, "HTTP 500"):
                client._request("GET", "/repos/pl0n3r/Factory/labels")
        with mock.patch(
            "scripts.sync_label_colors.urlopen",
            side_effect=URLError("offline"),
        ):
            with self.assertRaisesRegex(SyncError, "consultar GitHub"):
                client._request("GET", "/repos/pl0n3r/Factory/labels")

    def test_client_paginates_reads_and_apply_only_patches_color(self):
        client = GitHubLabelsClient()
        page = [{"name": f"l-{index}", "color": "FFFFFF"} for index in range(100)]
        tail = [{"name": "last", "color": "000000"}]
        with mock.patch.object(client, "_request", side_effect=[page, tail]) as request:
            labels = client.list_labels("pl0n3r/Factory")
        self.assertEqual(len(labels), 101)
        self.assertEqual(request.call_count, 2)
        with self.assertRaises(SyncError):
            client.list_labels("pl0n3r/Unknown")

        operation = {
            "action": "update_color",
            "repository": "pl0n3r/Factory",
            "label": "state/with slash",
            "color_before": "FFFFFF",
            "color_after": "000000",
        }
        with self.assertRaisesRegex(SyncError, "FACTORY_PROVISION_TOKEN"):
            client.update_color(operation)

        writer = GitHubLabelsClient("token")
        with mock.patch.object(writer, "_request", return_value={}) as request:
            writer.update_color(operation)
        method, path, payload = request.call_args.args
        self.assertEqual(method, "PATCH")
        self.assertIn("state%2Fwith%20slash", path)
        self.assertEqual(payload, {"color": "000000"})

    def test_collect_snapshots_and_execute_apply_are_idempotent(self):
        snapshots = {
            repository: self._canonical_snapshot(repository)
            for repository in REPOSITORIES
        }
        snapshots["pl0n3r/Factory"][0]["color"] = "FFFFFF"

        class FakeClient:
            def __init__(self):
                self.updates = []
            def list_labels(self, repository):
                return [dict(item) for item in snapshots[repository]]
            def update_color(self, operation):
                self.updates.append(dict(operation))
                for item in snapshots[operation["repository"]]:
                    if item["name"] == operation["label"]:
                        item["color"] = operation["color_after"]
                        return
                raise AssertionError("label missing")

        fake = FakeClient()
        collected = collect_snapshots(fake)
        self.assertEqual(set(collected), set(REPOSITORIES))

        with mock.patch("scripts.sync_label_colors.GitHubLabelsClient", return_value=fake):
            plan, residual = execute(apply=True, token="token")
        self.assertEqual(len(plan), 1)
        self.assertEqual(residual, [])
        self.assertEqual(len(fake.updates), 1)

        fake_no_token = FakeClient()
        with mock.patch("scripts.sync_label_colors.GitHubLabelsClient", return_value=fake_no_token):
            with self.assertRaisesRegex(SyncError, "FACTORY_PROVISION_TOKEN"):
                execute(apply=True, token=None)

    def test_execute_dry_run_never_passes_token_to_client(self):
        snapshots = {
            repository: self._canonical_snapshot(repository)
            for repository in REPOSITORIES
        }
        snapshots["pl0n3r/brvtal"][0]["color"] = "FFFFFF"

        class FakeClient:
            def list_labels(self, repository):
                return [dict(item) for item in snapshots[repository]]

        with mock.patch(
            "scripts.sync_label_colors.GitHubLabelsClient",
            return_value=FakeClient(),
        ) as client:
            plan, residual = execute(apply=False, token="must-not-be-used")
        client.assert_called_once_with(None)
        self.assertEqual(len(plan), 1)
        self.assertEqual(residual, [])

    def test_cli_reports_success_and_safe_errors_without_network(self):
        with mock.patch("scripts.sync_label_colors.execute", return_value=([], [])):
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                self.assertEqual(main(["--dry-run"]), 0)
            self.assertIn("0 drifts", stdout.getvalue())

        with mock.patch(
            "scripts.sync_label_colors.execute",
            side_effect=SyncError("fallo controlado"),
        ):
            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                self.assertEqual(main(["--dry-run"]), 2)
            self.assertIn("ERROR: fallo controlado", stderr.getvalue())

        with mock.patch.dict(os.environ, {"FACTORY_PROVISION_TOKEN": "secret"}, clear=False):
            with mock.patch(
                "scripts.sync_label_colors.execute",
                return_value=([], []),
            ) as execute_mock:
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    self.assertEqual(main(["--apply"]), 0)
                execute_mock.assert_called_once_with(apply=True, token="secret")
                self.assertIn("post-apply: 0 drifts", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
