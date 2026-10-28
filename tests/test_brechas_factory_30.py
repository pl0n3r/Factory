#!/usr/bin/env python3
"""Factory #1648: 16 label-color gaps, offline and fail-closed.

Passing a synthetic contract never proves migration, real labels, v1 release
or production readiness. The source matrix remains NO_VERIFICABLE.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.sync_label_colors import (
    GitHubLabelsClient, REPOSITORIES, REPOSITORY_LANGUAGE, SyncError,
    assert_safe_plan, execute, load_catalog, load_catalogs, plan_all,
    plan_repository, render_plan, validate_catalog_parity,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/label-color-sync.md"
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
CLAUSES = {
    "L20-U1": "exclusividad de la dimensión",
    "L22-U1": "clasificación a",
    "L22-U2": "Nunca se usa para esconder",
    "L22-U3": "migración de Issues existentes",
    "L24-U1": "ControlBot adopta",
    "L24-U2": "adopción permanece bloqueada",
    "L28-U1": "referencia histórica",
    "L30-U1": "motor",
    "L30-U2": "pruebas de paridad y reconciliación",
    "L32-U1": "No ejecutar",
    "L36-U1": "Para revertir una aplicación",
    "L36-U2": "no se requiere rename/create/delete",
    "L38-U1": "reconciliador falla cerrado",
    "L7-U1": "Fuente canónica",
    "L7-U2": "labels/en.json",
    "L8-U1": "mismo color por",
}
IDS = tuple(f"{DOC}:{unit}" for unit in CLAUSES)
LOCALS = frozenset({
    "L28-U1", "L30-U1", "L30-U2", "L32-U1",
    "L36-U1", "L36-U2", "L38-U1", "L7-U1", "L7-U2", "L8-U1",
})
GAPS = {
    "L20-U1": "UNKNOWN: exclusividad en Issues remotos no probada",
    "L22-U1": "UNKNOWN: clasificación conservadora del orquestador no probada",
    "L22-U2": "UNKNOWN: dependencias ejecutables no verificadas",
    "L22-U3": "UNKNOWN: migración y publicación v1 no autorizadas",
    "L24-U1": "UNKNOWN: adopción de ControlBot no acreditada aquí",
    "L24-U2": "UNKNOWN: publicación y sincronización reales no acreditadas",
}


def key(unit):
    return f"{DOC}:{unit}"


def matrix_rows(raw):
    """Never promote or silently accept a missing or duplicate matrix row."""
    result = {unit: UNKNOWN for unit in IDS}
    if not isinstance(raw, str):
        return result
    for unit in IDS:
        prefix = "| " + chr(96) + unit + chr(96) + " |"
        matches = [line for line in raw.splitlines() if line.startswith(prefix)]
        if len(matches) != 1:
            continue
        cells = tuple(x.strip() for x in matches[0].strip("|").split("|"))
        if (len(cells) == 5 and cells[0] == chr(96) + unit + chr(96)
                and bool(cells[1]) and cells[2] == "NO_VERIFICABLE"
                and "Contraste #1571" in cells[3] and cells[4] == "—"):
            result[unit] = "NO_VERIFICABLE"
    return result


def document_rows(raw):
    """Bind each clause to its actual numbered source line."""
    result = {unit: UNKNOWN for unit in IDS}
    if not isinstance(raw, str):
        return result
    lines = raw.splitlines()
    for unit, needle in CLAUSES.items():
        number = int(unit.split("-", 1)[0][1:])
        if len(lines) >= number and needle in lines[number - 1]:
            result[key(unit)] = "PRESENT"
    return result


def rejected(callback):
    try:
        callback()
    except SyncError:
        return True
    return False


def local_contrasts():
    """Proofs only for local color contracts; state migration stays UNKNOWN."""
    catalogs = load_catalogs(ROOT)
    es, en = catalogs["es"], catalogs["en"]
    state_es = next((x for x in es if x["key"] == "state_planned"), None)
    state_en = next((x for x in en if x["key"] == "state_planned"), None)
    snapshots = {
        repo: [{"name": x["name"], "color": x["color"]}
               for x in catalogs[REPOSITORY_LANGUAGE[repo]]]
        for repo in REPOSITORIES
    }
    snapshots["pl0n3r/Factory"][0]["color"] = "FFFFFF"
    snapshots["pl0n3r/brvtal"][0]["color"] = "FFFFFF"
    snapshots["pl0n3r/Factory"].append(
        {"name": "custom: untouched", "color": "ABCDEF"})
    plan = plan_all(snapshots, catalogs)
    assert_safe_plan(plan)
    reversal = [{**p, "color_before": p["color_after"],
                 "color_after": p["color_before"]} for p in plan]
    assert_safe_plan(reversal)
    fixed = deepcopy(snapshots)
    for operation in plan:
        for label in fixed[operation["repository"]]:
            if label["name"] == operation["label"]:
                label["color"] = operation["color_after"]
    zero_residual = plan_all(fixed, catalogs) == []

    class FixtureClient:
        def list_labels(self, repository):
            return deepcopy(snapshots[repository])

    with mock.patch("scripts.sync_label_colors.GitHubLabelsClient",
                    return_value=FixtureClient()) as client, \
         mock.patch("scripts.sync_label_colors.urlopen",
                    side_effect=AssertionError("NETWORK_FORBIDDEN")):
        dry_plan, dry_residual = execute(apply=False, token="synthetic-unused")
    no_network = client.call_args.args == (None,)
    bad_parity = deepcopy(en)
    bad_parity[0]["color"] = "FFFFFF"
    parity_rejected = rejected(lambda: validate_catalog_parity(es, bad_parity))
    missing_token = rejected(lambda: GitHubLabelsClient().update_color(plan[0]))
    bad_repo = rejected(lambda: plan_repository("pl0n3r/Unknown", [], catalogs))
    repeated = [{"name": es[0]["name"], "color": "FFFFFF"}] * 2
    bad_snapshot = rejected(lambda: plan_repository("pl0n3r/Factory", repeated, catalogs))
    bad_action = rejected(lambda: assert_safe_plan([{**plan[0], "action": "rename"}]))
    missing_repo = rejected(lambda: plan_all({"pl0n3r/Factory": []}, catalogs))
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "bad.json"
        path.write_text("[", encoding="utf-8")
        unreadable = rejected(lambda: load_catalog(path))
        path.write_text(json.dumps([{"key": "x", "name": "x", "color": "BAD"}]),
                        encoding="utf-8")
        invalid_color = rejected(lambda: load_catalog(path))

    return {
        key("L28-U1"): not (ROOT / ".github/workflows/sync-label-colors.yml").exists(),
        key("L30-U1"): (len(plan) == 2 and plan == dry_plan
                        and dry_residual == [] and no_network
                        and render_plan(plan) != "0 drifts"),
        key("L30-U2"): (zero_residual and bad_action
                        and all(p["action"] == "update_color" for p in plan)),
        key("L32-U1"): (missing_token and no_network),
        key("L36-U1"): (len(reversal) == len(plan)
                        and all(p["color_before"] != p["color_after"] for p in reversal)),
        key("L36-U2"): (
            all(set(p) == {"action", "repository", "label",
                           "color_before", "color_after"} for p in plan)
            and not any(p["label"] == "custom: untouched" for p in plan)),
        key("L38-U1"): (parity_rejected and missing_token and bad_repo
                        and bad_snapshot and bad_action and missing_repo
                        and unreadable and invalid_color),
        key("L7-U1"): (
            all(REPOSITORY_LANGUAGE[repo] == "es"
                for repo in REPOSITORIES if repo != "pl0n3r/brvtal")
            and plan_repository(
                "pl0n3r/Factory",
                [{"name": es[0]["name"], "color": "FFFFFF"}],
                catalogs)[0]["color_after"] == es[0]["color"]),
        key("L7-U2"): (
            REPOSITORY_LANGUAGE["pl0n3r/brvtal"] == "en"
            and plan_repository(
                "pl0n3r/brvtal",
                [{"name": en[0]["name"], "color": "FFFFFF"}],
                catalogs)[0]["label"] == en[0]["name"]),
        key("L8-U1"): (state_es is not None and state_en is not None
                        and state_es["color"] == state_en["color"]
                        and {p["key"]: p["color"] for p in es}
                        == {p["key"]: p["color"] for p in en}
                        and parity_rejected),
    }


def assess(matrix, document, observed):
    verdicts = {unit: UNKNOWN for unit in IDS}
    if (type(observed) is not dict
            or set(observed) != {key(u) for u in LOCALS}
            or any(type(x) is not bool for x in observed.values())):
        return verdicts
    statuses, sources = matrix_rows(matrix), document_rows(document)
    for unit in IDS:
        if (statuses[unit] == "NO_VERIFICABLE" and sources[unit] == "PRESENT"
                and observed.get(unit) is True):
            verdicts[unit] = LOCAL
    return verdicts


def external_status(_unit, _claim=None):
    return UNKNOWN


class BrechasFactory30Tests(unittest.TestCase):
    def setUp(self):
        self.matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        self.document = (ROOT / DOC).read_text(encoding="utf-8")

    def test_contrato_principal(self):
        """AC-01: every one of the 16 rows has an executable/local or UNKNOWN case."""
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        observations = local_contrasts()
        self.assertEqual(set(observations), {key(u) for u in LOCALS})
        states = matrix_rows(self.matrix)
        doc_states = document_rows(self.document)
        assessed = assess(self.matrix, self.document, observations)
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(states[unit], "NO_VERIFICABLE")
                self.assertEqual(doc_states[unit], "PRESENT")
                if unit in observations:
                    self.assertIs(observations[unit], True)
                    self.assertEqual(assessed[unit], LOCAL)
                else:
                    self.assertIn(unit.rsplit(":", 1)[-1], GAPS)
                    self.assertEqual(assessed[unit], UNKNOWN)

    def test_falla_cerrado(self):
        """AC-02: missing/duplicate/promoted/untrusted evidence stays UNKNOWN."""
        observed = local_contrasts()
        for unit in IDS:
            with self.subTest(unit=unit):
                row = next(s for s in self.matrix.splitlines()
                           if s.startswith("| " + chr(96) + unit + chr(96) + " |"))
                altered = (
                    self.matrix.replace(row, "", 1),
                    self.matrix + "\n" + row,
                    self.matrix.replace(row,
                                        row.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1),
                )
                for candidate in altered:
                    self.assertEqual(assess(candidate, self.document, observed)[unit],
                                     UNKNOWN)
                unit_id = unit.rsplit(":", 1)[-1]
                source_number = int(unit_id.split("-", 1)[0][1:])
                source_lines = self.document.splitlines()
                source_lines[source_number - 1] = ""
                self.assertEqual(assess(self.matrix, "\n".join(source_lines),
                                        observed)[unit], UNKNOWN)
        for data in (None, {}, {x: 1 for x in observed}):
            self.assertEqual(set(assess(self.matrix, self.document, data).values()),
                             {UNKNOWN})
        self.assertEqual(set(assess(None, self.document, observed).values()),
                         {UNKNOWN})

    def test_sin_datos_reales(self):
        """AC-03: no external network, credentials, personal data or apply."""
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^\s*(?:import|from)\s+(?:requests|httpx|socket|urllib|subprocess)\b")
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", own)
        self.assertFalse((ROOT / ".github/workflows/sync-label-colors.yml").exists())
        for path in (DOC, MATRIX, "labels/es.json", "labels/en.json",
                     "scripts/sync_label_colors.py"):
            self.assertTrue((ROOT / path).is_file())
        self.assertEqual(set(local_contrasts()), {key(u) for u in LOCALS})

    def test_estados_unknown_explicitos(self):
        """AC-04: offline contracts never certify CI, v1, GitHub or production."""
        observed = local_contrasts()
        decision = assess(self.matrix, self.document, observed)
        self.assertEqual({k for k, v in decision.items() if v == UNKNOWN},
                         {key(x) for x in GAPS})
        for unit in IDS:
            with self.subTest(unit=unit):
                for claim in (None, True, "success", {"ci": "success"},
                              {"pr": "MERGED"}, {"release_v1": "published"},
                              {"remote_labels": "synced"}, {"production": "healthy"}):
                    self.assertEqual(external_status(unit, claim), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
