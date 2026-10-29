"""Factory #1671: 16 Quality clauses through deterministic local witnesses.

No local test certifies project rollout, production health, Sonar API, or CI.
The matrix is not updated: NO_VERIFICABLE until separate MERGED reconciliation.
"""
from __future__ import annotations
import ast
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_SYNTHETIC_ONLY"
GAP = "BRECHA_DOCUMENTADA"
SPEC = {
    "docs/quality-engineering.md:L32-U2": ("docs/quality-engineering.md", "permanece degradación explícita", "test_quality_engineering_e2e.QualityEngineeringE2ETests.test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority"),
    "docs/quality-engineering.md:L33-U1": ("docs/quality-engineering.md", "un blocker crítico nunca se diluye", "test_quality_engineering_e2e.QualityEngineeringE2ETests.test_critical_quality_failure_materializes_corrective_work_through_existing_dispatcher"),
    "docs/quality-engineering.md:L41-U1": ("docs/quality-engineering.md", "Quality solo consume sus proyecciones", "test_quality_engineering_e2e.QualityEngineeringE2ETests.test_performance_and_recovery_remain_external_without_recalculation"),
    "docs/quality-engineering.md:L43-U1": ("docs/quality-engineering.md", "El rollout a Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory y FactoryRunner", None),
    "docs/quality-gates.md:L11-U1": ("docs/quality-gates.md", "La criticidad Quality solo puede elevar riesgo", "test_quality_gates.QualityGateCompilerTests.test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk"),
    "docs/quality-gates.md:L11-U2": ("docs/quality-gates.md", "Nunca reduce señales, blast radius ni controles", "test_quality_gates.QualityGateCompilerTests.test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk"),
    "docs/quality-gates.md:L7-U1": ("docs/quality-gates.md", "Risk y DoD consumen Quality Contract solo si valida con #343", "test_quality_gates.QualityGateCompilerTests.test_dod_adds_required_quality_gates_without_removing_existing_evidence"),
    "docs/quality-gates.md:L7-U2": ("docs/quality-gates.md", "Falta, mismatch o superficie desconocida falla cerrado", "test_quality_gates.QualityGateCompilerTests.test_missing_mismatched_or_undeclared_quality_context_fails_closed"),
    "docs/quality-health.md:B01": ("docs/quality-health.md", "Evidencia ausente, stale o unknown nunca equivale a PASS", "test_quality_status.QualityStatusTests.test_quality_health_derives_pass_degraded_unknown_blocked_with_reasons_and_freshness"),
    "docs/quality-health.md:B02": ("docs/quality-health.md", "NOT_APPLICABLE se conserva visible con razón/provenance", "test_quality_status.QualityStatusTests.test_sonar_not_applicable_is_projected_without_corrective_class"),
    "docs/quality-health.md:B03": ("docs/quality-health.md", "Quality consume sus estados canónicos y conserva razones/evidencia", "test_quality_status.QualityStatusTests.test_performance_and_recovery_are_external_dimensions_without_recalculation"),
    "docs/quality-health.md:B04": ("docs/quality-health.md", "UNKNOWN y BLOCKED nunca son ready", "test_quality_status.QualityStatusTests.test_readiness_projection_reuses_quality_health_and_unknown_or_blocked_never_ready"),
    "docs/quality-project-dna.md:L12-U1": ("docs/quality-project-dna.md", "source_ref", "test_quality_project_dna.QualityProjectDnaTests.test_valid_quality_contract_is_attached_by_reference_and_fingerprint"),
    "docs/quality-project-dna.md:L13-U1": ("docs/quality-project-dna.md", "fingerprint", "test_quality_project_dna.QualityProjectDnaTests.test_valid_quality_contract_is_attached_by_reference_and_fingerprint"),
    "docs/quality-project-dna.md:L17-U1": ("docs/quality-project-dna.md", "El Quality Contract completo", "test_quality_project_dna.QualityProjectDnaTests.test_valid_quality_contract_is_attached_by_reference_and_fingerprint"),
    "docs/quality-project-dna.md:L18-U1": ("docs/quality-project-dna.md", "no infiere", "test_quality_project_dna.QualityProjectDnaTests.test_existing_project_dna_discovery_remains_backward_compatible"),
}

GAPS = {
    "docs/quality-engineering.md:L43-U1":
        "Six consumers require their own independent rollout and production evidence."
}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matrix missing")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| " + chr(96)):
            continue
        cells = tuple(c.strip().replace("\\|", "|") for c in
                      re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = cells[0].strip(chr(96))
        if key not in SPEC:
            continue
        if (key in found or len(cells) != 5 or not cells[1]
                or cells[2] != "NO_VERIFICABLE" or not cells[3]
                or cells[4] != "—"):
            raise ValueError(UNKNOWN + ": invalid or promoted " + key)
        found[key] = cells
    if set(found) != set(SPEC):
        raise ValueError(UNKNOWN + ": missing coverage rows")
    return found


def valid_sources(sources: object) -> bool:
    if type(sources) is not dict or set(sources) != {r[0] for r in SPEC.values()}:
        return False
    return all(
        type(sources.get(path)) is str and phrase in sources[path]
        for path, phrase, _ in SPEC.values()
    )


def run_local_witnesses() -> dict[str, bool]:
    names = sorted({method for _, _, method in SPEC.values() if method})
    result = {}
    for name in names:
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
        capture = unittest.TestResult()
        suite.run(capture)
        result[name] = (
            capture.testsRun == 1 and not capture.errors
            and not capture.failures and not capture.skipped
        )
    return result


def evidence(key: object, matrix: object, sources: object,
             observations: object) -> str:
    if (type(key) is not str or key not in SPEC or
            type(observations) is not dict or not valid_sources(sources)):
        return UNKNOWN
    try:
        matrix_rows(matrix)
    except ValueError:
        return UNKNOWN
    _, _, method = SPEC[key]
    if method is None:
        return GAP if key in GAPS else UNKNOWN
    if set(observations) != {m for _, _, m in SPEC.values() if m}:
        return UNKNOWN
    return LOCAL if observations.get(method) is True else UNKNOWN


def operational(_key: object, _claim: object = None) -> str:
    return UNKNOWN


class BrechasFactory53Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        cls.sources = {p: (ROOT / p).read_text(encoding="utf-8")
                       for p in {r[0] for r in SPEC.values()}}

    def test_contrato_principal(self) -> None:
        self.assertEqual(16, len(SPEC))
        self.assertEqual(set(SPEC), set(matrix_rows(self.matrix)))
        self.assertTrue(valid_sources(self.sources))
        observed = run_local_witnesses()
        self.assertTrue(all(observed.values()), observed)
        for key in SPEC:
            with self.subTest(key=key):
                wanted = GAP if key in GAPS else LOCAL
                self.assertEqual(wanted, evidence(key, self.matrix, self.sources, observed))
                self.assertEqual(UNKNOWN, operational(key, observed))
                if key in GAPS:
                    self.assertIn("independent rollout", GAPS[key])

    def test_falla_cerrado(self) -> None:
        observed = {m: True for _, _, m in SPEC.values() if m}
        self.assertEqual(16, len(matrix_rows(self.matrix)))
        for key in SPEC:
            line = next(s for s in self.matrix.splitlines()
                        if s.startswith("| " + chr(96) + key + chr(96) + " |"))
            altered = (
                self.matrix.replace(line, "", 1),
                self.matrix + "\n" + line,
                self.matrix.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            )
            for bad in altered:
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(bad)
                self.assertEqual(UNKNOWN, evidence(key, bad, self.sources, observed))
            source = SPEC[key][0]
            self.assertEqual(UNKNOWN, evidence(
                key, self.matrix, {**self.sources, source: ""}, observed))
        self.assertEqual(UNKNOWN, evidence("UNKNOWN", self.matrix, self.sources, observed))
        self.assertEqual(UNKNOWN, evidence(next(iter(SPEC)), self.matrix, {}, observed))
        self.assertEqual(UNKNOWN, evidence(next(iter(SPEC)), self.matrix, self.sources, {}))

    def test_sin_datos_reales(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {
            "requests", "httpx", "socket", "urllib",
            "selenium", "playwright", "pymysql",
        })
        self.assertFalse(any("/.private" in source for source in self.sources))

    def test_estados_unknown_explicitos(self) -> None:
        observed = {m: True for _, _, m in SPEC.values() if m}
        for key in SPEC:
            with self.subTest(key=key):
                self.assertEqual("NO_VERIFICABLE", matrix_rows(self.matrix)[key][2])
                for claim in (None, True, {"ci": "success"},
                              {"production": "GREEN"}, {"sonar": "PASS"},
                              {"rollout": "complete"}):
                    self.assertEqual(UNKNOWN, operational(key, claim))
                self.assertNotEqual(
                    "VALIDATED_IN_PRODUCTION",
                    evidence(key, self.matrix, self.sources, observed),
                )
                if key in GAPS:
                    self.assertEqual(GAP, evidence(
                        key, self.matrix, self.sources, observed))
        key = "docs/quality-project-dna.md:L13-U1"
        name = SPEC[key][2]
        self.assertEqual(UNKNOWN, evidence(
            key, self.matrix, self.sources, {**observed, name: False}))


if __name__ == "__main__":
    unittest.main()
