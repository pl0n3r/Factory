import io
import os
import stat
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from scripts.deploy_kit import DeployError
from scripts import preview_kit as pk
from scripts.preview_kit import (
    PreviewError,
    _adapter_path,
    main,
    preview_stage_runner,
    run_preview,
)


class PreviewKitTests(unittest.TestCase):
    def test_preview_reuses_deploy_pipeline_then_health_smoke_e2e(self):
        events = []

        def base(stage):
            events.append(stage)
            return 0

        def verify(stage):
            events.append(stage)
            return 0

        run_preview(
            version="1.2.3",
            sha="a" * 40,
            migration_mode="additive",
            runner=base,
            verification_runner=verify,
        )
        self.assertEqual(
            events,
            [
                "build",
                "backup",
                "migrate",
                "deploy",
                "preview-health",
                "preview-smoke",
                "preview-e2e",
            ],
        )

    def test_preview_rejects_production_credentials(self):
        with patch.dict(
            os.environ,
            {"DEPLOY_TOKEN": "never-print-this"},
            clear=False,
        ):
            with self.assertRaisesRegex(
                PreviewError,
                "DEPLOY_TOKEN",
            ) as captured:
                run_preview(
                    version="1.2.3",
                    sha="b" * 40,
                    migration_mode="none",
                    runner=lambda _stage: 0,
                    verification_runner=lambda _stage: 0,
                )
        self.assertNotIn(
            "never-print-this",
            str(captured.exception),
        )
        with self.assertRaisesRegex(PreviewError, "construccion"):
            run_preview(
                version="1.2.3",
                sha="b" * 40,
                migration_mode="none",
                phase="live",
                runner=lambda _stage: 0,
                verification_runner=lambda _stage: 0,
            )

    def test_preview_environment_is_synthetic_and_restored(self):
        observed = []
        before = dict(os.environ)

        def capture(stage):
            root = Path(os.environ["FACTORY_PREVIEW_ROOT"])
            observed.append(
                (
                    stage,
                    os.environ.get("FACTORY_PREVIEW"),
                    os.environ.get("FACTORY_SYNTHETIC_DATA"),
                    root.exists(),
                    "ACTIONS_RUNTIME_TOKEN" in os.environ,
                    Path(os.environ["HOME"]).parent == root,
                    Path(os.environ["RUNNER_TEMP"]).parent == root,
                )
            )
            return 0

        with patch.dict(
            os.environ,
            {"ACTIONS_RUNTIME_TOKEN": "runner-only"},
            clear=False,
        ):
            expected_after = dict(os.environ)
            run_preview(
                version="1.2.3",
                sha="c" * 40,
                migration_mode="none",
                runner=capture,
                verification_runner=capture,
            )
            self.assertEqual(dict(os.environ), expected_after)

        self.assertEqual(dict(os.environ), before)
        self.assertTrue(observed)
        for (
            _,
            preview,
            synthetic,
            root_exists,
            runtime_token,
            home_is_private,
            temp_is_private,
        ) in observed:
            self.assertEqual(preview, "1")
            self.assertEqual(synthetic, "1")
            self.assertTrue(root_exists)
            self.assertFalse(runtime_token)
            self.assertTrue(home_is_private)
            self.assertTrue(temp_is_private)

    def test_post_deploy_failure_fails_preview(self):
        events = []

        def base(stage):
            events.append(stage)
            return 0

        def smoke_failure(stage):
            events.append(stage)
            return 7 if stage == "preview-smoke" else 0

        with self.assertRaises(DeployError):
            run_preview(
                version="1.2.3",
                sha="d" * 40,
                migration_mode="none",
                runner=base,
                verification_runner=smoke_failure,
            )
        self.assertIn("preview-smoke", events)
        self.assertNotIn("preview-e2e", events)

        rollback_events = []

        def base_with_rollback(stage):
            rollback_events.append(stage)
            return 0

        def health_failure(stage):
            rollback_events.append(stage)
            return 9 if stage == "preview-health" else 0

        with self.assertRaises(DeployError):
            run_preview(
                version="1.2.3",
                sha="e" * 40,
                migration_mode="none",
                runner=base_with_rollback,
                verification_runner=health_failure,
            )
        self.assertEqual(
            rollback_events,
            [
                "build",
                "backup",
                "deploy",
                "preview-health",
                "rollback",
            ],
        )

    def test_adapter_and_main_error_paths_are_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = root / "ops" / "factory" / "preview-health"
            adapter.parent.mkdir(parents=True)
            adapter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            adapter.chmod(0o700)
            self.assertEqual(_adapter_path("preview-health", root=root), adapter.resolve())

            with self.assertRaises(PreviewError):
                _adapter_path("unknown", root=root)

            missing = root / "ops" / "factory" / "preview-smoke"
            with self.assertRaises(PreviewError):
                _adapter_path("preview-smoke", root=root)

            outside = root.parent / (root.name + "-outside")
            outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            outside.chmod(0o700)
            symlink = root / "ops" / "factory" / "preview-e2e"
            symlink.symlink_to(outside)
            try:
                with self.assertRaises(PreviewError):
                    _adapter_path("preview-e2e", root=root)
            finally:
                outside.unlink(missing_ok=True)

        with patch(
            "scripts.preview_kit._adapter_path",
            return_value=Path("/tmp/preview-health"),
        ), patch(
            "scripts.preview_kit.subprocess.run",
            return_value=SimpleNamespace(returncode=9),
        ) as execute:
            self.assertEqual(preview_stage_runner("preview-health"), 9)
        execute.assert_called_once()

        for version, sha, migration_mode in (
            ("1.2", "a" * 40, "none"),
            ("1.2.3", "bad", "none"),
            ("1.2.3", "a" * 40, "destructive"),
        ):
            with self.subTest(version=version, migration_mode=migration_mode):
                with self.assertRaises(PreviewError):
                    run_preview(
                        version=version,
                        sha=sha,
                        migration_mode=migration_mode,
                        runner=lambda _stage: 0,
                        verification_runner=lambda _stage: 0,
                    )

        with patch(
            "scripts.preview_kit.tempfile.TemporaryDirectory",
            side_effect=OSError("disk unavailable"),
        ):
            with self.assertRaisesRegex(PreviewError, "crear o limpiar"):
                run_preview(
                    version="1.2.3",
                    sha="a" * 40,
                    migration_mode="none",
                    runner=lambda _stage: 0,
                    verification_runner=lambda _stage: 0,
                )

        with patch.object(sys, "argv", [
            "preview_kit.py",
            "--version",
            "1.2.3",
            "--sha",
            "a" * 40,
            "--migration-mode",
            "none",
        ]), patch("scripts.preview_kit.run_preview") as preview, patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as stdout:
            self.assertEqual(main(), 0)
        preview.assert_called_once()
        self.assertIn("validado", stdout.getvalue())

        with patch.object(sys, "argv", [
            "preview_kit.py",
            "--version",
            "1.2.3",
            "--sha",
            "a" * 40,
        ]), patch(
            "scripts.preview_kit.run_preview",
            side_effect=PreviewError("boom"),
        ), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main(), 1)
        self.assertIn("boom", stderr.getvalue())


    def test_adapter_release_environment_and_cli_edges(self):
        with self.assertRaisesRegex(PreviewError, "Etapa"):
            pk._adapter_path("missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = root / pk.PREVIEW_ADAPTERS["preview-health"]
            adapter.parent.mkdir(parents=True)
            adapter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            adapter.chmod(adapter.stat().st_mode | stat.S_IXUSR)
            self.assertEqual(pk._adapter_path("preview-health", root=root), adapter.resolve())

            adapter.unlink()
            adapter.write_text("echo x\n", encoding="utf-8")
            with self.assertRaisesRegex(PreviewError, "ejecutable"):
                pk._adapter_path("preview-health", root=root)

            adapter.unlink()
            outside = root / "outside"
            outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            outside.chmod(outside.stat().st_mode | stat.S_IXUSR)
            adapter.symlink_to(outside)
            with self.assertRaisesRegex(PreviewError, "symlinks"):
                pk._adapter_path("preview-health", root=root)

        for version, sha in (("01.2.3", "a" * 40), ("1.2.3", "bad")):
            with self.subTest(version=version, sha=sha):
                with self.assertRaisesRegex(PreviewError, "Versión o SHA"):
                    pk._validate_release(version, sha)

        safe = pk._safe_environment(
            {"PATH": "/bin", "IGNORED": "x"},
            preview_root="/tmp/preview-x",
            version="1.2.3",
            sha="a" * 40,
            migration_mode="additive",
        )
        self.assertEqual(safe["PATH"], "/bin")
        self.assertNotIn("IGNORED", safe)
        self.assertEqual(safe["FACTORY_REQUIRE_SCHEMA"], "1")

        with self.assertRaisesRegex(PreviewError, "credenciales prohibidas"):
            pk._safe_environment(
                {"DATABASE_URL": "secret"},
                preview_root="/tmp/x",
                version="1.2.3",
                sha="a" * 40,
                migration_mode="none",
            )

        before = dict(os.environ)
        with tempfile.TemporaryDirectory() as tmp:
            with pk.preview_environment(
                preview_root=tmp,
                version="1.2.3",
                sha="a" * 40,
                migration_mode="none",
            ):
                self.assertEqual(os.environ["FACTORY_PREVIEW"], "1")
                for name in ("home", "tmp", "composer", "cache", "config"):
                    self.assertTrue((Path(tmp) / name).is_dir())
        self.assertEqual(dict(os.environ), before)

        with self.assertRaisesRegex(PreviewError, "migration_mode"):
            run_preview(
                version="1.2.3",
                sha="a" * 40,
                migration_mode="destructive",
                runner=lambda _: 0,
                verification_runner=lambda _: 0,
            )

        with patch.object(pk.tempfile, "TemporaryDirectory", side_effect=OSError("disk")):
            with self.assertRaisesRegex(PreviewError, "crear o limpiar"):
                run_preview(
                    version="1.2.3",
                    sha="a" * 40,
                    migration_mode="none",
                    runner=lambda _: 0,
                    verification_runner=lambda _: 0,
                )

        with patch.object(sys, "argv", ["preview_kit.py", "--version", "1.2.3", "--sha", "a" * 40]),              patch.object(pk, "run_preview", return_value=None),              patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(pk.main(), 0)
            self.assertIn("validado", stdout.getvalue())
        with patch.object(sys, "argv", ["preview_kit.py", "--version", "1.2.3", "--sha", "a" * 40]),              patch.object(pk, "run_preview", side_effect=PreviewError("bad")),              patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(pk.main(), 1)
            self.assertIn("::error::bad", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
