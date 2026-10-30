"""Factory #1843: pruebas conductuales de retroalimentación, sin red ni PII.

Ejercita producto.feedback con agregados sintéticos; no inspecciona matrices
ni atribuye evidencia live a los contratos locales.
"""
from __future__ import annotations

import json
import math
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from producto import feedback as fb


PROJECT = "example/app"
EPIC = "example/app#17"
START = "2026-09-01T00:00:00Z"
END = "2026-09-08T00:00:00Z"
POST_START = "2026-09-08T00:00:00Z"
POST_END = "2026-09-15T00:00:00Z"


def record(**changes):
    raw = {
        "project": PROJECT,
        "epic": EPIC,
        "metric": "error_rate",
        "surface": "checkout",
        "phase": "baseline",
        "period_start": START,
        "period_end": END,
        "value": 0.10,
        "sample_size": 120,
    }
    raw.update(changes)
    return raw


def marker(metric="error_rate", surface="checkout"):
    body = '<!-- factory-product-metric ' + json.dumps({
        "metric": metric,
        "surface": surface,
        "target_improvement_pct": 10,
    }) + ' -->'
    return fb.parse_epic_marker(body, fb.load_catalog())


def rows():
    catalog = fb.load_catalog()
    before = fb.validate_record(record(), catalog, "baseline")
    after = fb.validate_record(record(
        phase="post-deploy", period_start=POST_START,
        period_end=POST_END, value=0.12,
    ), catalog, "post-deploy")
    return [before, after]


def report(entries, metrics=None):
    return fb.aggregate(
        entries, fb.load_catalog(),
        epic_markers={EPIC: metrics if metrics is not None else marker()},
    )


class CoberturaFactory52Tests(unittest.TestCase):
    def test_contrato_principal(self):
        catalog = fb.load_catalog()
        # L10..L16: invocar el validador real, no cotejar texto normativo.
        raw = record(period_start="2026-09-01T02:00:00+02:00")
        checked = fb.validate_record(raw, catalog, "fixture")
        self.assertEqual(set(checked), fb.RECORD_FIELDS)
        self.assertEqual((checked["project"], checked["epic"]), (PROJECT, EPIC))
        self.assertEqual((checked["metric"], checked["surface"]),
                         ("error_rate", "checkout"))
        self.assertEqual(checked["phase"], "baseline")
        self.assertEqual(checked["period_start"], "2026-09-01T00:00:00+00:00")
        self.assertEqual((checked["value"], checked["sample_size"]), (0.10, 120))
        # L18: esquema cerrado; L20: catálogo realmente completo.
        self.assertEqual({v["family"] for v in catalog.values()}, fb.FAMILIES)
        self.assertEqual(fb.FAMILIES, {"usage", "error", "conversion", "cwv", "seo"})

        # L34 y L36: ventanas contiguas, mínimo 100, umbral adverso >= 5 %.
        observed = rows()
        output = report(observed)
        result = output["results"][0]
        proposal = output["proposals"][0]
        self.assertEqual(output["records"], 2)
        self.assertEqual(output["min_sample_size"], 100)
        self.assertEqual((result["status"], result["delta_pct"]), ("regressed", 20.0))
        self.assertEqual(proposal["epic"], EPIC)
        self.assertEqual(proposal["target_improvement_pct"], 10.0)
        self.assertEqual(proposal["regression_pct"], 20.0)
        self.assertEqual(proposal["impact_score"], round(
            20 * min(4, round(math.log10(121), 4)), 2))
        self.assertIn("Propuestas priorizadas", fb.render_markdown(output))
        threshold = fb.validate_record(record(
            phase="post-deploy", period_start=POST_START, period_end=POST_END,
            value=0.105,
        ), catalog, "threshold")
        exact = report([observed[0], threshold])
        self.assertEqual(exact["results"][0]["status"], "regressed")
        self.assertEqual(exact["proposals"][0]["regression_pct"], 5.0)

        # L46/L47: el CLI real escribe JSON y tablero Markdown en ruta temporal.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "datos"
            data.mkdir()
            (data / "synthetic.jsonl").write_text(
                "\n".join(json.dumps(item) for item in (
                    record(), record(
                        phase="post-deploy", period_start=POST_START,
                        period_end=POST_END, value=0.12,
                    ),
                )) + "\n", encoding="utf-8",
            )
            bodies = {EPIC: '<!-- factory-product-metric ' + json.dumps({
                "metric": "error_rate", "surface": "checkout",
                "target_improvement_pct": 10,
            }) + ' -->'}
            markers = data / "epic-markers.json"
            markers.write_text(json.dumps(bodies), encoding="utf-8")
            artifacts = root / "artifacts"
            with patch.object(fb, "DATA_DIR", data), \
                 patch.object(fb, "EPIC_MARKERS_PATH", markers), \
                 patch.object(fb, "OUTPUT_DIR", artifacts), \
                 patch.object(sys, "argv", ["feedback"]):
                self.assertEqual(fb.main(), 0)
            machine = json.loads((artifacts / "reporte-producto.json").read_text())
            human = (artifacts / "reporte-producto.md").read_text()
            self.assertEqual(machine["proposals"][0]["epic"], EPIC)
            self.assertIn("Resultados por épico", human)
            self.assertIn("checkout", human)

    def test_falla_cerrado(self):
        catalog = fb.load_catalog()
        # L10..L18: identidad, catálogo, slug, fases, tiempo, valor, muestra,
        # campos adicionales y PII simulados deben rechazarse.
        invalid = (
            {"project": "invalid"}, {"epic": "other/app#17"},
            {"epic": "example/app#0"}, {"metric": "nonexistent"},
            {"surface": "checkout/session/abc"}, {"phase": "later"},
            {"period_start": "2026-09-01T00:00:00"},
            {"period_end": "2026-08-31T00:00:00Z"},
            {"value": float("nan")}, {"value": True},
            {"sample_size": 0}, {"sample_size": True},
            {"email": "synthetic@example.invalid"},
            {"url": "https://example.invalid/path"},
            {"ip": "127.0.0.1"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(fb.FeedbackValidationError):
                fb.validate_record(record(**changes), catalog, "synthetic")
        # El marker solo puede corresponder al epic/métrica/superficie observados.
        base = rows()
        for markers in ({}, {EPIC: marker(surface="home")}):
            with self.subTest(markers=markers), self.assertRaises(fb.FeedbackValidationError):
                fb.aggregate(base, catalog, epic_markers=markers)
        with self.assertRaises(fb.FeedbackValidationError):
            fb.parse_epic_marker("<!-- factory-product-metric ??? -->", catalog)
        self.assertIsNone(fb.parse_epic_marker("No marker", catalog))

        # L34-U1: solapamiento y baseline posterior no se aceptan.
        overlapped = fb.validate_record(record(
            phase="post-deploy", period_start="2026-09-07T00:00:00Z",
            period_end=POST_END, value=0.12,
        ), catalog, "overlap")
        with self.assertRaises(fb.FeedbackValidationError):
            report([base[0], overlapped])
        duplicate = fb.validate_record(record(
            period_start="2026-09-07T00:00:00Z",
            period_end="2026-09-09T00:00:00Z",
        ), catalog, "second")
        with self.assertRaises(fb.FeedbackValidationError):
            report([base[0], duplicate, base[1]])

        # L34-U2: CWV p75 jamás promedia percentiles de dos ventanas.
        first = fb.validate_record(record(
            metric="lcp_p75_ms", value=2200, period_end="2026-09-04T00:00:00Z",
        ), catalog, "cwv1")
        second = fb.validate_record(record(
            metric="lcp_p75_ms", value=2100,
            period_start="2026-09-04T00:00:00Z",
        ), catalog, "cwv2")
        third = fb.validate_record(record(
            metric="lcp_p75_ms", value=2400, phase="post-deploy",
            period_start=POST_START, period_end=POST_END,
        ), catalog, "cwv3")
        with self.assertRaises(fb.FeedbackValidationError):
            report([first, second, third], marker("lcp_p75_ms"))

        # L34-U3/U4: sin dos fases, muestra suficiente o baseline no cero,
        # no se inventan regresiones ni propuestas.
        for incomplete in (
            [base[0]],
            [fb.validate_record(record(sample_size=20), catalog, "few"),
             fb.validate_record(record(phase="post-deploy", period_start=POST_START,
                                       period_end=POST_END, value=0.12,
                                       sample_size=20), catalog, "few-post")],
            [fb.validate_record(record(value=0), catalog, "zero"), base[1]],
        ):
            output = report(incomplete)
            self.assertEqual(output["proposals"], [])
            self.assertIsNone(output["results"][0]["delta_pct"])
        # L36: 4% adverso es estable, no cruza umbral 5%.
        mild = fb.validate_record(record(
            phase="post-deploy", period_start=POST_START,
            period_end=POST_END, value=0.104,
        ), catalog, "mild")
        stable = report([base[0], mild])
        self.assertEqual(stable["results"][0]["status"], "stable")
        self.assertEqual(stable["proposals"], [])

    def test_sin_datos_reales(self):
        # Solo agregados sintéticos; prohibir red durante la verificación real.
        with patch.object(socket, "socket", side_effect=AssertionError("red prohibida")):
            catalog = fb.load_catalog()
            checked = fb.validate_record(record(), catalog, "sin red")
            self.assertEqual(checked["epic"], EPIC)
            output = report(rows())
            self.assertEqual(len(output["proposals"]), 1)
            self.assertEqual(fb.required_epics(rows()), [EPIC])
            self.assertEqual(marker()["direction"], "decrease")
            self.assertNotIn("email", output["proposals"][0])
            self.assertNotIn("token", output["proposals"][0])


if __name__ == "__main__":
    unittest.main()
