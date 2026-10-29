"""#1683: brechas de producto, contrato sintético sin evidencia live."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import tempfile
import unittest

from producto.feedback import (
    FAMILIES, RECORD_FIELDS, FeedbackValidationError, aggregate, load_catalog,
    load_epic_markers, parse_epic_marker, render_markdown, required_epics,
    validate_record,
)

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = "docs/retroalimentacion-producto.md"
MATRIX_PATH = "docs/matriz-cobertura.md"
SOURCE_PATH = "producto/feedback.py"
IDS = tuple(DOC_PATH + ":" + clause for clause in (
    "L15-U1", "L16-U1", "L18-U1", "L18-U2", "L20-U1",
    "L30-U1", "L34-U1", "L34-U2", "L34-U3", "L34-U4",
    "L36-U1", "L40-U1", "L46-U1", "L47-U1", "L49-U1", "L49-U2",
))
# La publicación en Actions y la consulta a Issues reales exigen recibos externos.
EXTERNAL = frozenset(IDS[i] for i in (12, 13, 14))
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
EPIC = "example/factory#123"
PROJ = "example/factory"
BODY = ('<!-- factory-product-metric '
        '{"metric":"error_rate","surface":"home",'
        '"target_improvement_pct":10} -->')


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, str) or not raw:
        raise ValueError("UNKNOWN: matriz no disponible")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        parts = tuple(s.strip() for s in re.split(r"(?<!\\)\|",
                      line.strip().strip("|")))
        key = parts[0].strip(" \x60")
        if key not in IDS:
            continue
        if (key in found or len(parts) != 5
                or parts[2] != "NO_VERIFICABLE"
                or "No se confirmó" not in parts[3]
                or not all(parts[:4])):
            raise ValueError("UNKNOWN: fila incompleta, duplicada o promovida")
        found[key] = parts
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: faltan brechas")
    return found


def fixture(**change) -> dict:
    record = {
        "project": PROJ, "epic": EPIC, "metric": "error_rate",
        "surface": "home", "phase": "baseline",
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-09-08T00:00:00Z",
        "value": 0.2, "sample_size": 200,
    }
    return {**record, **change}


def normalized(catalog: dict, **change) -> dict:
    return validate_record(fixture(**change), catalog, "sintético")


def rejects(catalog: dict, **change) -> bool:
    try:
        normalized(catalog, **change)
    except (FeedbackValidationError, TypeError, ValueError):
        return True
    return False


def marker(catalog: dict) -> dict:
    return parse_epic_marker(BODY, catalog)


def compare(catalog: dict, baseline=0.2, post=0.25,
            baseline_samples=200, post_samples=200, extra=()):
    first = normalized(catalog, value=baseline, sample_size=baseline_samples)
    second = normalized(
        catalog, phase="post-deploy",
        period_start="2026-09-09T00:00:00Z",
        period_end="2026-09-16T00:00:00Z",
        value=post, sample_size=post_samples,
    )
    return aggregate([first, second, *extra], catalog,
                     epic_markers={EPIC: marker(catalog)})


def fails(fn) -> bool:
    try:
        fn()
    except (FeedbackValidationError, TypeError, ValueError):
        return True
    return False


def evidence(catalog: dict, doc: str, source: str) -> dict[str, bool]:
    result = {}
    valid = normalized(catalog)
    result[IDS[0]] = (
        isinstance(valid["value"], float)
        and rejects(catalog, value=float("nan"))
        and rejects(catalog, value=True)
        and rejects(catalog, value=-0.1)
        and "agregado numérico" in doc
    )
    result[IDS[1]] = (
        valid["sample_size"] == 200
        and rejects(catalog, sample_size=0)
        and rejects(catalog, sample_size=True)
        and rejects(catalog, sample_size=1.5)
        and "cantidad agregada" in doc
    )
    result[IDS[2]] = (
        set(valid) == RECORD_FIELDS
        and rejects(catalog, dynamic_extra="synthetic")
        and "No se permiten campos adicionales" in doc
    )
    result[IDS[3]] = (
        {"email", "ip", "user_id", "session_id"}.isdisjoint(RECORD_FIELDS)
        and rejects(catalog, email="test@example.invalid")
        and rejects(catalog, user_id="fake")
        and "En particular el contrato no tiene nombre" in doc
    )
    result[IDS[4]] = (
        {spec["family"] for spec in catalog.values()} == FAMILIES
        and FAMILIES == {"usage", "error", "conversion", "cwv", "seo"}
        and "cinco familias obligatorias" in doc
    )
    m = marker(catalog)
    row = normalized(catalog)
    result[IDS[5]] = (
        m["metric"] == row["metric"]
        and m["surface"] == row["surface"]
        and m["target_improvement_pct"] == 10.0
        and required_epics([row, row]) == [EPIC]
        and fails(lambda: aggregate(
            [row], catalog, epic_markers={}))
        and fails(lambda: aggregate(
            [row], catalog, epic_markers={
                EPIC: {**m, "surface": "other"}}))
        and "resolver el Issue real" in doc
    )
    other_base = normalized(
        catalog, period_start="2026-09-07T00:00:00Z",
        period_end="2026-09-14T00:00:00Z",
    )
    result[IDS[6]] = (
        fails(lambda: compare(catalog, extra=[other_base]))
        and fails(lambda: compare(
            catalog, extra=[normalized(
                catalog, period_start="2026-09-04T00:00:00Z",
                period_end="2026-09-10T00:00:00Z")]))
        and "ventanas dentro de una fase no pueden solaparse" in doc
    )
    cwv = [
        normalized(catalog, metric="lcp_p75_ms", value=2000,
                   period_start="2026-09-01T00:00:00Z",
                   period_end="2026-09-04T00:00:00Z"),
        normalized(catalog, metric="lcp_p75_ms", value=2200,
                   period_start="2026-09-04T00:00:00Z",
                   period_end="2026-09-08T00:00:00Z"),
    ]
    result[IDS[7]] = (
        fails(lambda: aggregate(cwv, catalog, epic_markers={
            EPIC: {**m, "metric": "lcp_p75_ms", "direction": "decrease"}}))
        and "único agregado por fase" in doc
    )
    low = compare(catalog, baseline_samples=99, post_samples=99)
    enough = compare(catalog, baseline_samples=100, post_samples=100)
    result[IDS[8]] = (
        low["results"][0]["status"] == "insufficient-data"
        and not low["proposals"]
        and enough["results"][0]["status"] == "regressed"
        and "al menos 100 muestras" in doc
    )
    missing = aggregate([row], catalog, epic_markers={EPIC: m})
    zero = compare(catalog, baseline=0)
    result[IDS[9]] = (
        not missing["proposals"]
        and missing["results"][0]["status"] == "insufficient-data"
        and zero["results"][0]["status"] == "non-comparable-zero-baseline"
        and zero["results"][0]["delta_pct"] is None
        and not zero["proposals"]
    )
    threshold = compare(catalog, post=0.21)
    below = compare(catalog, post=0.209)
    result[IDS[10]] = (
        len(threshold["proposals"]) == 1
        and threshold["proposals"][0]["regression_pct"] == 5.0
        and not below["proposals"]
        and "al menos 5%" in doc
    )
    proposal = threshold["proposals"][0]
    result[IDS[11]] = (
        proposal["impact_score"] ==
        round(proposal["regression_pct"] * min(
            4.0, round(math.log10(proposal["post_deploy_samples"] + 1), 4)), 2)
        and "solo ordenar evidencia comparable" in doc
        and not any(k in proposal for k in ("revenue", "legal_severity"))
    )
    full = compare(catalog)
    markdown = render_markdown(full)
    result[IDS[12]] = (
        '"reporte-producto.json"' in source
        and '"results": results' in source
        and '"proposals": proposals' in source
        and full["records"] == 2
        and "artifacts/reporte-producto.json" in doc
    )
    result[IDS[13]] = (
        '"reporte-producto.md"' in source
        and "## Propuestas priorizadas" in markdown
        and EPIC in markdown
        and "artifacts/reporte-producto.md" in doc
    )
    result[IDS[14]] = (
        required_epics([row, row]) == [EPIC]
        and "load_epic_markers(" in source
        and "sin recibir token de GitHub" in doc
    )
    with tempfile.TemporaryDirectory(prefix="factory-feedback-synth-") as tmp:
        path = Path(tmp) / "epic-markers.json"
        path.write_text(json.dumps({EPIC: BODY}), encoding="utf-8")
        loaded = load_epic_markers(path, catalog, [EPIC])
        bad_marker = BODY.replace('"surface":"home"', '"surface":"other"')
        path.write_text(json.dumps({EPIC: bad_marker}), encoding="utf-8")
        mismatch = load_epic_markers(path, catalog, [EPIC])
        path.write_text(json.dumps({}), encoding="utf-8")
        missing_issue = fails(
            lambda: load_epic_markers(path, catalog, [EPIC]))
        path.write_text(json.dumps({EPIC: "sin marker"}), encoding="utf-8")
        missing_marker = fails(
            lambda: load_epic_markers(path, catalog, [EPIC]))
    result[IDS[15]] = (
        loaded[EPIC]["metric"] == "error_rate"
        and missing_issue and missing_marker
        and fails(lambda: aggregate(
            [row], catalog, epic_markers=mismatch))
        and "corrida falla cerrado" in doc
    )
    return result


def project(raw_matrix: object, checks: object, live_claim=None) -> dict:
    try:
        matrix_rows(raw_matrix)
    except ValueError:
        return dict.fromkeys(IDS, UNKNOWN)
    if (type(checks) is not dict or set(checks) != set(IDS)
            or any(type(v) is not bool for v in checks.values())):
        return dict.fromkeys(IDS, UNKNOWN)
    return {key: (LOCAL if checks[key] and key not in EXTERNAL else UNKNOWN)
            for key in IDS}


class BrechasFactory65Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = read(MATRIX_PATH)
        cls.doc = read(DOC_PATH)
        cls.source = read(SOURCE_PATH)
        cls.catalog = load_catalog()

    def test_contrato_principal(self):
        rows = matrix_rows(self.matrix)
        found = evidence(self.catalog, self.doc, self.source)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(found), set(IDS))
        for key in IDS:
            with self.subTest(row=key):
                self.assertTrue(found[key], "sin aserción específica: " + key)
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")

    def test_falla_cerrado(self):
        found = evidence(self.catalog, self.doc, self.source)
        target = next(line for line in self.matrix.splitlines()
                      if "\x60" + IDS[0] + "\x60" in line)
        for changed in (
            None, "", self.matrix.replace(target, "", 1),
            self.matrix + "\n" + target,
            self.matrix.replace(
                target, target.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
        ):
            with self.subTest(matrix=str(changed)[:25]):
                with self.assertRaises(ValueError):
                    matrix_rows(changed)
                self.assertEqual(set(project(changed, found).values()), {UNKNOWN})
        for fake in (None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
                     dict.fromkeys(IDS, "success"),
                     {**dict.fromkeys(IDS, True), "extra": True}):
            self.assertEqual(set(project(self.matrix, fake).values()), {UNKNOWN})
        self.assertTrue(rejects(self.catalog, sample_size=0))
        self.assertTrue(rejects(self.catalog, value=float("inf")))
        self.assertTrue(fails(lambda: aggregate(
            [normalized(self.catalog)], self.catalog, epic_markers={})))

    def test_sin_datos_reales(self):
        payload = json.dumps(fixture(), sort_keys=True).lower()
        for forbidden in ("access_token", "ghp_", "password", "private key",
                          "https://", "http://", "@gmail", "real-user"):
            self.assertNotIn(forbidden, payload)
        tree = ast.parse(read("tests/test_brechas_factory_65.py"))
        banned = {"requests", "socket", "urllib", "http", "subprocess"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(
                    {x.name.split(".")[0] for x in node.names} & banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], banned)

    def test_estados_unknown_explicitos(self):
        checks = evidence(self.catalog, self.doc, self.source)
        for synthetic_claim in (None, {}, {"live": True}, {"ci": "success"},
                                {"github_issues": "resolved"},
                                {"artifacts": "published"}):
            statuses = project(self.matrix, checks, synthetic_claim)
            self.assertEqual(set(statuses), set(IDS))
            for key in IDS:
                with self.subTest(key=key, claim=synthetic_claim):
                    self.assertEqual(statuses[key],
                                     UNKNOWN if key in EXTERNAL else LOCAL)
                    self.assertNotIn(statuses[key], {"CUBIERTO", "LIVE"})
        self.assertEqual(set(project(self.matrix,
                                   dict.fromkeys(IDS, False)).values()),
                         {UNKNOWN})


if __name__ == "__main__":
    unittest.main()
