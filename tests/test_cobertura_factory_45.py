"""Pruebas reales de Sonar Watch y evidencia Sonar para Factory #1836.

Los Issues y respuestas HTTP son simulados. No ejecuta el watcher productivo,
no inspecciona las filas de matrices ni modifica políticas de Sonar.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "test_sonar_watch.py"
SPEC = importlib.util.spec_from_file_location("_factory45_sonar_support", SUPPORT)
assert SPEC is not None and SPEC.loader is not None
support = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(support)
watch = support.sonar_watch

WATCH = "docs/quality-sonar-watch.md:"
SONAR = "docs/quality-sonar.md:"
OFFLINE = frozenset({
    WATCH + "L30-U1", WATCH + "L32-U1", WATCH + "L32-U2",
    WATCH + "L42-U1", WATCH + "L42-U2",
    WATCH + "L52-U1", WATCH + "L52-U2",
    WATCH + "L54-U1", WATCH + "L54-U2", WATCH + "L54-U3",
    WATCH + "L54-U4", WATCH + "L54-U5", WATCH + "L56-U1",
    WATCH + "L60-U1", WATCH + "L60-U2", WATCH + "L64-U1",
    SONAR + "L10-U1",
})
POLICY = {
    WATCH + "L3-U3": "ejecuciones expresamente autorizadas son una regla operativa, no un permiso inferible del motor",
    WATCH + "L46-U1": "la existencia del entrypoint no autoriza activarlo; autorización externa",
    WATCH + "L48-U1": "los CI de PR no sustituyen el scheduler retirado: límite operativo/documental",
}


def run_existing(testcase, *methods):
    """Regresiones previas que llaman al motor real con dobles sin red."""
    suite = unittest.TestSuite(
        unittest.TestLoader().loadTestsFromName(
            f"SonarWatchTests.{name}", module=support
        )
        for name in methods
    )
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful() or result.testsRun != len(methods):
        raise AssertionError(
            f"Regresiones Sonar incorrectas: {result.testsRun} "
            f"{result.failures!r} {result.errors!r}"
        )
    testcase.assertEqual(result.testsRun, len(methods))


class CoberturaFactory45Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada unidad offline ejerce código funcional con fixtures."""
        done = set()
        self.assertEqual((len(OFFLINE), len(POLICY)), (17, 3))
        self.assertEqual(len(OFFLINE | POLICY.keys()), 20)
        with mock.patch.object(
            watch, "urlopen", side_effect=AssertionError("red prohibida")
        ):
            configs = watch.load_runtime_config()
            self.assertEqual(len(configs), 6)
            api = watch.SonarApi(token="")
            private = [copy.deepcopy(configs[0])]
            private[0]["contract"]["sonar"]["expected_visibility"] = "private"
            api.get = lambda *_args: self.fail("no debe consultar red")
            with self.assertRaises(watch.SonarWatchError):
                api.preflight_visibility(private)
            done.add(WATCH + "L30-U1")

            public = [copy.deepcopy(configs[0])]
            api.get = lambda *_args: {}
            with self.assertRaises(watch.SonarWatchError):
                api.preflight_visibility(public)
            done.add(WATCH + "L32-U1")

            raw = support.snapshot()
            raw["visibility"] = "private"
            issues = support.FakeIssues()
            support.sync(raw, issues)
            visibility = issues.find(watch.issue_marker("factory", "visibility"))
            self.assertEqual(len(visibility), 1)
            self.assertEqual(visibility[0]["state"], "open")
            self.assertIn("FAIL", visibility[0]["body"])
            done.add(WATCH + "L32-U2")

            for value, expected in (("true", "automatic"), ("false", "ci")):
                payload = {
                    "settings": [
                        {"key": "sonar.autoscan.enabled", "value": value}
                    ]
                }
                self.assertEqual(
                    watch.SonarApi.analysis_method_from_settings(payload),
                    expected,
                )
            done.add(WATCH + "L42-U1")

            invalid_settings = (
                {}, {"settings": []},
                {"settings": [
                    {"key": "sonar.autoscan.enabled", "value": "true"},
                    {"key": "sonar.autoscan.enabled", "value": "false"},
                ]},
                {"settings": [{"key": "other", "value": "true"}]},
                {"settings": [
                    {"key": "sonar.autoscan.enabled", "value": "yes"}
                ]},
            )
            for payload in invalid_settings:
                with self.subTest(settings=payload):
                    with self.assertRaises(watch.SonarWatchError):
                        watch.SonarApi.analysis_method_from_settings(payload)
            done.add(WATCH + "L42-U2")

            failing = support.snapshot()
            failing["analysis"]["coverage_available"] = False
            issues = support.FakeIssues()
            support.sync(failing, issues)
            marker = watch.issue_marker("factory", "coverage")
            self.assertEqual(issues.find(marker)[0]["state"], "open")
            support.sync(support.snapshot(), issues)
            self.assertEqual(issues.find(marker)[0]["state"], "closed")
            self.assertIn(
                "estado: completado", issues.find(marker)[0]["labels"]
            )
            done.add(WATCH + "L52-U1")
            done.add(WATCH + "L54-U3")

            run_existing(
                self,
                "test_not_applicable_closes_auto_issue_once_and_preserves_required_failures",
            )
            done.add(WATCH + "L52-U2")
            done.add(WATCH + "L54-U4")

            issues = support.FakeIssues()
            failing = support.snapshot()
            failing["visibility"] = "private"
            support.sync(failing, issues)
            item = issues.find(watch.issue_marker("factory", "visibility"))[0]
            self.assertEqual(
                item["labels"],
                ["tipo: calidad", "prioridad: media", "estado: bloqueado"],
            )
            done.add(WATCH + "L54-U1")
            self.assertIn("Motivo del bloqueo:", item["body"])
            self.assertIn("Condición de desbloqueo:", item["body"])
            self.assertIn("PASS/CURRENT", item["body"])
            done.add(WATCH + "L54-U2")

            custom = {
                "labels": [
                    "tipo: calidad", "prioridad: media",
                    "estado: bloqueado", "equipo: observadores"
                ]
            }
            self.assertEqual(
                watch._auto_issue_labels(custom, state="closed"),
                ["tipo: calidad", "prioridad: media",
                 "estado: completado", "equipo: observadores"],
            )
            with self.assertRaises(watch.SonarWatchError):
                watch._auto_issue_labels(
                    {"labels": ["estado: reservado"]}, state="open"
                )
            done.add(WATCH + "L54-U5")

            self.assertIn(
                "https://sonarcloud.io/project/overview?id=factory",
                item["body"],
            )
            self.assertIn("Freshness:", item["body"])
            self.assertIn("sonar:factory:snapshot:", item["body"])
            done.add(WATCH + "L56-U1")

            ci_missing = support.snapshot()
            ci_missing["analysis"]["method"] = "ci"
            ci_missing["analysis"]["coverage_available"] = False
            issues = support.FakeIssues()
            support.sync(ci_missing, issues)
            self.assertEqual(
                issues.find(watch.issue_marker("factory", "coverage"))[0]["state"],
                "open",
            )
            done.add(WATCH + "L60-U1")

            wrong_method = support.snapshot()
            wrong_method["analysis"]["method"] = "automatic"
            issues = support.FakeIssues()
            support.sync(wrong_method, issues)
            mismatch = issues.find(
                watch.issue_marker("factory", "analysis_method")
            )
            self.assertEqual(len(mismatch), 1)
            self.assertIn("FAIL", mismatch[0]["body"])
            done.add(WATCH + "L60-U2")

            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "invalid-config.json"
                path.write_text(
                    json.dumps({"version": 1, "provenance": {}, "projects": []}),
                    encoding="utf-8",
                )
                with self.assertRaises(watch.SonarWatchError):
                    watch.load_runtime_config(path)
            done.add(WATCH + "L64-U1")

            normalized = watch._snapshot_from_api(
                "factory", support.NOW,
                {"projectStatus": {"status": "OK", "conditions": []}},
                {"analyses": [{"date": support.NOW}]},
                {"current": {"status": "SUCCESS", "errorMessage": None}},
                {"component": {"measures": [{"metric": "coverage"}]}},
                {"settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]},
                {"component": {"visibility": "public"}},
                {"issues": []}, {"hotspots": []},
            )
            self.assertEqual(
                normalized["analysis"],
                {"analyzed_at": support.NOW,
                 "method": "ci", "coverage_available": True},
            )
            self.assertEqual(normalized["project"], "factory")
            done.add(SONAR + "L10-U1")

        self.assertEqual(done, OFFLINE)

    def test_falla_cerrado(self):
        """AC-02: sin configuración, autorización o evidencia válida no actúa."""
        with mock.patch.object(
            watch, "urlopen", side_effect=AssertionError("red prohibida")
        ):
            api = watch.SonarApi(token="")
            with self.assertRaises(watch.SonarWatchError):
                api.http.request(
                    "/api/settings/values",
                    method="POST", payload={"change": True},
                )
            for bad in (
                {"settings": [{"key": "sonar.autoscan.enabled"}]},
                {"settings": [{"key": "sonar.autoscan.enabled",
                               "value": "TRUE"}]},
                {"settings": None},
            ):
                with self.subTest(bad=bad):
                    with self.assertRaises(watch.SonarWatchError):
                        watch.SonarApi.analysis_method_from_settings(bad)

            with self.assertRaises(watch.SonarWatchError):
                watch._origin_url("bad?secret=1")
            with self.assertRaises(watch.SonarWatchError):
                watch._auto_issue_labels(
                    {"labels": ["tipo: incidente"]}, state="closed"
                )
            failing = support.snapshot()
            failing["visibility"] = "private"
            with self.assertRaises(watch.SonarWatchError):
                watch.sync_project(
                    contract=support.contract(),
                    snapshot=failing,
                    observed_at=support.NOW,
                    project_ref="pl0n3r/Factory",
                    origin_ref="sonar:factory",
                    origin_url="https://untrusted.invalid/?token=x",
                    issues=support.FakeIssues(),
                )
            run_existing(
                self,
                "test_unrecoverable_large_page_or_paging_drift_fails_closed",
                "test_sonar_rejects_incomplete_and_malformed_page_without_fake_green",
                "test_retries_are_idempotent_under_duplicate_observation",
            )

    def test_sin_datos_reales(self):
        """AC-03: fixtures, sin tokens, secretos, PII o escrituras remotas."""
        self.assertEqual(watch.SonarApi(token="").token, "")
        marker = watch.issue_marker("factory", "coverage")
        self.assertIn("factory-sonar-watch", marker)
        self.assertNotIn("token", marker.lower())
        with mock.patch.object(
            watch, "urlopen", side_effect=AssertionError("red prohibida")
        ):
            issues = support.FakeIssues()
            failing = support.snapshot()
            failing["analysis"]["coverage_available"] = False
            operations = support.sync(failing, issues)
            self.assertTrue(operations)
            self.assertTrue(issues.rows)
            self.assertEqual(
                set(issues.rows[0]["labels"]),
                {"tipo: calidad", "prioridad: media", "estado: bloqueado"},
            )
        self.assertEqual((len(OFFLINE), len(POLICY)), (17, 3))


if __name__ == "__main__":
    unittest.main()
