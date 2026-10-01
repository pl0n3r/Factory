"""Pruebas de la cabina de mando sin red."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest.mock import patch
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
        project = cabina.PROYECTOS[0]
        encoded = cabina.base64.b64encode(
            b"<?php return ['version' => '1.2.3'];"
        ).decode()
        with patch.object(cabina, "gh", return_value={"content": encoded}):
            self.assertEqual(cabina.version_main(project, "token"), "1.2.3")
        with patch.object(cabina, "gh", return_value={}):
            self.assertIsNone(cabina.version_main(project, "token"))

        runner = cabina.PROYECTOS[-1]
        self.assertEqual(cabina.salud(runner), {"estado": "na"})
        with patch.object(cabina, "http_json", return_value=(503, None)):
            self.assertEqual(cabina.salud(project)["estado"], "caido")
        with patch.object(
            cabina,
            "http_json",
            return_value=(
                200,
                {
                    "status": "healthy",
                    "deployment": {
                        "version": "1.2.3",
                        "commit": "abc1234",
                    },
                    "schema_up_to_date": True,
                },
            ),
        ):
            health = cabina.salud(project)
        self.assertEqual(health["estado"], "ok")
        self.assertEqual(health["version"], "1.2.3")
        self.assertEqual(health["sha"], "abc1234")
        self.assertIs(health["esquema"], True)

        issue = {"number": 1, "title": "x"}
        pull = {"number": 2, "title": "pr", "pull_request": {}}
        with patch.object(cabina, "gh", return_value=[issue, pull]):
            self.assertEqual(cabina.issues(project, "token", "x"), [issue])
        auto = {"number": 3, "title": "[AUTO] señal"}
        normal = {"number": 4, "title": "normal"}
        with patch.object(cabina, "gh", return_value=[auto, normal, pull]):
            self.assertEqual(cabina.auto_abiertos(project, "token"), [auto])

        with patch.object(
            cabina,
            "gh",
            return_value={"workflow_runs": [{"name": "Deploy", "status": "completed"}]},
        ):
            self.assertIsNone(cabina.ci_main(project, "token"))
        with patch.object(
            cabina,
            "gh",
            side_effect=[{"total_count": 2}, {"total_count": 7}],
        ):
            self.assertEqual(cabina.contar_prs(project, "token", "2026-09-01"), (2, 7))

        with (
            patch.object(cabina, "PROYECTOS", [project]),
            patch.object(cabina, "salud", return_value={"estado": "ok"}),
            patch.object(cabina, "gh", side_effect=cabina.CollectionError("offline")),
        ):
            collected = cabina.recolectar("token")
        self.assertFalse(collected["proyectos"][0]["github_ok"])
        self.assertEqual(collected["proyectos"][0]["incidentes"], [])


        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit): return b'{"ok":true}'

        with patch.object(cabina.urllib.request, "urlopen", return_value=Response()):
            status, payload = cabina.http_json("https://api.github.com/x", "token")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})

        class BadJsonResponse(Response):
            def read(self, _limit): return b"not-json"

        with patch.object(cabina.urllib.request, "urlopen", return_value=BadJsonResponse()):
            self.assertEqual(cabina.http_json("https://example.com")[1], None)

        error = cabina.urllib.error.HTTPError(
            "https://example.com", 404, "not found", {}, None
        )
        with patch.object(cabina.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(cabina.http_json("https://example.com"), (404, None))
        with patch.object(cabina.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertEqual(cabina.http_json("https://example.com"), (0, None))

        with patch.object(cabina, "http_json", return_value=(200, {"ok": True})):
            self.assertEqual(cabina.gh("/repos/x/y", "token"), {"ok": True})
        no_version = cabina.Proyecto(
            "NoVersion", "pl0n3r/NoVersion", "x", None, None, "", "", None
        )
        self.assertIsNone(cabina.version_main(no_version, "token"))
        self.assertIn("Health no verificable", cabina.semaforo(datos({"estado": "desconocido"}))[1])
        self.assertIn("⏳", cabina._render_ci({
            "status": "queued", "url": "https://x", "conclusion": None
        }))
        self.assertIn("❌", cabina._render_ci({
            "status": "completed", "url": "https://x", "conclusion": "failure"
        }))


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
