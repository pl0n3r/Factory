import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch
from scripts import deploy_kit
from scripts.deploy_kit import DeployError, adapter_path, run_pipeline, validate_transport_environment

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


    def test_hostinger_transport_configuration(self):
        env = {
            "HOSTINGER_SSH_HOST": "ssh.example.test",
            "HOSTINGER_SSH_USER": "u123456",
            "HOSTINGER_SSH_PORT": "65002",
            "HOSTINGER_RELEASE_ROOT": "/home/u123456/domains/example.test/factory-releases",
            "HOSTINGER_KNOWN_HOSTS": "[ssh.example.test]:65002 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITESTONLYHOSTKEY",
            "DEPLOY_SSH_KEY": "-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
        }
        validate_transport_environment("hostinger-ssh", env)
        for field in tuple(env):
            candidate = dict(env)
            candidate[field] = ""
            with self.subTest(missing=field):
                with self.assertRaisesRegex(DeployError, field):
                    validate_transport_environment("hostinger-ssh", candidate)
        invalid = dict(env)
        invalid["HOSTINGER_KNOWN_HOSTS"] = "other.example.test ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITESTONLYHOSTKEY"
        with self.assertRaisesRegex(DeployError, "no fija el host"):
            validate_transport_environment("hostinger-ssh", invalid)

    def test_transport_is_optional_and_never_logged(self):
        calls = []
        run_pipeline(
            origin="https://example.test",
            health_path="/health",
            version="1.2.3",
            sha="d" * 40,
            phase="construccion",
            migration_mode="none",
            transport="none",
            environment={"DEPLOY_SSH_KEY": "SHOULD-NOT-MATTER"},
            runner=lambda stage: (calls.append(stage) or 0),
            health=Mock(return_value={}),
        )
        self.assertEqual(calls, ["build", "backup", "deploy"])

        secret = "SUPER-SECRET-PRIVATE-KEY-MATERIAL"
        env = {
            "HOSTINGER_SSH_HOST": "ssh.example.test",
            "HOSTINGER_SSH_USER": "u123456",
            "HOSTINGER_SSH_PORT": "not-a-port",
            "HOSTINGER_RELEASE_ROOT": "/home/u123456/releases",
            "HOSTINGER_KNOWN_HOSTS": "[ssh.example.test]:65002 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITESTONLYHOSTKEY",
            "DEPLOY_SSH_KEY": secret,
        }
        stderr = io.StringIO()
        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                os.sys,
                "argv",
                [
                    "deploy_kit.py",
                    "--origin", "https://example.test",
                    "--health-path", "/health",
                    "--version", "1.2.3",
                    "--sha", "e" * 40,
                    "--phase", "construccion",
                    "--migration-mode", "none",
                    "--transport", "hostinger-ssh",
                ],
            ):
                with redirect_stderr(stderr):
                    self.assertEqual(deploy_kit.main(), 1)
        self.assertNotIn(secret, stderr.getvalue())

        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertIn("transport: {required: false, default: 'none', type: string}", workflow)
        self.assertIn("HOSTINGER_KNOWN_HOSTS: ${{ secrets.HOSTINGER_KNOWN_HOSTS }}", workflow)
        self.assertNotIn("StrictHostKeyChecking=no", workflow)
