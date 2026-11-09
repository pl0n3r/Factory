"""Factory #2030: evidencia acotada de 70 cláusulas, sin operación remota."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from producto import feedback as fb
from producto.test_feedback import record, aggregate_rows, CATALOG
from scripts import reusable_permission_compat as permissions
from scripts.release_auto_rollback_plan import plan_rollback
from seguridad.resiliencia import validate_manifest, ValidationError
from seguridad.test_resiliencia import sample_manifest, NOW
from intelligence.risk_compiler import compile_risk
from tests.test_risk_compiler import complete_dna, signals
from tests import test_cobertura_factory_52 as feedback_witness
from tests import test_cobertura_factory_54 as rollback_witness

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-14.md"
# Inventario congelado del issue; nunca derivar expectativas de la salida probada.
CLAUSES = (
    ('docs/resiliencia-fabrica.md:L41-U1', '**Delimitar:** identificar permisos efectivos, repos alcanzables y ventana de exposición sin copiar secretos a Issues o logs.'),
    ('docs/resiliencia-fabrica.md:L42-U1', '**Rotar:** renovar credenciales donde existan y revocar las anteriores'),
    ('docs/resiliencia-fabrica.md:L42-U2', 'los tokens efímeros expiran y no se almacenan como evidencia.'),
    ('docs/resiliencia-fabrica.md:L43-U1', '**Recuperar:** verificar integridad y antigüedad de la copia externa, restaurar en un entorno aislado y comparar refs, tags y artefactos.'),
    ('docs/resiliencia-fabrica.md:L44-U1', '**Verificar:** ejecutar CI, smoke y prueba de rollback antes de retomar despliegues.'),
    ('docs/resiliencia-fabrica.md:L45-U1', '**Aprender:** registrar causa, controles preventivos y resultado en `lecciones/` sin PII ni credenciales.'),
    ('docs/resiliencia-fabrica.md:L62-U1', 'La validación estructural no prueba hechos externos.'),
    ('docs/resiliencia-fabrica.md:L62-U2', 'Si en el futuro aparece una escritura cross-repo, esa capacidad debe introducir una GitHub App dedicada y evidencia verificable antes de habilitarse.'),
    ('docs/retroalimentacion-producto.md:L9-U1', '`project`: `owner/repo`;'),
    ('docs/retroalimentacion-producto.md:L10-U1', '`epic`: `owner/repo#N`, del mismo proyecto;'),
    ('docs/retroalimentacion-producto.md:L11-U1', '`metric`: identificador del catálogo `producto/metricas.json`;'),
    ('docs/retroalimentacion-producto.md:L12-U1', '`surface`: slug de taxonomía de producto, por ejemplo `home` o `checkout`;'),
    ('docs/retroalimentacion-producto.md:L13-U1', '`phase`: `baseline` o `post-deploy`;'),
    ('docs/retroalimentacion-producto.md:L14-U1', '`period_start` / `period_end`: ISO-8601 con zona horaria;'),
    ('docs/retroalimentacion-producto.md:L15-U1', '`value`: agregado numérico;'),
    ('docs/retroalimentacion-producto.md:L16-U1', '`sample_size`: cantidad agregada usada para ponderar.'),
    ('docs/retroalimentacion-producto.md:L18-U1', 'No se permiten campos adicionales.'),
    ('docs/retroalimentacion-producto.md:L18-U2', 'En particular el contrato no tiene nombre, email, teléfono, IP, user/session ID, query string, URL libre, payload de error ni texto de usuario. `surface` e'),
    ('docs/retroalimentacion-producto.md:L20-U1', 'Las métricas iniciales cubren las cinco familias obligatorias: `usage`, `error`, `conversion`, `cwv` y `seo`.'),
    ('docs/retroalimentacion-producto.md:L30-U1', 'El reporte semanal **debe resolver el Issue real de cada épico observado**, parsear ese marker y rechazar telemetría cuya `metric` o `surface` no coincida.'),
    ('docs/retroalimentacion-producto.md:L34-U1', 'Las ventanas dentro de una fase no pueden solaparse y baseline debe terminar antes de post-deploy.'),
    ('docs/retroalimentacion-producto.md:L34-U2', 'Para Core Web Vitals p75 se exige **un único agregado por fase**: Factory no promedia percentiles ya calculados, porque eso no reconstruye el percentil de'),
    ('docs/retroalimentacion-producto.md:L34-U3', 'Por defecto se requieren al menos 100 muestras por fase.'),
    ('docs/retroalimentacion-producto.md:L34-U4', 'Sin ambas fases, con muestra insuficiente o baseline igual a cero, no se calcula una regresión porcentual ni se propone un Issue.'),
    ('docs/retroalimentacion-producto.md:L36-U1', 'Una variación adversa de al menos 5% entra a `proposals`.'),
    ('docs/retroalimentacion-producto.md:L40-U1', 'Sirve únicamente para ordenar evidencia comparable.'),
    ('docs/retroalimentacion-producto.md:L46-U1', '`artifacts/reporte-producto.json`: resultados y propuestas máquina;'),
    ('docs/retroalimentacion-producto.md:L47-U1', '`artifacts/reporte-producto.md`: tablero humano y Job Summary.'),
    ('docs/retroalimentacion-producto.md:L49-U1', 'El workflow primero obtiene la lista validada de épicos presentes en la telemetría, consulta solo esos Issues vía API y construye un mapa efímero de bodies'),
    ('docs/retroalimentacion-producto.md:L49-U2', 'Si un Issue falta, no tiene marker o declara otra métrica/surface, la corrida falla cerrado.'),
    ('docs/reusable-permission-compat.md:L3-U1', '`reusable_permission_compat.py` define un contrato **puro y fail-closed** para comparar el permission envelope máximo que requiere un workflow reusable con'),
    ('docs/reusable-permission-compat.md:L7-U1', 'niveles: `none < read < write`;'),
    ('docs/reusable-permission-compat.md:L8-U1', 'scopes omitidos por el caller equivalen a `none`;'),
    ('docs/reusable-permission-compat.md:L9-U1', 'scopes o niveles desconocidos invalidan el contrato;'),
    ('docs/reusable-permission-compat.md:L10-U1', 'un reusable es compatible solo si, para cada scope requerido, el caller concede un nivel igual o mayor;'),
    ('docs/reusable-permission-compat.md:L11-U1', 'un conjunto de consumidores es compatible solo si **todos** sus callers lo son.'),
    ('docs/reusable-permission-compat.md:L11-U2', 'No existe mayoría, promedio ni excepción implícita.'),
    ('docs/reusable-permission-compat.md:L17-U1', 'Su único trabajo es validar mapas ya extraídos por un adaptador confiable.'),
    ('docs/reusable-permission-compat.md:L19-U1', 'La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato'),
    ('docs/reusable-permission-compat.md:L19-U2', 'cualquier evidencia ausente o inválida debe conservar el bloqueo.'),
    ('docs/reusable-release-rollback.md:L9-U1', 'SHA exacto de Factory que está resolviendo `@v1`;'),
    ('docs/reusable-release-rollback.md:L10-U1', 'tag/release semántica asociada al incidente;'),
    ('docs/reusable-release-rollback.md:L11-U1', 'repositorios y workflows consumidores afectados;'),
    ('docs/reusable-release-rollback.md:L12-U1', 'run IDs cuyo resultado sea `startup_failure`;'),
    ('docs/reusable-release-rollback.md:L13-U1', 'SHA/tag estable previo conocido que sí materializaba jobs en consumidores.'),
    ('docs/reusable-release-rollback.md:L19-U1', 'El objetivo debe ser un SHA/tag Factory previamente conocido como estable para los consumidores afectados.'),
    ('docs/reusable-release-rollback.md:L19-U2', 'No se elige por inferencia ni por “último release verde” si no existe evidencia de consumidor.'),
    ('docs/reusable-release-rollback.md:L23-U1', '`affected_factory_sha=<SHA afectado>`;'),
    ('docs/reusable-release-rollback.md:L24-U1', '`stable_factory_sha=<SHA estable objetivo>`;'),
    ('docs/reusable-release-rollback.md:L25-U1', 'consumidores que justifican el rollback;'),
    ('docs/reusable-release-rollback.md:L26-U1', 'evidencia que demuestra que el SHA estable había materializado jobs.'),
    ('docs/reusable-release-rollback.md:L30-U1', 'Detectar o recomendar rollback **no autoriza** a un agente, workflow o sesión automática a mover `refs/tags/v1`.'),
    ('docs/reusable-release-rollback.md:L32-U1', 'El OWNER debe ejecutar conscientemente la actualización del tag mayor al SHA estable exacto mediante su canal administrativo autorizado.'),
    ('docs/reusable-release-rollback.md:L34-U1', 'La acción administrativa debe equivaler exactamente a mover:'),
    ('docs/reusable-release-rollback.md:L38-U1', 'No se autoriza mover tags semánticos, publicar una release nueva, cambiar otra referencia ni usar un SHA distinto.'),
    ('docs/reusable-release-rollback.md:L42-U1', 'Después de restablecer `v1`, genera un evento nuevo en al menos un consumidor afectado y exige evidencia nueva de que:'),
    ('docs/reusable-release-rollback.md:L44-U1', 'el workflow reutilizable vuelve a **materializar jobs**;'),
    ('docs/reusable-release-rollback.md:L45-U1', 'el run deja de terminar en `startup_failure`;'),
    ('docs/reusable-release-rollback.md:L46-U1', 'el workflow usa el `Factory@v1` que resuelve al SHA estable objetivo.'),
    ('docs/reusable-release-rollback.md:L48-U1', 'Solo pueden reintentarse o regenerarse después de restablecer el canal.'),
    ('docs/reusable-release-rollback.md:L50-U1', 'Si no existe evidencia nueva de consumidor, el incidente permanece abierto/fail-closed.'),
    ('docs/reusable-release-rollback.md:L56-U1', 'SHA afectado;'),
    ('docs/reusable-release-rollback.md:L57-U1', 'SHA estable restaurado;'),
    ('docs/reusable-release-rollback.md:L58-U1', 'repos/workflows afectados;'),
    ('docs/reusable-release-rollback.md:L59-U1', 'run IDs antes y después;'),
    ('docs/reusable-release-rollback.md:L60-U1', 'evidencia de al menos un consumidor recuperado;'),
    ('docs/reusable-release-rollback.md:L61-U1', 'decisión humana/administrativa que movió `v1`.'),
    ('docs/reusable-release-rollback.md:L63-U1', 'Después del rollback, la corrección de fondo debe viajar por un PR separado y una nueva puerta de release.'),
    ('docs/reusable-release-rollback.md:L63-U2', 'Nunca uses el rollback como bypass de compatibilidad reusable↔caller.'),
    ('docs/risk-compiler.md:L12-U1', 'señales operativas;'),
)


def normalized(text):
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def assert_inventory(report):
    found = re.findall(r"^\| `([^`]+:L\d+-U\d+)` \|", report, re.MULTILINE)
    if found != [key for key, _ in CLAUSES]:
        raise ValueError("Inventario incompleto, duplicado o reordenado")
    for line in report.splitlines():
        if line.startswith("| `docs/") and not line.endswith("| NO_VERIFICABLE |"):
            raise ValueError("Promoción sin consolidación")


class VerificacionFactory14Tests(unittest.TestCase):
    def test_inventario_y_anclas(self):
        report = REPORT.read_text(encoding="utf-8")
        assert_inventory(report)
        methods = re.findall(r"\| `(test_\w+)` \|", report)
        self.assertEqual(len(methods), 70)
        self.assertTrue(all(callable(getattr(self, name, None)) for name in methods))
        self.assertEqual(len(CLAUSES), 70)
        self.assertEqual(len(dict(CLAUSES)), 70)
        for key, clause in CLAUSES:
            path, line = key.split(":L")
            number = int(line.split("-")[0])
            actual = (ROOT / path).read_text(encoding="utf-8").splitlines()[number - 1]
            with self.subTest(fila=key):
                self.assertIn(normalized(clause), normalized(actual))
        row = next(line for line in report.splitlines() if line.startswith("| `docs/"))
        for changed in (report.replace(row, "", 1), report + "\n" + row,
                        report.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1)):
            with self.assertRaises(ValueError):
                assert_inventory(changed)

    def test_runbooks_no_equivalen_a_ejecucion(self):
        # Anclas completas, no palabras aisladas: cambiar una prohibición rompe el test.
        for key, clause in CLAUSES:
            if not key.startswith(("docs/resiliencia", "docs/reusable-release")):
                continue
            path = key.split(":L")[0]
            with self.subTest(fila=key):
                self.assertIn(normalized(clause), normalized((ROOT / path).read_text()))
        runbook = (ROOT / "docs/reusable-release-rollback.md").read_text()
        self.assertIn("refs/tags/v1 -> <stable_factory_sha>", runbook)
        self.assertIn("Los runs fallidos previos al rollback **no prueban recuperación**", runbook)

    def test_manifiesto_sin_secretos_ni_prueba_externa(self):
        original = sample_manifest()
        self.assertIsNone(validate_manifest(deepcopy(original), now=NOW))
        for mutate in (
            lambda s: s["cross_repo_write"].update(required_mechanism="github-token:ephemeral"),
            lambda s: s["checks"]["restore_drill"].update(verified_at="2025-01-01T00:00:00Z"),
            lambda s: s["checks"].pop("token_rotation"),
            lambda s: s["execution_mechanisms"].update(token="synthetic-sentinel"),
        ):
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(ValidationError) as error:
                validate_manifest(value, now=NOW)
            self.assertNotIn("synthetic-sentinel", str(error.exception))
        # Aceptar metadatos sintéticos no produce certificado de restore ni hace I/O.
        self.assertEqual(original, sample_manifest())

    def test_feedback_esquema_cerrado(self):
        self.assertEqual(set(fb.validate_record(record(), CATALOG, "fixture")), {
            "project", "epic", "metric", "surface", "phase", "period_start",
            "period_end", "value", "sample_size",
        })
        for field, value in (
            ("project", "no-repo"), ("epic", "other/repo#1"),
            ("metric", "unknown"), ("surface", "path/user/123"), ("phase", "other"),
            ("period_start", "2026-09-01T00:00:00"), ("value", float("inf")),
            ("sample_size", True), ("sample_size", 0),
            *((key, "synthetic") for key in (
                "name", "email", "phone", "ip", "user_id", "session_id",
                "query_string", "url", "error_payload", "user_text",
            )),
        ):
            with self.subTest(field=field), self.assertRaises(fb.FeedbackValidationError):
                fb.validate_record(record(**{field: value}), CATALOG, "fixture")
        self.assertEqual({s["family"] for s in fb.load_catalog().values()},
                         {"usage", "error", "conversion", "cwv", "seo"})

    def test_feedback_muestra_y_umbral_exactos(self):
        def pair(value, count=100):
            return [fb.validate_record(r, CATALOG, "fixture") for r in (
                record(value=0.1, sample_size=count),
                record(phase="post-deploy", value=value, sample_size=count,
                       period_start="2026-09-08T00:00:00Z", period_end="2026-09-15T00:00:00Z"),
            )]
        for value, count, state, proposals in (
            (0.104, 100, "stable", 0), (0.105, 100, "regressed", 1),
            (0.105, 99, "insufficient-data", 0), (0.095, 100, "improved", 0),
        ):
            with self.subTest(value=value, count=count):
                report = aggregate_rows(pair(value, count))
                self.assertEqual(report["results"][0]["status"], state)
                self.assertEqual(len(report["proposals"]), proposals)
        missing = aggregate_rows(pair(0.2)[:1])
        self.assertIsNone(missing["results"][0]["delta_pct"])
        self.assertEqual(missing["proposals"], [])

    def test_feedback_ventanas_markers_y_cli(self):
        # Reutilizar regresiones conductuales reales; ejecutar ambas, sin copiar su lógica.
        self.run_witness(feedback_witness.CoberturaFactory52Tests, "test_contrato_principal")
        self.run_witness(feedback_witness.CoberturaFactory52Tests, "test_falla_cerrado")
        from producto.test_feedback import FeedbackTests
        for method in (
            "test_overlapping_windows_within_phase_fail_closed",
            "test_overlapping_before_after_windows_fail_closed",
            "test_cwv_percentiles_are_not_averaged_across_windows",
            "test_zero_baseline_never_invents_percent_change",
            "test_report_requires_matching_epic_marker_and_includes_target",
            "test_marker_file_requires_exact_observed_epics",
        ):
            self.run_witness(FeedbackTests, method)

    def run_witness(self, case, method):
        result = unittest.TestResult()
        case(method).run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.skipped)
        self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))

    def test_workflow_retirado_no_se_acredita(self):
        self.assertFalse((ROOT / ".github/workflows/feedback-producto.yml").exists())
        report = REPORT.read_text()
        self.assertIn("#1304", report)
        self.assertIn("No hay consulta API ni publicación semanal acreditada", report)

    def test_permisos_tabla_completa_y_unanimidad(self):
        for required, allowed in {"none": {"none", "read", "write"},
                                  "read": {"read", "write"}, "write": {"write"}}.items():
            for granted in ("none", "read", "write"):
                result = permissions.compare_permissions({"contents": required}, {"contents": granted})
                self.assertEqual(result["compatible"], granted in allowed)
        self.assertEqual(permissions.compare_permissions({"actions": "read"}, {})["missing"],
                         [{"scope": "actions", "required": "read", "granted": "none"}])
        callers = {"a": {"contents": "write"}, "b": {"contents": "read"}, "c": {}}
        self.assertFalse(permissions.compare_callers({"contents": "read"}, callers)["compatible"])
        for required, granted in ((None, {}), ({"unknown": "read"}, {}),
                                  ({}, {"contents": "admin"}), ({}, None)):
            self.assertEqual(permissions.compare_permissions(required, granted)["reason"], "invalid_contract")
        self.assertFalse(permissions.compare_callers({}, {})["compatible"])
        from tests.test_reusable_permission_compat import ReusablePermissionCompatTests
        self.run_witness(ReusablePermissionCompatTests, "test_contract_is_pure_deterministic_and_fail_closed")

    def test_rollback_plan_sin_autoridad(self):
        for method in ("test_contrato_principal", "test_falla_cerrado", "test_sin_datos_reales"):
            self.run_witness(rollback_witness.CoberturaFactory54Tests, method)
        result = plan_rollback(rollback_witness.incident())
        self.assertEqual(result["decision"], "HUMAN_GATE_REQUIRED")
        self.assertIs(result["authorizes_tag_move"], False)
        self.assertEqual(result["mutations"], 0)
        self.assertNotIn("recovered", result)

    def test_senal_operativa_eleva_dimension(self):
        task = {"id": "synthetic", "title": "Docs", "change_type": "docs",
                "surfaces": ["docs"], "signals": signals()}
        baseline = compile_risk(project_dna=complete_dna(), task=task)
        task["signals"]["production"] = True
        elevated = compile_risk(project_dna=complete_dna(), task=task)
        self.assertEqual(baseline["dimensions"]["signals"], "low")
        self.assertEqual(elevated["dimensions"]["signals"], "high")
        self.assertIn("task.signals.production", {row["source"] for row in elevated["trace"]})

    def test_mutaciones_conductuales_detectadas(self):
        # Mutantes en memoria: no se modifica ningún archivo productivo.
        for target, attribute, replacement, method in (
            (fb, "REGRESSION_THRESHOLD_PCT", 6.0, "test_feedback_muestra_y_umbral_exactos"),
            (permissions, "compare_callers", lambda *_: {"compatible": True},
             "test_permisos_tabla_completa_y_unanimidad"),
        ):
            with patch.object(target, attribute, replacement):
                result = unittest.TestResult()
                type(self)(method).run(result)
                self.assertTrue(result.failures, method)
                self.assertFalse(result.errors, method)


if __name__ == "__main__":
    unittest.main()
