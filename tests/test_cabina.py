"""Pruebas de la cabina de mando sin red."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "cabina.py"
spec = importlib.util.spec_from_file_location("cabina", RUTA)
assert spec is not None
assert spec.loader is not None
cabina = importlib.util.module_from_spec(spec)
sys.modules["cabina"] = cabina
spec.loader.exec_module(cabina)


def datos(salud: dict, version_main: str = "0.1.1", incidentes: list | None = None) -> dict:
    return {
        "p": cabina.PROYECTOS[0], "version_main": version_main, "sha_main": "a" * 40,
        "salud": salud, "github_ok": True,
        "ci": {"status": "completed", "conclusion": "success", "url": "https://x", "sha": "aaaaaaa"},
        "incidentes": incidentes or [], "criticos": [], "bloqueados": [], "decisiones": [],
        "prs_abiertos": 2, "prs_semana": 5,
    }


class HealthTests(unittest.TestCase):
    def test_http_200_without_valid_health_is_unknown(self) -> None:
        project = cabina.PROYECTOS[0]
        with patch.object(cabina, "http_json", return_value=(200, None)):
            result = cabina.salud(project)
        self.assertEqual(result["estado"], "desconocido")


class CollectionTests(unittest.TestCase):
    def test_canonical_product_inventory_is_exact(self) -> None:
        self.assertEqual(
            [project.nombre for project in cabina.PROYECTOS],
            ["Condor", "GrindFlow", "BRVTAL", "FactoryRunner"],
        )
        projects = {project.nombre: project for project in cabina.PROYECTOS}
        runner = projects["FactoryRunner"]
        self.assertEqual(runner.repo, "pl0n3r/FactoryRunner")
        self.assertEqual(runner.roadmap, 1)
        self.assertEqual(runner.version_path, "config/version.json")
        self.assertIsNone(runner.sitio)
        self.assertIsNone(runner.health)

    def test_github_failure_is_explicitly_unknown(self) -> None:
        with patch.object(cabina, "http_json", return_value=(429, None)):
            with self.assertRaises(cabina.CollectionError):
                cabina.gh("/repos/pl0n3r/factory", "token")
        d = datos(
            {"estado": "ok", "codigo": 200, "version": "0.1.1"}
        )
        d["github_ok"] = False
        self.assertEqual(
            cabina.semaforo(d),
            ("gris", "Datos GitHub no disponibles"),
        )




    def test_collection_covers_success_and_edge_payloads(self) -> None:
        class Response:
            def __init__(self, status, payload): self.status, self.payload = status, payload
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return self.payload

        with patch.object(cabina.urllib.request, "urlopen", return_value=Response(200, b'{"ok":true}')):
            self.assertEqual(cabina.http_json(cabina.API + "/x", "token"), (200, {"ok": True}))
        with patch.object(cabina.urllib.request, "urlopen", return_value=Response(200, b"not-json")):
            self.assertEqual(cabina.http_json("https://example.com"), (200, None))
        error = cabina.urllib.error.HTTPError("https://x", 429, "rate", {}, None)
        with patch.object(cabina.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(cabina.http_json("https://x"), (429, None))
        with patch.object(cabina.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertEqual(cabina.http_json("https://x"), (0, None))

        project = cabina.PROYECTOS[0]
        encoded = cabina.base64.b64encode(b"<?php return ['version' => '9.8.7'];").decode()
        with patch.object(cabina, "gh", return_value={"content": encoded}):
            self.assertEqual(cabina.version_main(project, "t"), "9.8.7")
        with patch.object(cabina, "gh", return_value=[]):
            self.assertIsNone(cabina.version_main(project, "t"))

        self.assertFalse(cabina._health_payload_valid([]))
        self.assertTrue(cabina._health_payload_valid({"status": "healthy"}))
        runner = cabina.PROYECTOS[-1]
        self.assertEqual(cabina.salud(runner), {"estado": "na"})
        with patch.object(cabina, "http_json", return_value=(503, None)):
            self.assertEqual(cabina.salud(project)["estado"], "caido")
        with patch.object(cabina, "http_json", return_value=(200, {"status": "ok", "deployment": {"version": "1.2.3", "commit": "abc"}, "schema_up_to_date": True})):
            health = cabina.salud(project)
        self.assertEqual((health["estado"], health["version"], health["sha"], health["esquema"]), ("ok", "1.2.3", "abc", True))

        issue_payload = [{"number": 1, "title": "x"}, {"number": 2, "pull_request": {}}]
        with patch.object(cabina, "gh", return_value=issue_payload):
            self.assertEqual([x["number"] for x in cabina.issues(project, "t", "tipo: incidente")], [1])
        with patch.object(cabina, "gh", return_value={"bad": True}):
            self.assertEqual(cabina.auto_abiertos(project, "t"), [])
        with patch.object(cabina, "gh", return_value=[
            {"number": 3, "title": "[AUTO] broken"},
            {"number": 4, "title": "normal"},
            {"number": 5, "title": "[AUTO] pr", "pull_request": {}},
        ]):
            self.assertEqual([x["number"] for x in cabina.auto_abiertos(project, "t")], [3])

        with patch.object(cabina, "gh", return_value={"workflow_runs": [{"name": "Docs", "status": "completed"}]}):
            self.assertIsNone(cabina.ci_main(project, "t"))
        with patch.object(cabina, "gh", side_effect=[{"total_count": 4}, {"total_count": 6}]):
            self.assertEqual(cabina.contar_prs(project, "t", "2026-01-01"), (4, 6))

        with patch.object(cabina, "salud", return_value={"estado": "ok", "version": "1"}),              patch.object(cabina, "gh", return_value={"sha": "a" * 40}),              patch.object(cabina, "issues", return_value=[]),              patch.object(cabina, "auto_abiertos", return_value=[]),              patch.object(cabina, "contar_prs", return_value=(1, 2)),              patch.object(cabina, "version_main", return_value="1"),              patch.object(cabina, "ci_main", return_value={"status": "completed", "conclusion": "success"}):
            collected = cabina.recolectar("t")
        self.assertEqual(len(collected["proyectos"]), len(cabina.PROYECTOS))
        self.assertTrue(all(item["github_ok"] for item in collected["proyectos"]))

        with patch.object(cabina, "salud", return_value={"estado": "na"}),              patch.object(cabina, "gh", side_effect=cabina.CollectionError("down")):
            degraded = cabina.recolectar("t")
        self.assertTrue(all(not item["github_ok"] for item in degraded["proyectos"]))

        self.assertIn("y 1 más", cabina.lista([
            {"html_url": f"https://x/{i}", "number": i, "title": str(i)} for i in range(7)
        ], "vacío"))
        self.assertIn("vacío", cabina.lista([], "vacío"))
        self.assertIn("⏳", cabina._render_ci({"status": "queued", "url": "https://x"}))
        self.assertIn("❌", cabina._render_ci({"status": "completed", "conclusion": "failure", "url": "https://x"}))
        self.assertEqual(cabina._render_ci(None), "—")

        self.assertIsNone(cabina.inicializar_sentry({"SENTRY_DSN": "dsn"}))
        with patch.object(cabina.importlib, "import_module", side_effect=ImportError("missing")):
            self.assertIsNone(
                cabina.inicializar_sentry(
                    {
                        "SENTRY_DSN": "dsn",
                        "SENTRY_RELEASE": "factory@test",
                        "SENTRY_ENVIRONMENT": "test",
                    }
                )
            )
        sdk = MagicMock()
        with patch.object(cabina.importlib, "import_module", return_value=sdk):
            self.assertIs(
                cabina.inicializar_sentry(
                    {
                        "SENTRY_DSN": "dsn",
                        "SENTRY_RELEASE": "factory@test",
                        "SENTRY_ENVIRONMENT": "test",
                    }
                ),
                sdk,
            )
        sdk.init.assert_called_once()

        with (
            patch.object(cabina, "inicializar_sentry", return_value=None),
            patch.object(cabina, "main", return_value=0),
        ):
            self.assertEqual(cabina.ejecutar_con_observabilidad(), 0)
        failing_sdk = MagicMock()
        failing_sdk.capture_exception.side_effect = RuntimeError("sentry down")
        original = ValueError("cabina down")
        with (
            patch.object(cabina, "inicializar_sentry", return_value=failing_sdk),
            patch.object(cabina, "main", side_effect=original),
        ):
            with self.assertRaises(ValueError) as raised:
                cabina.ejecutar_con_observabilidad()
        self.assertIs(raised.exception, original)


class CiTests(unittest.TestCase):
    def test_latest_ci_run_pending_is_not_replaced_by_old_success(self) -> None:
        payload = {
            "workflow_runs": [
                {
                    "name": "CI main",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://new",
                    "head_sha": "b" * 40,
                },
                {
                    "name": "CI main",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://old",
                    "head_sha": "a" * 40,
                },
            ]
        }
        with patch.object(cabina, "gh", return_value=payload):
            result = cabina.ci_main(cabina.PROYECTOS[0], "token")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "in_progress")
        self.assertIsNone(result["conclusion"])
        self.assertEqual(result["url"], "https://new")


class SemaforoTests(unittest.TestCase):
    def test_sitio_caido_es_rojo(self) -> None:
        self.assertEqual(cabina.semaforo(datos({"estado": "caido", "codigo": 500}))[0], "rojo")

    def test_esquema_atrasado_es_amarillo(self) -> None:
        d = datos({"estado": "ok", "codigo": 200, "version": "0.1.1", "esquema": False})
        self.assertEqual(cabina.semaforo(d)[0], "amarillo")

    def test_version_desplegada_distinta_es_amarillo(self) -> None:
        d = datos({"estado": "ok", "codigo": 200, "version": "0.1.0"}, version_main="0.1.1")
        self.assertEqual(cabina.semaforo(d)[0], "amarillo")

    def test_incidente_abierto_es_amarillo(self) -> None:
        d = datos({"estado": "ok", "codigo": 200, "version": "0.1.1"}, incidentes=[{"number": 1}])
        self.assertEqual(cabina.semaforo(d)[0], "amarillo")

    def test_sano_es_verde(self) -> None:
        d = datos({"estado": "ok", "codigo": 200, "version": "0.1.1"})
        self.assertEqual(cabina.semaforo(d), ("verde", "Sano"))

    def test_sin_sitio_es_gris(self) -> None:
        self.assertEqual(cabina.semaforo(datos({"estado": "na"}))[0], "gris")


class RenderTests(unittest.TestCase):
    def test_all_green_title_requires_all_green(self) -> None:
        green = datos(
            {"estado": "ok", "codigo": 200, "version": "0.1.1"}
        )
        yellow = datos(
            {"estado": "ok", "codigo": 200, "version": "0.1.1"},
            incidentes=[{
                "number": 1,
                "title": "Incidente",
                "html_url": "https://github.com/x/1",
            }],
        )
        generated = datetime.now(timezone.utc)
        all_green = cabina.render({
            "proyectos": [green, datos(green["salud"])],
            "generado": generated,
        })
        self.assertIn("Todo en verde", all_green)

        mixed = cabina.render({
            "proyectos": [green, yellow],
            "generado": generated,
        })
        self.assertNotIn("Todo en verde", mixed)
        self.assertIn("estados por revisar", mixed)

    def test_escapa_titulos_y_muestra_decisiones(self) -> None:
        d = datos({"estado": "ok", "codigo": 200, "version": "0.1.1"})
        d["decisiones"] = [{"number": 7, "title": "<script>x</script>", "html_url": "https://github.com/x/7"}]
        pagina = cabina.render({"proyectos": [d], "generado": datetime.now(timezone.utc)})
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", pagina)
        self.assertNotIn("<script>x</script>", pagina)
        self.assertIn("Te toca decidir (1)", pagina)
        self.assertIn("noindex", pagina)


if __name__ == "__main__":
    unittest.main()
