import io
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from scripts import preview_kit as preview
from scripts.deploy_kit import DeployError
from scripts.preview_kit import PreviewError, run_preview


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

    def test_adapter_and_cli_cover_fail_closed_edges(self):
        with self.assertRaises(PreviewError):
            preview._adapter_path("unknown")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = preview.PREVIEW_ADAPTERS["preview-health"]
            adapter = root / relative
            adapter.parent.mkdir(parents=True)
            adapter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            adapter.chmod(0o700)
            self.assertEqual(
                preview._adapter_path("preview-health", root=root),
                adapter.resolve(),
            )
            adapter.unlink()
            outside = root.parent / "outside-preview-adapter"
            outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            try:
                adapter.symlink_to(outside)
            except OSError:
                pass
            else:
                with self.assertRaises(PreviewError):
                    preview._adapter_path("preview-health", root=root)

        with (
            patch.object(preview, "_adapter_path", return_value=Path("/tmp/fake")),
            patch.object(
                preview.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=7),
            ) as run,
        ):
            self.assertEqual(preview.preview_stage_runner("preview-health"), 7)
        run.assert_called_once()

        with self.assertRaises(PreviewError):
            run_preview(
                version="bad",
                sha="x",
                migration_mode="none",
                runner=lambda _stage: 0,
                verification_runner=lambda _stage: 0,
            )
        with self.assertRaises(PreviewError):
            run_preview(
                version="1.2.3",
                sha="a" * 40,
                migration_mode="destructive",
                runner=lambda _stage: 0,
                verification_runner=lambda _stage: 0,
            )
        with patch.object(
            preview.tempfile,
            "TemporaryDirectory",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(PreviewError):
                run_preview(
                    version="1.2.3",
                    sha="a" * 40,
                    migration_mode="none",
                    runner=lambda _stage: 0,
                    verification_runner=lambda _stage: 0,
                )

        with (
            patch.object(
                preview.sys,
                "argv",
                [
                    "preview_kit.py",
                    "--version",
                    "1.2.3",
                    "--sha",
                    "a" * 40,
                    "--migration-mode",
                    "none",
                ],
            ),
            patch.object(preview, "run_preview"),
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(preview.main(), 0)
        self.assertIn("Preview sintético validado", output.getvalue())

        with (
            patch.object(
                preview.sys,
                "argv",
                [
                    "preview_kit.py",
                    "--version",
                    "1.2.3",
                    "--sha",
                    "a" * 40,
                ],
            ),
            patch.object(preview, "run_preview", side_effect=PreviewError("bad")),
            redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(preview.main(), 1)
        self.assertIn("::error::bad", error.getvalue())

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


if __name__ == "__main__":
    unittest.main()
