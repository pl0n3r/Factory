"""Factory #1644: 16 contrapruebas offline para Knowledge Lifecycle / Operations.

Las aserciones prueban contratos locales con datos sintéticos; no constituyen
evidencia de producción, una aprobación humana ni un PR fusionado.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    KnowledgeLifecycleError,
    can_increase_autonomy,
    create_knowledge_record,
    effective_state,
    propose_pruning_candidates,
    revalidate_knowledge,
    transition_knowledge,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
LIFECYCLE = "docs/knowledge-lifecycle.md"
OPERATIONS = "docs/knowledge-operations-e2e.md"
NOW = "2026-09-28T00:00:00Z"
NEXT = "2026-09-29T00:00:00Z"
LATER = "2026-10-01T00:00:00Z"
UNKNOWN = "UNKNOWN"
LOCAL = "OFFLINE_CONTRACT_ONLY"

CLAUSES = (
    f"{LIFECYCLE}:L30-U1",
    f"{LIFECYCLE}:L30-U2",
    f"{LIFECYCLE}:L30-U3",
    f"{LIFECYCLE}:L30-U4",
    f"{LIFECYCLE}:L30-U5",
    f"{LIFECYCLE}:L30-U6",
    f"{LIFECYCLE}:L30-U7",
    f"{LIFECYCLE}:L36-U1",
    f"{LIFECYCLE}:L37-U1",
    f"{LIFECYCLE}:L38-U1",
    f"{LIFECYCLE}:L40-U1",
    f"{LIFECYCLE}:L40-U2",
    f"{LIFECYCLE}:L42-U1",
    f"{LIFECYCLE}:L9-U1",
    f"{OPERATIONS}:L13-U1",
    f"{OPERATIONS}:L14-U1",
)


def fixture(name="rule-alpha", *, fingerprint="a" * 64,
            source="pl0n3r/Factory#319@rev:old", state="active",
            validated="2026-01-01T00:00:00Z", useful=None):
    """Identidades ficticias, fechas fijas y ningún proveedor externo."""
    return create_knowledge_record(
        knowledge_id=name, knowledge_type="guardrail",
        content_fingerprint=fingerprint, provenance=[source],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge-lifecycle"},
        created_at="2025-01-01T00:00:00Z",
        last_validated_at=validated, last_useful_at=useful or validated,
        confidence=0.90, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


def rejected(operation) -> bool:
    try:
        operation()
    except KnowledgeLifecycleError:
        return True
    return False


def matrix_rows(raw: object) -> dict[str, str]:
    """La ausencia, duplicación o promoción unilateral falla cerrado."""
    if not isinstance(raw, str):
        raise ValueError("Matriz ilegible")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        key = cells[0].strip("`")
        if key not in CLAUSES:
            continue
        if key in found or len(cells) != 5 or any(not c for c in cells):
            raise ValueError(f"Fila ambigua: {key}")
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError(f"Promoción sin evidencia: {key}")
        if "Contraste #1571" not in cells[3]:
            raise ValueError(f"Falta procedencia en {key}")
        found[key] = cells[2]
    if set(found) != set(CLAUSES):
        raise ValueError("Faltan unidades contratadas")
    return found


def assess(matrix: object, proof: object) -> dict[str, str]:
    """La verificación local nunca se convierte en estatus operativo."""
    result = {key: UNKNOWN for key in CLAUSES}
    try:
        matrix_rows(matrix)
    except ValueError:
        return result
    if type(proof) is not dict or set(proof) != set(CLAUSES):
        return result
    if any(type(v) is not bool for v in proof.values()):
        return result
    return {key: LOCAL if proof[key] else UNKNOWN for key in CLAUSES}


def offline_contrast() -> dict[str, bool]:
    """Un predicado por unidad, probado contra implementación real sin I/O."""
    old = fixture()
    same_ref = "pl0n3r/Factory#319"
    new_rev = f"{same_ref}@rev:new"
    refreshed = revalidate_knowledge(
        old, validated_at=NOW, evidence=[new_rev],
        confidence=0.97, evidence_class="verified",
    )
    simple = revalidate_knowledge(
        old, validated_at=NOW, evidence=[same_ref],
        confidence=0.95, evidence_class="verified",
    )
    sha = revalidate_knowledge(
        old, validated_at=NOW, evidence=[f"{same_ref}@sha256:{'b' * 64}"],
        confidence=0.95, evidence_class="verified",
    )
    event = revalidate_knowledge(
        old, validated_at=NOW, evidence=[f"{same_ref}@event:verification-2"],
        confidence=0.95, evidence_class="verified",
    )
    original = deepcopy(old)
    replay_rejected = rejected(lambda: revalidate_knowledge(
        old, validated_at=NOW, evidence=[old["provenance"][0]],
        confidence=0.95, evidence_class="verified",
    ))
    empty_rejected = rejected(lambda: revalidate_knowledge(
        old, validated_at=NOW, evidence=[],
        confidence=0.95, evidence_class="verified",
    ))
    deprecated = transition_knowledge(
        old, target_state="deprecated", at=NOW,
        evidence=["pl0n3r/Factory#320@event:superseded"],
        reason="superseded",
    )
    archived = transition_knowledge(
        deprecated, target_state="archived", at=NEXT,
        evidence=["pl0n3r/Factory#320@event:archived"],
        reason="audit-retention",
    )
    retired_deny = all(rejected(lambda item=item: revalidate_knowledge(
        item, validated_at=LATER,
        evidence=["pl0n3r/Factory#320@event:new-evidence"],
        confidence=0.99, evidence_class="verified",
    )) for item in (deprecated, archived))
    proposal = fixture(
        "rule-successor", source="pl0n3r/Factory#321@event:new-proposal",
        state="candidate", validated=NEXT,
    )
    candidate = fixture("rule-candidate", state="candidate", validated=NEXT)

    duplicate_a = fixture("rule-dupe-a", fingerprint="c" * 64,
                          validated=NEXT)
    duplicate_b = fixture("rule-dupe-b", fingerprint="c" * 64,
                          validated=NEXT)
    duplicate = propose_pruning_candidates(
        [duplicate_a, duplicate_b], now_at=LATER)
    unused = propose_pruning_candidates([
        fixture("rule-unused", fingerprint="d" * 64,
                validated=NEXT, useful="2026-01-01T00:00:00Z"),
    ], now_at=LATER)
    aged = propose_pruning_candidates([
        fixture("rule-aged", fingerprint="e" * 64,
                validated="2026-01-01T00:00:00Z", useful=NEXT),
    ], now_at=LATER)
    all_pruning = duplicate + unused + aged

    lessons = [{
        "id": f"lesson-1644-{n}",
        "project": "pl0n3r/factory", "kind": "process",
        "occurred_at": f"2026-09-0{n}T00:00:00Z",
        "what": "Repeated synthetic contract drift",
        "why": "Lifecycle revalidation was not checked",
        "prevention": "Require verification of evidence identity",
        "source": f"pl0n3r/factory#{321+n}",
    } for n in (1, 2)]
    guardrails = compile_guardrail_candidates(lessons)
    pending = guardrails[0] if len(guardrails) == 1 else {}
    draft_guardrail = pending.get("candidate", {}).get("changes", [])
    guardrail_value = draft_guardrail[0].get("value", {}) if draft_guardrail else {}

    return {
        f"{LIFECYCLE}:L30-U1": empty_rejected and (
            new_rev in refreshed["provenance"]),
        f"{LIFECYCLE}:L30-U2": all(
            len(value["history"]) >= 1 and value["state"] == "active"
            for value in (simple, sha, event)),
        f"{LIFECYCLE}:L30-U3": (
            set(refreshed["provenance"]) ==
            {f"{same_ref}@rev:old", f"{same_ref}@rev:new"} and
            len(refreshed["provenance"]) == 2),
        f"{LIFECYCLE}:L30-U4": (
            replay_rejected and old == original and
            old["last_validated_at"] == "2026-01-01T00:00:00Z"),
        f"{LIFECYCLE}:L30-U5": (
            refreshed["last_validated_at"] == NOW and
            refreshed["last_useful_at"] == NOW and
            refreshed["confidence"] == 0.97 and
            refreshed["evidence_class"] == "verified" and
            refreshed["history"][-1]["reason"] == "revalidated" and
            refreshed["history"][-1]["to"] == "active" and
            refreshed["history"][-1]["evidence"] == [new_rev]),
        f"{LIFECYCLE}:L30-U6": (
            retired_deny and deprecated["state"] == "deprecated" and
            archived["state"] == "archived"),
        f"{LIFECYCLE}:L30-U7": (
            retired_deny and proposal["knowledge_id"] != old["knowledge_id"]
            and proposal["state"] == "candidate" and
            not can_increase_autonomy(proposal, LATER)),
        f"{LIFECYCLE}:L36-U1": (
            len(duplicate) == 1 and
            duplicate[0]["knowledge_ids"] == ["rule-dupe-a", "rule-dupe-b"]
            and "duplicate" in duplicate[0]["reasons"]),
        f"{LIFECYCLE}:L37-U1": (
            len(unused) == 1 and
            unused[0]["reasons"] == ["unused"]),
        f"{LIFECYCLE}:L38-U1": (
            len(aged) == 1 and aged[0]["reasons"] == ["aged"]),
        f"{LIFECYCLE}:L40-U1": (
            len(all_pruning) == 3 and
            duplicate[0]["action"] == "review-consolidation" and
            unused[0]["action"] == "review-retirement" and
            aged[0]["action"] == "review-retirement"),
        f"{LIFECYCLE}:L40-U2": (
            all(p["delete"] is False and p["history_preserved"] is True
                and "delete" not in p["action"] for p in all_pruning)),
        f"{LIFECYCLE}:L42-U1": (
            not can_increase_autonomy(old, NOW) and
            can_increase_autonomy(refreshed, NOW) and
            old["provenance"][0] in refreshed["provenance"] and
            len(refreshed["history"]) > len(old["history"])),
        f"{LIFECYCLE}:L9-U1": (
            effective_state(candidate, LATER) == "candidate" and
            not can_increase_autonomy(candidate, LATER)),
        f"{OPERATIONS}:L13-U1": (
            bool(draft_guardrail) and
            guardrail_value.get("status") == "candidate" and
            "promoted" not in pending and
            not can_increase_autonomy(proposal, LATER)),
        f"{OPERATIONS}:L14-U1": (
            bool(all_pruning) and
            all(p["delete"] is False and p["history_preserved"] is True
                for p in all_pruning)),
    }


class BrechasFactory26Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: las 16 cláusulas tienen una aserción offline ejecutable."""
        matrix = MATRIX.read_text(encoding="utf-8")
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(len(set(CLAUSES)), 16)
        self.assertEqual(set(matrix_rows(matrix)), set(CLAUSES))
        evidence = offline_contrast()
        self.assertEqual(set(evidence), set(CLAUSES))
        for unit in CLAUSES:
            with self.subTest(unit=unit):
                self.assertIs(evidence[unit], True, f"{unit}: regresión sin cubrir")
                self.assertEqual(assess(matrix, evidence)[unit], LOCAL)
                self.assertTrue((ROOT / unit.split(":")[0]).is_file())

    def test_falla_cerrado(self):
        """AC-02: evidencia parcial, repetida, falsa o malformada es UNKNOWN."""
        matrix = MATRIX.read_text(encoding="utf-8")
        one = next(line for line in matrix.splitlines()
                   if line.startswith(f"| `{CLAUSES[0]}` |"))
        for invalid in (None, "", matrix.replace(one, "", 1),
                        matrix + "\n" + one,
                        matrix.replace(one, one.replace(
                            "NO_VERIFICABLE", "CUBIERTO", 1), 1)):
            with self.subTest(invalid=repr(invalid)[:36]):
                self.assertEqual(set(assess(invalid, offline_contrast()).values()),
                                 {UNKNOWN})
        valid = offline_contrast()
        for invalid in (None, {}, {CLAUSES[0]: True},
                        {k: 1 for k in CLAUSES},
                        {**valid, "extra": True}):
            self.assertEqual(set(assess(matrix, invalid).values()), {UNKNOWN})
        for unit in CLAUSES:
            with self.subTest(unit=unit):
                self.assertEqual(assess(matrix, {**valid, unit: False})[unit], UNKNOWN)

    def test_sin_datos_reales(self):
        """AC-03: solo fixtures; sin red, PII, secretos ni side-effects."""
        self.assertEqual(fixture()["scope"]["project"], "pl0n3r/Factory")
        self.assertTrue(all(
            f["delete"] is False for f in propose_pruning_candidates(
                [fixture("rule-test", validated="2026-01-01T00:00:00Z")],
                now_at=NOW)))
        code = (ROOT / "tests/test_brechas_factory_26.py").read_text(
            encoding="utf-8")
        tree = ast.parse(code)
        forbidden = {"requests", "urllib", "socket", "subprocess", "httpx",
                     "os", "smtplib"}
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(imports & forbidden)
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", code)
        self.assertFalse(any(k in fixture()
                             for k in ("password", "token", "email", "dsn")))

    def test_estados_unknown_explicitos(self):
        """AC-04: CI, producto y autoridad externa nunca son inferidos."""
        matrix = MATRIX.read_text(encoding="utf-8")
        proof = offline_contrast()
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual(matrix_rows(matrix)[key], "NO_VERIFICABLE")
                self.assertNotEqual(assess(matrix, proof)[key], "PRODUCTION_GREEN")
                for claim in (None, True, "success", {"ci": "success"},
                              {"approval": "claimed"}, {"release": "merged"}):
                    self.assertEqual(operational_status(key, claim), UNKNOWN)


def operational_status(_key: str, _claim: object = None) -> str:
    """Esta hoja no observa producción ni decide autoridad."""
    return UNKNOWN


if __name__ == "__main__":
    unittest.main()
