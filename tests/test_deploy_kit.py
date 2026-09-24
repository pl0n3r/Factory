import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from scripts.deploy_kit import DeployError, adapter_path, run_pipeline

class T(unittest.TestCase):
    def test_order(self):
        calls = []
        run_pipeline(
            origin="https://example.test",
            health_path="/health",
            version="1.2.3",
            sha="a" * 40,
            phase="construccion",
            migration_mode="additive",
            runner=lambda stage: (calls.append(stage) or 0),
            health=Mock(return_value={}),
        )
        self.assertEqual(calls, ["build", "backup", "migrate", "deploy"])

    def test_partial_migration(self):
        calls = []
        with self.assertRaisesRegex(DeployError, "parcialmente"):
            run_pipeline(
                origin="https://example.test",
                health_path="/health",
                version="1.2.3",
                sha="b" * 40,
                phase="construccion",
                migration_mode="additive",
                runner=lambda stage: (calls.append(stage) or (1 if stage == "migrate" else 0)),
                health=Mock(),
            )
        self.assertEqual(calls, ["build", "backup", "migrate"])

    def test_live_gate(self):
        with self.assertRaisesRegex(DeployError, "aprobación"):
            run_pipeline(
                origin="https://example.test",
                health_path="/health",
                version="1.2.3",
                sha="c" * 40,
                phase="live",
                migration_mode="additive",
                runner=lambda stage: 0,
                health=Mock(),
            )

    def test_unknown_stage_cannot_select_an_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(DeployError, "Etapa de deploy inválida"):
                adapter_path("../../bin/sh", root=Path(tmp))

    def test_adapter_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real"
            target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            target.chmod(0o755)
            adapter = root / "ops/factory/build"
            adapter.parent.mkdir(parents=True)
            adapter.symlink_to(target)
            with self.assertRaisesRegex(DeployError, "symlinks"):
                adapter_path("build", root=root)
