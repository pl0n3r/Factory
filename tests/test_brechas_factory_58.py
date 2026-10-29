#!/usr/bin/env python3
"""Factory #1676: contraste local de 16 brechas Sonar, README y reconciliación.

Los fixtures no acreditan CI, Sonar remoto, estado actual de Issues ni producción.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

from quality.sonar import SonarEvidenceError, normalize_sonar_snapshot
from readme.progress_readiness import calculate_progress_readiness

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
SONAR = "docs/quality-sonar.md"
README = "docs/readme-contract.md"
READINESS = "docs/readme-progress-readiness.md"
HISTORY = "docs/reconciliacion-issues-20261024.md"
SONAR_POLICY = "quality/sonar-watch-config.json"
README_POLICY = "readme/contract.json"
PATHS = (MATRIX, SONAR, README, READINESS, HISTORY, SONAR_POLICY, README_POLICY)
UNKNOWN, LOCAL = "UNKNOWN", "CONTRATO_LOCAL"
NOW = "2026-09-30T12:00:00Z"

CLAUSES = {
    "docs/quality-sonar.md:L34-U1": (SONAR, "Los `evidence_ref` item-level se validan pero no se propagan"),
    "docs/quality-sonar.md:L34-U2": (SONAR, "la autoridad del lote queda en `snapshot.evidence_refs`"),
    "docs/quality-sonar.md:L5-U1": (SONAR, "Debe declarar:"),
    "docs/quality-sonar.md:L7-U1": (SONAR, "`project` dentro del catálogo explícito"),
    "docs/quality-sonar.md:L8-U1": (SONAR, "`snapshot_at` con zona horaria"),
    "docs/quality-sonar.md:L9-U1": (SONAR, "`quality_gate` con estado"),
    "docs/readme-contract.md:B03": (README, "Se añade únicamente si el producto ya expone un endpoint público real"),
    "docs/readme-contract.md:B04": (README, "no hace commits automáticos para cambiar estado"),
    "docs/readme-progress-readiness.md:B04": (READINESS, "Los targets de adopción viven en"),
    "docs/reconciliacion-issues-20261024.md:L20-U1": (HISTORY, "8 Issues abiertos"),
    "docs/reconciliacion-issues-20261024.md:L20-U2": (HISTORY, "0 cierres automáticos"),
    "docs/reconciliacion-issues-20261024.md:L20-U3": (HISTORY, "La existencia de commits parciales no permite cerrar"),
    "docs/reconciliacion-issues-20261024.md:L21-U1": (HISTORY, "No se fusiona Factory@v1"),
    "docs/reconciliacion-issues-20261024.md:L21-U2": (HISTORY, "Esta hoja solo reclama su documento y su test"),
    "docs/reconciliacion-issues-20261024.md:L22-U1": (HISTORY, "Antes de un corte posterior hay que releer Issues"),
    "docs/reconciliacion-issues-20261024.md:L22-U2": (HISTORY, "Este documento no prueba el estado futuro"),
}
IDS = tuple(CLAUSES)
HISTORICAL = frozenset(k for k in IDS if k.startswith(HISTORY + ":"))
SONAR_IDS = tuple(k for k in IDS if k.startswith(SONAR + ":"))
README_IDS = tuple(k for k in IDS if k not in HISTORICAL and k not in SONAR_IDS)


def sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in PATHS}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Rechazar filas ausentes, duplicadas, ambiguas y promocionadas."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: matriz ilegible")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| `"):
            continue
        cells = tuple(s.strip() for s in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        if not cells or not cells[0].startswith("`"):
            continue
        key = cells[0].strip("`")
        if key not in CLAUSES:
            continue
        if (key in found or len(cells) != 5 or not cells[1]
                or cells[2] != "NO_VERIFICABLE" or not cells[3] or not cells[4]):
            raise ValueError("UNKNOWN: fila inválida " + key)
        if key.startswith(SONAR + ":") and (
            "[Contraste #1573](contraste-factory_resto_5.md)" not in cells[3]
            or cells[4] != "—"
        ):
            raise ValueError("UNKNOWN: provenance Sonar inválida " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: faltan filas")
    return found


def doc_matches(key: str, data: dict[str, str]) -> bool:
    if key not in CLAUSES:
        return False
    path, phrase = CLAUSES[key]
    content = data.get(path)
    if type(content) is not str or phrase.casefold() not in content.casefold():
        return False
    match = re.search(r":L([1-9]\d*)-U[1-9]\d*$", key)
    if match:
        lines = content.splitlines()
        number = int(match.group(1)) - 1
        return number < len(lines) and phrase.casefold() in lines[number].casefold()
    return True


def sonar_policy(data: dict[str, str]) -> dict:
    config = json.loads(data[SONAR_POLICY])
    contracts = [r["contract"] for r in config["projects"] if r["project"] == "factory"]
    if config["version"] != 1 or len(contracts) != 1:
        raise ValueError("UNKNOWN: contract ambiguo")
    return contracts[0]


def snapshot() -> dict:
    return {
        "project": "factory", "snapshot_at": "2026-09-30T11:55:00Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {"analyzed_at": "2026-09-30T11:50:00Z",
                     "method": "ci", "coverage_available": True},
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50},
        "visibility": "public", "debt": [],
        "evidence_refs": ["sonar:factory:synthetic:snapshot"],
    }


def normalized(policy: dict, sample: dict) -> dict:
    return normalize_sonar_snapshot(policy, sample, observed_at=NOW)


def signal(result: dict, name: str) -> dict:
    return next(s for s in result["signals"] if s["signal"] == name)


def sonar_proofs(data: dict[str, str]) -> dict[str, bool]:
    policy, raw = sonar_policy(data), snapshot()
    base = normalized(policy, raw)
    with_item = deepcopy(raw)
    with_item["debt"] = [{
        "type": "bug", "severity": "MINOR",
        "opened_at": "2026-09-29T12:00:00Z",
        "evidence_ref": "sonar:synthetic:item:1",
    }]
    debt = normalized(policy, with_item)
    refs = signal(debt, "historical_debt")["evidence_refs"]
    invalid = deepcopy(with_item)
    invalid["debt"][0]["evidence_ref"] = "https://example.invalid/secret"
    try:
        normalized(policy, invalid)
    except SonarEvidenceError:
        rejected_item = True
    else:
        rejected_item = False
    missing = deepcopy(raw)
    missing["quality_gate"] = None
    unknown_gate = signal(normalized(policy, missing), "quality_gate")
    extra = deepcopy(raw)
    extra["unexpected"] = True
    try:
        normalized(policy, extra)
    except SonarEvidenceError:
        rejected_extra = True
    else:
        rejected_extra = False
    wrong = deepcopy(raw)
    wrong["project"] = "invalid"
    try:
        normalized(policy, wrong)
    except SonarEvidenceError:
        rejected_project = True
    else:
        rejected_project = False
    naive = deepcopy(raw)
    naive["snapshot_at"] = "2026-09-30T11:55:00"
    try:
        normalized(policy, naive)
    except SonarEvidenceError:
        rejected_naive = True
    else:
        rejected_naive = False
    failure = deepcopy(raw)
    failure["quality_gate"] = {"status": "ERROR", "conditions": [
        {"metric": "new_bugs", "status": "ERROR", "actual": "1", "threshold": "0"}]}
    failed_gate = signal(normalized(policy, failure), "quality_gate")
    tests = (
        rejected_item and "sonar:synthetic:item:1" not in refs,
        refs == ["sonar:factory:synthetic:snapshot"]
        and signal(debt, "historical_debt")["details"]["counts"][0]["count"] == 1,
        rejected_extra and unknown_gate["status"] == UNKNOWN,
        rejected_project and base["project"] == "factory",
        rejected_naive and base["snapshot_freshness"]["state"] == "CURRENT",
        failed_gate["status"] == "FAIL"
        and len(failed_gate["details"]["failed_conditions"]) == 1,
    )
    return dict(zip(SONAR_IDS, tests, strict=True))


def readme_proofs(data: dict[str, str]) -> dict[str, bool]:
    live = json.loads(data[README_POLICY])["live_status"]
    result = calculate_progress_readiness({
        "version": 1,
        "target": {"id": "fixture", "label": "Synthetic Fixture",
                   "scope": "pl0n3r/Factory", "version": "1"},
        "dimensions": [{"id": "service", "label": "Service", "weight": 1,
                        "milestones": [{"id": "health", "label": "Health",
                                        "weight": 1, "progress_state": UNKNOWN,
                                        "readiness_state": UNKNOWN,
                                        "evidence_refs": []}]}],
        "blockers": [], "observed_at": NOW,
    })
    checks = (
        live["missing_optional_source"] == "omit"
        and "public_health" in live["optional_sources"]
        and "endpoint público real" in data[README],
        live["commits_for_refresh"] is False
        and live["refresh_mode"] == "request_time"
        and "no hace commits automáticos" in data[README],
        result["readiness"]["status"] != "READY"
        and result["evidence_freshness"] == "DEGRADED"
        and "Los targets de adopción" in data[READINESS],
    )
    return dict(zip(README_IDS, checks, strict=True))


def evidence(data: dict[str, str]) -> dict[str, bool]:
    proofs = {**sonar_proofs(data), **readme_proofs(data)}
    for key in HISTORICAL:
        proofs[key] = (
            "**Corte exacto:**" in data[HISTORY]
            and "**fotografía fechada**" in data[HISTORY]
            and doc_matches(key, data)
        )
    if set(proofs) != set(IDS):
        raise ValueError("UNKNOWN: falta aserción")
    return proofs


def assess(data: object, proofs: object) -> dict[str, str]:
    if (type(data) is not dict or set(data) != set(PATHS)
            or any(type(v) is not str or not v for v in data.values())
            or type(proofs) is not dict or set(proofs) != set(IDS)
            or any(type(v) is not bool for v in proofs.values())):
        return dict.fromkeys(IDS, UNKNOWN)
    try:
        matrix_rows(data[MATRIX])
    except ValueError:
        return dict.fromkeys(IDS, UNKNOWN)
    return {k: (LOCAL if proofs[k] and doc_matches(k, data)
                and k not in HISTORICAL else UNKNOWN) for k in IDS}


def remote_verdict(_key: str) -> str:
    """Necesita observación externa autenticada que aquí no existe."""
    return UNKNOWN


class BrechasFactory58Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = sources()
        cls.proofs = evidence(cls.data)

    def test_contrato_principal(self) -> None:
        """AC-01: 16 filas, nueve contratos locales y siete brechas históricas."""
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(matrix_rows(self.data[MATRIX])), set(IDS))
        results = assess(self.data, self.proofs)
        for key in IDS:
            with self.subTest(row=key):
                self.assertTrue(doc_matches(key, self.data), key)
                self.assertTrue(self.proofs[key], key)
                self.assertEqual(UNKNOWN if key in HISTORICAL else LOCAL,
                                 results[key], key)

    def test_falla_cerrado(self) -> None:
        """AC-02: omisiones, duplicados, promoción, datos no fiables."""
        baseline = self.data[MATRIX]
        row = next(x for x in baseline.splitlines()
                   if x.startswith("| `" + IDS[0] + "` |"))
        with self.assertRaises(ValueError):
            matrix_rows(baseline + "\n" + row)
        with self.assertRaises(ValueError):
            matrix_rows(baseline.replace(row, "", 1))
        with self.assertRaises(ValueError):
            matrix_rows(baseline.replace(
                row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1))
        for key in IDS:
            with self.subTest(row=key):
                changed = dict(self.data)
                changed[CLAUSES[key][0]] = ""
                self.assertEqual(UNKNOWN, assess(changed, self.proofs)[key])
                negative = dict(self.proofs)
                negative[key] = False
                self.assertEqual(UNKNOWN, assess(self.data, negative)[key])
        self.assertEqual(set(assess(self.data, {**self.proofs, "fake": True}).values()), {UNKNOWN})
        self.assertEqual(set(assess(self.data, None).values()), {UNKNOWN})

    def test_sin_datos_reales(self) -> None:
        """AC-03: sin secretos, PII, peticiones externas ni mutaciones."""
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^(?:from|import)\s+(?:requests|httpx|socket|subprocess|urllib)\b")
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", own)
        self.assertNotRegex(own, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
        self.assertEqual(set(PATHS), set(self.data))
        for path in PATHS:
            self.assertFalse(Path(path).is_absolute())
            self.assertTrue((ROOT / path).is_file())
        self.assertFalse(normalized(sonar_policy(self.data), snapshot())["execute_actions"])

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04 local: sin inferir producción ni estado actual de un corte viejo."""
        evaluated = assess(self.data, self.proofs)
        self.assertEqual(HISTORICAL, {k for k in IDS if evaluated[k] == UNKNOWN})
        rows = matrix_rows(self.data[MATRIX])
        for key in IDS:
            with self.subTest(row=key):
                self.assertEqual("NO_VERIFICABLE", rows[key][2])
                self.assertNotEqual("CUBIERTO", evaluated[key])
                self.assertEqual(UNKNOWN, remote_verdict(key))
        self.assertIn("24 de octubre de 2026", self.data[HISTORY])


if __name__ == "__main__":
    unittest.main()
