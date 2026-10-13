"""Regresiones de observabilidad Sentry para la cabina."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
RUTA = ROOT / "scripts" / "cabina.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "cabina.yml"

spec = importlib.util.spec_from_file_location("cabina_sentry_test", RUTA)
assert spec is not None
assert spec.loader is not None
cabina = importlib.util.module_from_spec(spec)
sys.modules["cabina_sentry_test"] = cabina
spec.loader.exec_module(cabina)


class SentryTests(unittest.TestCase):
    def test_without_dsn_is_noop_without_import(self) -> None:
        with patch.object(cabina.importlib, "import_module") as importer:
            self.assertIsNone(cabina.inicializar_sentry({}))
        importer.assert_not_called()

    def test_init_uses_privacy_safe_explicit_options(self) -> None:
        sdk = MagicMock()
        dsn = str(id(self))
        env = {
            "SENTRY_DSN": dsn,
            "SENTRY_RELEASE": "factory@abc123",
            "SENTRY_ENVIRONMENT": "github-actions",
        }
        with patch.object(cabina.importlib, "import_module", return_value=sdk):
            result = cabina.inicializar_sentry(env)

        self.assertIs(result, sdk)
        sdk.init.assert_called_once_with(
            dsn=env["SENTRY_DSN"],
            release="factory@abc123",
            environment="github-actions",
            send_default_pii=False,
            include_local_variables=False,
            include_source_context=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            traces_sample_rate=0.0,
            profiles_sample_rate=0.0,
            enable_logs=False,
            default_integrations=False,
            auto_enabling_integrations=False,
        )

    def test_exception_is_captured_flushed_and_reraised(self) -> None:
        sdk = MagicMock()
        original = RuntimeError("fallo original")
        with (
            patch.object(cabina, "inicializar_sentry", return_value=sdk),
            patch.object(cabina, "main", side_effect=original),
        ):
            with self.assertRaises(RuntimeError) as raised:
                cabina.ejecutar_con_observabilidad()

        self.assertIs(raised.exception, original)
        sdk.capture_exception.assert_called_once_with(original)
        sdk.flush.assert_called_once_with(timeout=2.0)

    def test_sentry_failure_does_not_replace_original_exception(self) -> None:
        sdk = MagicMock()
        sdk.capture_exception.side_effect = RuntimeError("sentry no disponible")
        original = ValueError("fallo de cabina")
        with (
            patch.object(cabina, "inicializar_sentry", return_value=sdk),
            patch.object(cabina, "main", side_effect=original),
        ):
            with self.assertRaises(ValueError) as raised:
                cabina.ejecutar_con_observabilidad()

        self.assertIs(raised.exception, original)

    def test_init_failure_degrades_to_noop(self) -> None:
        sdk = MagicMock()
        sdk.init.side_effect = RuntimeError("init falló")
        dsn = str(id(self))
        env = {
            "SENTRY_DSN": dsn,
            "SENTRY_RELEASE": "factory@abc123",
            "SENTRY_ENVIRONMENT": "github-actions",
        }
        with patch.object(cabina.importlib, "import_module", return_value=sdk):
            self.assertIsNone(cabina.inicializar_sentry(env))


class WorkflowSentryContractTests(unittest.TestCase):
    def test_offline_engine_survives_without_actions_secret_or_scheduler(self):
        self.assertFalse(WORKFLOW_PATH.exists())
        source = RUTA.read_text(encoding="utf-8")
        self.assertIn("inicializar_sentry", source)
        self.assertIn("ejecutar_con_observabilidad", source)
        self.assertIn("send_default_pii", source)
        self.assertIn("SENTRY_DSN", source)

if __name__ == "__main__":
    unittest.main()
