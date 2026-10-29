"""Factory #1670: 16 fail-closed offline witnesses for human gates and Quality.

Only repository-owned deterministic functions and synthetic fixtures are
executed. A unit test is not an owner vote, consumer rollout, CI attestation,
production gate, or Sonar API response. Those external claims stay UNKNOWN.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import re
import sys
import unittest

from quality.contract import QualityContractError, validate_quality_contract
from quality.status import readiness_projection

ROOT = Path(__file__).resolve().parents[1]
for source_dir in (ROOT / "seguridad", ROOT / "tests"):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from puertas_humanas import (  # noqa: E402
    CATEGORIES, GateValidationError, classify_body, gate_identity,
    gate_target_identity, validate_gate,
)
from decision_respuesta import (  # noqa: E402
    _comment_command, _evidence_body, _existing_evidence, _gate_snapshot,
)
import test_quality_engineering_e2e as fixtures  # noqa: E402

UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_SYNTHETIC_ONLY"
GAP = "BRECHA_DOCUMENTADA"
UNITS = (
    "docs/puertas-humanas.md:B01",
    "docs/puertas-humanas.md:B02",
    "docs/puertas-humanas.md:B03",
    "docs/puertas-humanas.md:B05",
    "docs/puertas-humanas.md:B06",
    "docs/quality-contract.md:L15-U1",
    "docs/quality-contract.md:L16-U1",
    "docs/quality-contract.md:L17-U1",
    "docs/quality-contract.md:L18-U1",
    "docs/quality-contract.md:L19-U1",
    "docs/quality-contract.md:L20-U1",
    "docs/quality-contract.md:L22-U1",
    "docs/quality-contract.md:L7-U1",
    "docs/quality-engineering.md:L19-U1",
    "docs/quality-engineering.md:L31-U1",
    "docs/quality-engineering.md:L32-U1",
)
SOURCE_FILES = {
    "matrix": "docs/matriz-cobertura.md",
    "human": "docs/puertas-humanas.md",
    "quality": "docs/quality-contract.md",
    "engineering": "docs/quality-engineering.md",
    "privacy": "scripts/auditar_privacidad.py",
    "privacy_ci": ".github/workflows/auditoria-privacidad.yml",
    "gate": "seguridad/puertas_humanas.py",
    "response": "seguridad/decision_respuesta.py",
    "sync": "seguridad/sincronizar_puerta.py",
    "quality_code": "quality/contract.py",
    "status_code": "quality/status.py",
}
GAPS = {
    "docs/puertas-humanas.md:B03":
        "Identity checked locally; concurrency/serial response events in real consumers not authenticated.",
    "docs/puertas-humanas.md:B05":
        "The schema permits a nonreversible option; real safe_default requires owner evaluation.",
    "docs/puertas-humanas.md:B06":
        "Privacy audit attestation is not proof of real data absence or legal approval.",
}
EXPECTED = {
    "docs/puertas-humanas.md:B01": "categorías humanas",
    "docs/puertas-humanas.md:B02": "/decidir X",
    "docs/puertas-humanas.md:B03": "puertas equivalentes",
    "docs/puertas-humanas.md:B05": "safe_default",
    "docs/puertas-humanas.md:B06": "nothing_live",
    "docs/quality-contract.md:L15-U1": "expected_visibility",
    "docs/quality-contract.md:L16-U1": "analysis_method",
    "docs/quality-contract.md:L17-U1": "max_analysis_age_seconds",
    "docs/quality-contract.md:L18-U1": "max_organization_line_usage_percent",
    "docs/quality-contract.md:L19-U1": "max_open_vulnerabilities",
    "docs/quality-contract.md:L20-U1": "max_debt_age_days",
    "docs/quality-contract.md:L22-U1": "Sonar monitoring no configurado",
    "docs/quality-contract.md:L7-U1": "Performance",
    "docs/quality-engineering.md:L19-U1": "current",
    "docs/quality-engineering.md:L31-U1": "UNKNOWN",
    "docs/quality-engineering.md:L32-U1": "FLAKY",
}


def sources():
    return {name: (ROOT / path).read_text(encoding="utf-8")
            for name, path in SOURCE_FILES.items()}


def matrix_rows(raw):
    """Exact 16 rows, unique, unpromoted; no inferred post-merge evidence."""
    if type(raw) is not str or not raw.strip():
        raise ValueError(UNKNOWN + ": matrix missing")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in line.strip("|").split(" | "))
        if not cells:
            continue
        key = cells[0].strip("\x60 ")
        if key not in UNITS:
            continue
        if (key in found or len(cells) != 5
                or cells[0] != "\x60" + key + "\x60"
                or cells[2] != "NO_VERIFICABLE"
                or not cells[1] or EXPECTED[key].casefold() not in (
                    cells[1] + " " + cells[3]).casefold()
                or "Contraste" not in cells[3] and "Candidato" not in cells[3]
                or cells[4] != "—"):
            raise ValueError(UNKNOWN + ": ambiguous/promoted " + key)
        found[key] = cells
    if set(found) != set(UNITS):
        raise ValueError(UNKNOWN + ": missing " + str(sorted(set(UNITS) - set(found))))
    return found


def gate_value():
    return {
        "category": "legal",
        "context": "Escoger el método de prueba sin activar servicios reales.",
        "options": [
            {"id": "A", "label": "No iniciar", "reversible": True},
            {"id": "B", "label": "Preparar", "reversible": False},
        ],
        "recommendation": "A",
        "safe_default": "A",
    }


def gate_body(gate):
    return "Contexto de prueba\n<!-- factory-human-gate " + json.dumps(
        gate, separators=(",", ":"), ensure_ascii=False
    ) + " -->"


def event(command="/decidir A", association="OWNER", bot=False):
    return {
        "issue": {"number": 1, "body": gate_body(gate_value())},
        "comment": {"body": command, "author_association": association,
                    "user": {"login": "synthetic-owner",
                             "type": "Bot" if bot else "User"}},
    }


def sonar_policy():
    return {
        "expected_visibility": "public",
        "analysis_method": "ci",
        "max_analysis_age_seconds": 86400,
        "max_organization_line_usage_percent": 80,
        "max_open_vulnerabilities": 0,
        "max_open_bugs": 4,
        "max_open_hotspots": 0,
        "max_debt_age_days": 30,
    }


def quality_payload():
    return fixtures.quality_contract()


def contract_probe():
    """Actual validator; independent per-field negative cases."""
    base = quality_payload()
    base["sonar"] = sonar_policy()
    normalized = validate_quality_contract(base)
    policy = normalized["sonar"]
    result = {}
    checks = {
        "L15-U1": ("expected_visibility", "unknown"),
        "L16-U1": ("analysis_method", "hybrid"),
        "L17-U1": ("max_analysis_age_seconds", 0),
        "L18-U1": ("max_organization_line_usage_percent", 101),
        "L19-U1": ("max_open_bugs", -1),
        "L20-U1": ("max_debt_age_days", -1),
    }
    for unit, (field, rejected) in checks.items():
        altered = copy.deepcopy(base)
        altered["sonar"][field] = rejected
        try:
            validate_quality_contract(altered)
            invalid_rejected = False
        except QualityContractError:
            invalid_rejected = True
        result["docs/quality-contract.md:" + unit] = (
            policy[field] == sonar_policy()[field] and invalid_rejected
        )
    all_debt_rejected = True
    for field in ("max_open_vulnerabilities", "max_open_bugs", "max_open_hotspots"):
        altered = copy.deepcopy(base)
        altered["sonar"][field] = -1
        try:
            validate_quality_contract(altered)
            all_debt_rejected = False
        except QualityContractError:
            pass
    result["docs/quality-contract.md:L19-U1"] &= all_debt_rejected
    no_sonar = validate_quality_contract(quality_payload())
    result["docs/quality-contract.md:L22-U1"] = (
        "sonar" not in no_sonar and "sonar" not in quality_payload()
        and "sonar" in normalized
    )
    dimension = no_sonar["dimensions"]
    result["docs/quality-contract.md:L7-U1"] = (
        dimension["performance"] == {
            "required": True, "source_ref": "pl0n3r/Factory#304",
        } and dimension["recovery"] == {
            "required": True, "source_ref": "pl0n3r/Factory#305",
        } and all(set(dimension[name]) == {"required", "source_ref"}
                  for name in ("performance", "recovery"))
    )
    return result


def human_probe():
    raw = gate_value()
    normalized = validate_gate(raw)
    invalid = copy.deepcopy(raw)
    invalid["category"] = "unlisted"
    try:
        validate_gate(invalid)
        rejected = False
    except GateValidationError:
        rejected = True
    body = gate_body(raw)
    options, fingerprint = _gate_snapshot(body)
    journal = _evidence_body("B", fingerprint)
    record = json.loads(
        journal.split("-->", 1)[0].removeprefix(
            "<!-- factory-human-decision "
        )
    )
    def fake_api(method, path, payload=None):
        if method == "GET" and path.endswith("/comments?per_page=100"):
            return [{"user": {"login": "github-actions[bot]"},
                     "body": journal}]
        raise AssertionError("unexpected external API request")

    modified = copy.deepcopy(raw)
    modified["context"] += " Cambio sintético de alcance."
    _, different = _gate_snapshot(gate_body(modified))
    equivalent = copy.deepcopy(raw)
    equivalent["context"] = "  Escoger el método de prueba sin activar servicios reales.  "
    other = copy.deepcopy(raw)
    other["context"] = "Escoger otro método de prueba."
    duplicate_identity = (
        gate_target_identity(raw) == gate_target_identity(equivalent)
        and gate_identity(raw) == gate_identity(equivalent)
        and gate_identity(raw) != gate_identity(other)
    )
    return {
        "docs/puertas-humanas.md:B01": (
            normalized["category"] in CATEGORIES and rejected
            and classify_body(body)["status"] == "gate"
            and classify_body(body + body)["status"] == "invalid-gate"
            and _comment_command(event()) == "A"
            and _comment_command(event(association="COLLABORATOR")) is None
            and _comment_command(event(bot=True)) is None
        ),
        "docs/puertas-humanas.md:B02": (
            options == {"A", "B"} and record["version"] == 2
            and record["option"] == "B"
            and record["gate_sha256"] == fingerprint
            and _existing_evidence(fake_api, "repos/example/issues/1")
                == ("B", fingerprint)
            and fingerprint != different
            and "sin ejecutar el efecto" in journal
            and _comment_command(event(command=" /decidir A")) is None
        ),
        "docs/puertas-humanas.md:B03": duplicate_identity,
        "docs/puertas-humanas.md:B05": (
            normalized["safe_default"] == "A"
            and normalized["options"][0]["reversible"] is True
            and normalized["options"][1]["reversible"] is False
        ),
        "docs/puertas-humanas.md:B06": True,  # evidence-source gate below
    }


def quality_health_probe():
    healthy = fixtures.derive(fixtures.gate_evidence(), [fixtures.regression()])
    current = (healthy["state"] == "PASS"
               and readiness_projection(healthy)["ready"] is True
               and readiness_projection(healthy)["recalculated"] is False)
    stale = fixtures.derive(
        fixtures.gate_evidence(observed_at="2026-09-29T00:00:00Z"), []
    )
    missing = fixtures.derive(fixtures.gate_evidence()[:-1], [])
    flaky = fixtures.derive(
        fixtures.gate_evidence(), [fixtures.regression(before_failures=1)]
    )
    return {
        "docs/quality-engineering.md:L19-U1": current,
        "docs/quality-engineering.md:L31-U1": (
            stale["state"] == missing["state"] == UNKNOWN
            and not readiness_projection(stale)["ready"]
            and not readiness_projection(missing)["ready"]
        ),
        "docs/quality-engineering.md:L32-U1": (
            flaky["state"] == "DEGRADED"
            and not readiness_projection(flaky)["ready"]
            and "quality_regression_flaky" in flaky["work_item_classes"]
        ),
    }


def evidence_by_unit(data):
    if type(data) is not dict or set(data) != set(SOURCE_FILES) or any(
        type(value) is not str or not value for value in data.values()
    ):
        return {key: UNKNOWN for key in UNITS}
    try:
        matrix_rows(data["matrix"])
    except ValueError:
        return {key: UNKNOWN for key in UNITS}
    tests = {**human_probe(), **contract_probe(), **quality_health_probe()}
    docs = {
        "docs/puertas-humanas.md": data["human"],
        "docs/quality-contract.md": data["quality"],
        "docs/quality-engineering.md": data["engineering"],
    }
    result = {}
    for key in UNITS:
        filename = key.split(":")[0]
        doc = docs[filename]
        marker = ("categorías cerradas" if key == "docs/puertas-humanas.md:B01"
                  else EXPECTED[key])
        if marker.casefold() not in doc.casefold():
            result[key] = UNKNOWN
        elif key == "docs/puertas-humanas.md:B06":
            result[key] = GAP if (
                "d063_attestation" in data["privacy"]
                and "nothing_live" in data["privacy"]
                and "no_real_customer_data" in data["privacy"]
                and "auditar_privacidad.py" in data["privacy_ci"]
            ) else UNKNOWN
        elif tests.get(key) is True:
            result[key] = GAP if key in GAPS else LOCAL
        else:
            result[key] = UNKNOWN
    return result


def operational(_key, _candidate=None):
    """Never infer consumer rollout, OWNER consent or production from local tests."""
    return UNKNOWN


class BrechasFactory52Tests(unittest.TestCase):
    def test_contrato_principal(self):
        data = sources()
        observed = evidence_by_unit(data)
        self.assertEqual(16, len(UNITS))
        self.assertEqual(set(UNITS), set(matrix_rows(data["matrix"])))
        self.assertEqual(set(UNITS), set(observed))
        for key in UNITS:
            with self.subTest(unit=key):
                self.assertEqual(GAP if key in GAPS else LOCAL, observed[key])
                self.assertEqual(UNKNOWN, operational(key, observed[key]))

    def test_falla_cerrado(self):
        data = sources()
        raw = data["matrix"]
        for key in UNITS:
            line = next(row for row in raw.splitlines()
                        if row.startswith("| \x60" + key + "\x60 |"))
            for corrupt in (
                raw.replace(line, "", 1),
                raw + "\n" + line,
                raw.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(unit=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(corrupt)
                    self.assertTrue(all(value == UNKNOWN for value in
                        evidence_by_unit({**data, "matrix": corrupt}).values()))
        for filename in SOURCE_FILES:
            altered = copy.deepcopy(data)
            altered[filename] = ""
            self.assertTrue(all(value == UNKNOWN
                for value in evidence_by_unit(altered).values()))
        malformed = quality_payload()
        malformed["sonar"] = sonar_policy()
        for value in (None, "any", -1):
            variant = copy.deepcopy(malformed)
            variant["sonar"]["max_open_bugs"] = value
            with self.assertRaises(QualityContractError):
                validate_quality_contract(variant)
        for corrupt in ({"ci": "success"}, None, {}):
            self.assertEqual(UNKNOWN, operational(UNITS[0], corrupt))
        with self.assertRaises(GateValidationError):
            validate_gate({**gate_value(), "safe_default": "C"})

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports.update(node.module.split(".")[0] for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom) and node.module)
        self.assertFalse(imports & {"requests", "httpx", "socket", "urllib",
                                    "subprocess", "playwright", "pymysql"})
        self.assertEqual(set(SOURCE_FILES), set(sources()))
        self.assertTrue(all((ROOT / path).is_file() for path in SOURCE_FILES.values()))
        self.assertNotIn("GH_TOKEN", str(sonar_policy()))
        self.assertNotIn("Authorization", gate_body(gate_value()))
        self.assertTrue(all(operational(key) == UNKNOWN for key in UNITS))

    def test_estados_unknown_explicitos(self):
        seen = evidence_by_unit(sources())
        for key in UNITS:
            with self.subTest(unit=key):
                self.assertIn(seen[key], {LOCAL, GAP})
                for claim in (None, True, {"ci": "success"}, {"owner": "approved"},
                              {"sonar": "GREEN"}, {"production": True}):
                    self.assertEqual(UNKNOWN, operational(key, claim))
                self.assertEqual("NO_VERIFICABLE",
                    matrix_rows(sources()["matrix"])[key][2])
        for key, reason in GAPS.items():
            self.assertIn(" ", reason)
            self.assertEqual(GAP, seen[key])


if __name__ == "__main__":
    unittest.main()
