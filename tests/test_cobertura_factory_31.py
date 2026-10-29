"""#1822: regresiones ejecutables de Performance Factory (20 filas de matriz).

Cada caso ejerce los módulos ya existentes con contratos, métricas, logs y
corridas *sintéticos*. Los resultados no prueban autenticación REST, CrUX,
producción, efectos de Workflow/WorkItem ni una adopción de baseline.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from performance.contract import validate_performance_contract, PerformanceContractError
from performance.detector import detect_performance, PerformanceDetectionError
from performance.ci_professional_report import diagnose_factoryrunner_ci_professionals
from performance.github_actions_ci import evaluate_factoryrunner_ci_run, PerformanceCiObservationError
from performance.ci_suite_benchmark import (
    SuiteBenchmarkError, parse_unittest_summary, compare_unittest_summaries,
)
from performance.classifier import classify_performance_envelope, PerformanceClassifierError

ROOT = Path(__file__).resolve().parents[1]
BRVTAL = ROOT / 'performance/contracts/brvtal.json'
FACTORYRUNNER = ROOT / 'performance/contracts/factoryrunner.json'
T = '2026-10-01T11:47:49Z'
NOW = '2026-10-01T12:00:00Z'
SHA = '7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf'
REF = 'github:pl0n3r/brvtal/actions/runs/36853443439@attempt2'
RUN_SHA = '33277d549a82e9cba5371982d1d80e43e06bd0d5'
CI_NOW = '2026-10-24T20:00:00Z'


def contract(name: str) -> dict:
    path = {'brvtal': BRVTAL, 'factoryrunner': FACTORYRUNNER}[name]
    return json.loads(path.read_text(encoding='utf-8'))


def observation(metric='fcp', *, value=None, surface='public.home.mobile', **changes) -> dict:
    sample = {
        'version': 1, 'project': 'brvtal', 'surface': surface, 'metric': metric,
        'value': {'fcp': 380, 'lcp': 1624, 'cls': 0, 'dom_content_loaded': 419}[metric] if value is None else value,
        'unit': 'ratio' if metric == 'cls' else 'ms', 'observed_at': T,
        'window_seconds': 1, 'sample_count': 1,
        'severity': 'info', 'operational_impact': False,
        'bottleneck': 'frontend', 'evidence_ref': REF, 'sha': SHA, 'release': '0.1.101',
    }
    sample.update(changes)
    return sample


def envelope() -> dict:
    return {
        'version': 1, 'project': 'brvtal',
        'classification_authority': 'factory-performance-v1',
        'classification': None,
        'identity': {'sha': SHA, 'release': '0.1.101'},
        'evidence_ref': REF, 'observed_at': T,
        'observations': [observation(), observation('dom_content_loaded')],
    }


def ci_run() -> dict:
    return {
        'id': 40119747013, 'name': 'CI', 'event': 'push',
        'head_branch': 'main', 'head_sha': RUN_SHA,
        'status': 'completed', 'conclusion': 'success', 'run_attempt': 1,
        'run_started_at': '2026-10-24T18:13:54Z',
        'updated_at': '2026-10-24T18:16:04Z',
        'repository': {'full_name': 'pl0n3r/FactoryRunner'},
    }


def log(count=616, seconds='104.376') -> str:
    return f'Ran {count} tests in {seconds}s\n\nOK\n'


def provenance(run_id, sha, job):
    return {'repository': 'pl0n3r/FactoryRunner', 'event': 'push',
            'branch': 'main', 'suite': 'python.unittest',
            'run_id': run_id, 'head_sha': sha, 'job_id': job}


class CoberturaFactory31Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """13 filas offline: valores/budgets, CI GET-only, parser y delegación."""
        brvtal = contract('brvtal')
        canonical = validate_performance_contract(brvtal)
        self.assertEqual(canonical['project'], 'brvtal')
        # docs/performance-brvtal.md:L26-28: tres budgets de laboratorio.
        for metric, value, budget in (('fcp', 1800, 1800), ('lcp', 2500, 2500), ('cls', 0.1, 0.1)):
            with self.subTest(row=f'brvtal/{metric}'):
                for candidate, expected in ((value, False), (budget + 1, True)):
                    result = detect_performance(brvtal, observation(metric, value=candidate), evaluated_at=NOW)
                    self.assertEqual(result['budget']['operator'], 'lte')
                    self.assertEqual(result['budget']['value'], budget)
                    self.assertIs(result['breach'], expected)
                    self.assertEqual(result['classification'], 'PERF_DEGRADATION' if expected else 'PERF_INFO')
        # docs/performance-brvtal.md:L34: ventana puntual, freshness explícita.
        fresh = detect_performance(brvtal, observation(), evaluated_at=NOW)
        stale = detect_performance(brvtal, observation(), evaluated_at='2026-10-10T12:00:00Z')
        self.assertEqual((fresh['evidence_state'], fresh['classification']), ('CURRENT', 'PERF_INFO'))
        self.assertEqual((stale['evidence_state'], stale['classification']), ('STALE', 'PERF_REVIEW'))
        self.assertEqual(fresh['observed']['sample_count'], 1)
        # docs/performance-brvtal.md:L36: sin presupuesto, UNKNOWN estricto.
        unknown = detect_performance(brvtal, observation('dom_content_loaded'), evaluated_at=NOW)
        self.assertEqual((unknown['classification'], unknown['evidence_state']), ('PERF_REVIEW', 'UNKNOWN'))
        self.assertIsNone(unknown['budget'])
        self.assertIsNone(unknown['breach'])
        self.assertEqual(unknown['allowed_actions'], [])

        # docs/performance-ci-professional-report.md:L14-15: policy read-only.
        runner_contract = validate_performance_contract(contract('factoryrunner'))
        metric_spec = runner_contract['surfaces'][0]['metrics'][0]
        self.assertEqual(set(metric_spec['allowed_actions']), {'observe', 'diagnose', 'benchmark'})
        self.assertNotIn('create_work_item', metric_spec['allowed_actions'])
        self.assertNotIn('auto_repair', metric_spec['allowed_actions'])
        # docs/performance-ci-professional-report.md:L20,23,28: profesional
        # recomendado sin asignar, datos saneados y ninguna autoridad ejecutiva.
        report = diagnose_factoryrunner_ci_professionals(
            contract('factoryrunner'), ci_run(), evaluated_at=CI_NOW)
        self.assertEqual(report['classification'], 'PERF_DEGRADATION')
        self.assertEqual(report['readiness']['status'], 'DEGRADED')
        self.assertEqual(report['team']['decision'], 'TEAM_RECOMMENDED')
        self.assertEqual(report['team']['primary'], 'sre')
        self.assertTrue({'sre', 'qa'}.issubset(report['team']['roles']))
        self.assertEqual(report['identity']['sha'], RUN_SHA)
        self.assertEqual(report['authority'], 'unchanged')
        for flag in ('execute_actions', 'create_work_item', 'dispatch', 'adopt', 'candidate_terminal'):
            self.assertIs(report[flag], False, flag)

        # docs/performance-ci-suite-benchmark.md:L22-U1,L5-U1,L7-U2:
        # parser del job distinto del adaptador de corrida completa.
        measured = parse_unittest_summary(log())
        self.assertEqual(measured, {'suite': 'python.unittest', 'tests': 616,
                                    'duration_ms': 104376, 'status': 'DIAGNOSTIC_ONLY'})
        whole = evaluate_factoryrunner_ci_run(contract('factoryrunner'), ci_run(), evaluated_at=CI_NOW)
        self.assertEqual(whole['detection']['observed']['value'], 130)
        self.assertEqual(whole['detection']['classification'], 'PERF_DEGRADATION')
        self.assertEqual(measured['duration_ms'], 104376)
        self.assertFalse(whole['create_work_item'])

        # docs/performance-ci-suite-benchmark.md:L22-U2: sintético
        # comparable solo diagnóstico; diferente recuento -> no comparable.
        before = parse_unittest_summary(log(615, '152.868'))
        older = provenance(40029930158, '789a312d7520e9813835f99d8c4e5de5ee22cb2a', 120675383335)
        newer = provenance(40119747013, RUN_SHA, 120948484385)
        not_comparable = compare_unittest_summaries(before, measured, older, newer)
        self.assertEqual(not_comparable['status'], 'NO_COMPARABLE')
        self.assertIsNone(not_comparable['duration_delta_ms'])
        equal_count = compare_unittest_summaries(
            parse_unittest_summary(log(616, '100.000')), measured, older, newer)
        self.assertEqual(equal_count['status'], 'COMPARABLE_DIAGNOSTIC')
        self.assertEqual(equal_count['duration_delta_ms'], 4376)
        self.assertEqual(equal_count['causality'], 'unproven')
        for payload in (not_comparable, equal_count):
            self.assertFalse(payload['adopt'])
            self.assertFalse(payload['create_work_item'])
            self.assertFalse(payload['execute_actions'])

        # docs/performance-classification.md:L3-U1,L11-U1: el
        # clasificador llama realmente al detector; no crea WorkItems.
        with mock.patch('performance.classifier.detect_performance', wraps=detect_performance) as detector_spy:
            classified = classify_performance_envelope(brvtal, envelope(), evaluated_at=NOW)
        self.assertEqual(detector_spy.call_count, 2)
        self.assertEqual(classified['summary']['classifications'], {'PERF_INFO': 1, 'PERF_REVIEW': 1})
        self.assertEqual(classified['summary']['evidence_states'], {'CURRENT': 1, 'UNKNOWN': 1})
        self.assertIs(classified['execute_actions'], False)
        self.assertIs(classified['create_work_item'], False)

    def test_falla_cerrado(self):
        """Datos falsos, insuficientes y sin autoridad nunca generan remedios."""
        brvtal = contract('brvtal')
        for invalid in (dict(brvtal, project='invalid project'), dict(brvtal, token='dummy'),
                        dict(brvtal, surfaces=[])):
            with self.subTest(contract=tuple(invalid)):
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(invalid)
        for change in ({'unit': 's'}, {'sample_count': False}, {'value': float('nan')},
                       {'evidence_ref': 'ghp_' + 'x' * 30}):
            with self.subTest(change=change):
                with self.assertRaises(PerformanceDetectionError):
                    detect_performance(brvtal, observation(**change), evaluated_at=NOW)
        for change in ({'event': 'pull_request'}, {'head_branch': 'dev'},
                       {'head_sha': 'bad'}, {'status': 'in_progress'},
                       {'repository': {'full_name': 'other/repo'}}):
            with self.subTest(ci=change):
                bad = dict(ci_run(), **change)
                with self.assertRaises(PerformanceCiObservationError):
                    evaluate_factoryrunner_ci_run(contract('factoryrunner'), bad, evaluated_at=CI_NOW)
        unknown = diagnose_factoryrunner_ci_professionals(
            contract('factoryrunner'), ci_run(), evaluated_at='2026-11-02T20:00:00Z')
        self.assertEqual(unknown['status'], 'UNKNOWN')
        self.assertEqual(unknown['team']['decision'], 'NO_ASSIGNMENT')
        self.assertFalse(unknown['create_work_item'])
        for invalid in ('', log() + log(), log().replace('OK', 'FAILED (errors=1)'),
                        log().replace('104.376', 'nan'), 'a' * 256001):
            with self.subTest(log=str(invalid[:16])):
                with self.assertRaises(SuiteBenchmarkError):
                    parse_unittest_summary(invalid)
        valid = parse_unittest_summary(log())
        for corrupt in ({**valid, 'tests': True}, {**valid, 'status': 'HEALTHY'}):
            with self.assertRaises(SuiteBenchmarkError):
                compare_unittest_summaries(corrupt, valid,
                    provenance(10, 'a'*40, 10), provenance(11, 'b'*40, 11))
        for payload in (
            dict(envelope(), classification='PERF_INFO'),
            dict(envelope(), classification_authority='producer'),
            dict(envelope(), secret_payload='dummy'),
        ):
            with self.assertRaises(PerformanceClassifierError):
                classify_performance_envelope(brvtal, payload, evaluated_at=NOW)
        duplicate = envelope()
        duplicate['observations'].append(copy.deepcopy(duplicate['observations'][0]))
        with self.assertRaises(PerformanceClassifierError):
            classify_performance_envelope(brvtal, duplicate, evaluated_at=NOW)

    def test_sin_datos_reales(self):
        """Proyección blanca real, sin copiar metadatos privados del input."""
        input_run = ci_run()
        sentinel = 'synthetic-private-payload-not-a-real-secret'
        input_run['noncanonical_extra'] = sentinel
        report = diagnose_factoryrunner_ci_professionals(
            contract('factoryrunner'), input_run, evaluated_at=CI_NOW)
        self.assertNotIn(sentinel, repr(report))
        self.assertEqual(set(report), {
            'version', 'project', 'surface', 'metric', 'classification',
            'evidence_state', 'status', 'identity', 'evidence_refs', 'readiness',
            'team', 'authority', 'execute_actions', 'create_work_item',
            'dispatch', 'adopt', 'candidate_terminal',
        })
        self.assertIs(report['dispatch'], False)
        bench = parse_unittest_summary(sentinel + '\n' + log())
        self.assertEqual(bench['status'], 'DIAGNOSTIC_ONLY')
        self.assertNotIn(sentinel, repr(bench))
        classified = classify_performance_envelope(contract('brvtal'), envelope(), evaluated_at=NOW)
        self.assertNotIn('token', classified)
        self.assertIs(classified['create_work_item'], False)


if __name__ == '__main__':
    unittest.main()