"""Issue #1797: aserciones conductuales sin red ni datos reales.

Las cuatro citas de conversación son ejemplos, no contratos ejecutables.
No se inspecciona el estado de la matriz de cobertura.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import unittest
from unittest.mock import patch
from evolution.autonomy import AUTONOMY_LEVELS
from evolution.capability_authority import CapabilityAuthorityError, CapabilityAuthorityRegistry
from evolution.provenance import TrustedDecisionSource, authenticated_decision_reader_from_environment
from intelligence.context_compiler import (
    ContextCompilerError, MAX_CONTEXT_ITEMS, MAX_ITEM_CHARS,
    MAX_PACKAGE_CHARS, compile_mission_context,
)
from intelligence.project_dna import discover_project_dna

def stable_hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def decision(
    *,
    operation="grant",
    capability="deploy-observer",
    actions=("observe", "propose"),
    scopes=("project:brvtal",),
    targets=("production",),
    authority_class="operational",
    degrade_on=("fitness-regression",),
    revoke_on=("critical-incident",),
    actor_ref="decision:owner#1",
    reason="explicit reviewed authority",
    grant_id="",
):
    raw = {
        "version": 1,
        "operation": operation,
        "capability": capability,
        "actions": list(actions),
        "scopes": list(scopes),
        "targets": list(targets),
        "authority_class": authority_class,
        "degrade_on": list(degrade_on),
        "revoke_on": list(revoke_on),
        "actor_ref": actor_ref,
        "reason": reason,
        "status": "resolved",
        "grant_id": grant_id,
    }
    raw["fingerprint"] = stable_hash(raw)
    return raw


def authenticated_source(records):
    env = {
        "FACTORY_DECISION_SOURCE_ID": "controlbot:test-decisions",
        "FACTORY_DECISION_SOURCE_URL": "https://controlbot.example/decisions",
        "FACTORY_PROVENANCE_TOKEN": "test-token",
    }
    with patch.dict(os.environ, env, clear=False), patch(
        "evolution.provenance._fetch_json", return_value=records
    ):
        return authenticated_decision_reader_from_environment()


def grant_decision(*, decision_ref="owner-decision:factory#246:grant", **kwargs):
    raw = decision(**kwargs)
    normalized = {
        "capability": raw["capability"],
        "actions": tuple(sorted(raw["actions"])),
        "scopes": tuple(sorted(raw["scopes"])),
        "targets": tuple(sorted(raw["targets"])),
        "authority_class": raw["authority_class"],
        "human_gate": raw["authority_class"] != "operational",
        "degrade_on": tuple(sorted(raw["degrade_on"])),
        "revoke_on": tuple(sorted(raw["revoke_on"])),
        "reason": raw["reason"],
    }
    ref = decision_ref
    raw["grant_id"] = stable_hash(
        {
            **normalized,
            "decision_ref": ref,
            "source_id": "controlbot:test-decisions",
            "actor_ref": raw["actor_ref"],
        }
    )
    unsigned = dict(raw)
    unsigned.pop("fingerprint")
    raw["fingerprint"] = stable_hash(unsigned)
    return ref, raw



def dna():
    return discover_project_dna(
        paths=["package.json", ".github/workflows/ci.yml"],
        manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
        capabilities=["api"],
    )


def task():
    return {
        "id": "factory#147",
        "title": "Context Compiler",
        "goal": "compile minimal mission context",
        "tags": ["context", "living"],
    }




def item(n, *, category="lesson", tags=("context",), text=None):
    return {"category": category, "source": f"fixture:synthetic-{n:02}",
            "text": text if text is not None else f"Synthetic {n}",
            "tags": list(tags)}


class CoberturaFactory06Tests(unittest.TestCase):
    """AC-01, AC-02 y AC-03 invocan funciones reales."""

    def test_contrato_principal(self):
        # capability-authority L18/L21/L22: bindings exactos; no cartesiano.
        a, ra = grant_decision(
            decision_ref="decision:synthetic-a", actions=("execute",),
            scopes=("project:alpha",), targets=("staging",))
        b, rb = grant_decision(
            decision_ref="decision:synthetic-b", actions=("execute",),
            scopes=("project:beta",), targets=("production",))
        registry = CapabilityAuthorityRegistry()
        registry.grant(a, decision_source=authenticated_source({a: ra}))
        registry.grant(b, decision_source=authenticated_source({b: rb}))
        row = registry.matrix("deploy-observer")["actions"]["execute"]
        self.assertEqual(row["scopes"], ["project:alpha", "project:beta"])
        self.assertEqual(row["targets"], ["production", "staging"])
        self.assertEqual(
            {(tuple(x["scopes"]), tuple(x["targets"])) for x in row["bindings"]},
            {(("project:alpha",), ("staging",)),
             (("project:beta",), ("production",))})
        for scope, target, ok in (
            ("project:alpha", "staging", True),
            ("project:beta", "production", True),
            ("project:alpha", "production", False),
            ("project:beta", "staging", False),
        ):
            self.assertIs(registry.authorize("deploy-observer", "execute", scope, target), ok)

        # capability-authority L26: fuente inmutable autenticada; revocación efectiva.
        caller = TrustedDecisionSource("caller-fixture")
        caller.record_decision(a, ra)
        with self.assertRaises(CapabilityAuthorityError):
            CapabilityAuthorityRegistry().grant(a, decision_source=caller)
        rev_ref = "decision:synthetic-revoke"
        rev = decision(operation="revoke", actions=("execute",),
                       scopes=("project:alpha",), targets=("staging",),
                       grant_id=ra["grant_id"])
        registry.revoke(ra["grant_id"], rev_ref,
                        decision_source=authenticated_source({rev_ref: rev}))
        self.assertFalse(registry.authorize("deploy-observer", "execute",
                                            "project:alpha", "staging"))
        self.assertTrue(registry.authorize("deploy-observer", "execute",
                                           "project:beta", "production"))
        self.assertEqual(registry.history[-1].event, "revoke")
        self.assertEqual(registry.history[-1].source_id, "controlbot:test-decisions")

        # capability-authority L39/L42: niveles autónomos no conceden permisos.
        first = registry.autonomy_scope("deploy-observer", AUTONOMY_LEVELS[0])
        for level in AUTONOMY_LEVELS:
            current = registry.autonomy_scope("deploy-observer", level)
            self.assertEqual(current["authority"], first["authority"])
            self.assertEqual(current["fingerprint"], first["fingerprint"])
            self.assertFalse(registry.authorize("deploy-observer",
                                                "promote_adopt", "project:beta", "production"))

        # context-compiler L4/L11-L15: DNA, task, contexto, fuente, límites y SHA.
        project, mission = dna(), task()
        dec, lesson, other = item(1, category="decision"), item(2), item(3, tags=("none",))
        result = compile_mission_context(
            project_dna=project, task=mission, context_items=[other, lesson, dec])
        self.assertEqual(result["project_dna"], project)
        self.assertEqual(result["task"], mission)
        self.assertEqual(result["context"], [dec, lesson])
        self.assertEqual([x["source"] for x in result["context"]],
                         [dec["source"], lesson["source"]])
        self.assertEqual(result["limits"], {
            "max_context_items": MAX_CONTEXT_ITEMS,
            "max_item_chars": MAX_ITEM_CHARS,
            "max_package_chars": MAX_PACKAGE_CHARS})
        self.assertEqual(result["fingerprint"], stable_hash(
            {key: value for key, value in result.items() if key != "fingerprint"}))
        self.assertEqual(result, compile_mission_context(
            project_dna=project, task=mission, context_items=[dec, other, lesson]))

        # context-compiler L32/L33: 12 items, 1200 chars, selección determinista.
        many = [item(i, text="x" * 800) for i in range(MAX_CONTEXT_ITEMS + 5)]
        bound = compile_mission_context(
            project_dna=project, task=mission, context_items=many)
        self.assertEqual(len(bound["context"]), MAX_CONTEXT_ITEMS)
        self.assertEqual(bound, compile_mission_context(
            project_dna=project, task=mission, context_items=list(reversed(many))))
        truncated = compile_mission_context(project_dna=project, task=mission,
            context_items=[item(99, text="x" * (MAX_ITEM_CHARS + 3))])
        self.assertEqual(len(truncated["context"][0]["text"]), MAX_ITEM_CHARS)

        # context-compiler L35: sin I/O, sin mutar input, sin evaluar riesgo.
        before = copy.deepcopy((project, mission, [dec]))
        with patch("builtins.open", side_effect=AssertionError("unexpected IO")), patch(
            "socket.socket.connect", side_effect=AssertionError("unexpected network")):
            pure = compile_mission_context(
                project_dna=project, task=mission, context_items=[dec])
        self.assertEqual(before, (project, mission, [dec]))
        self.assertNotIn("risk", pure)
        self.assertNotIn("authority", pure)

    def test_falla_cerrado(self):
        ref, raw = grant_decision(
            decision_ref="decision:synthetic-negative", actions=("execute",),
            scopes=("project:alpha",), targets=("staging",))
        reg = CapabilityAuthorityRegistry()
        reg.grant(ref, decision_source=authenticated_source({ref: raw}))
        for action, scope, target in (
            ("execute", "project:alpha", "production"),
            ("execute", "project:beta", "staging"),
            ("promote_adopt", "project:alpha", "staging"),
            ("delete", "project:alpha", "staging"),
        ):
            self.assertFalse(reg.authorize("deploy-observer", action, scope, target))
        with self.assertRaises(CapabilityAuthorityError):
            reg.autonomy_scope("deploy-observer", "superuser")
        altered = copy.deepcopy(raw)
        altered["targets"] = ["production"]
        with self.assertRaises(CapabilityAuthorityError):
            CapabilityAuthorityRegistry().grant(
                ref, decision_source=authenticated_source({ref: altered}))
        with self.assertRaises(CapabilityAuthorityError):
            CapabilityAuthorityRegistry().grant(ref, decision_source=None)
        revoke_ref = "decision:synthetic-untrusted"
        revoke = decision(operation="revoke", actions=("execute",),
                          scopes=("project:alpha",), targets=("staging",),
                          grant_id=raw["grant_id"])
        caller = TrustedDecisionSource("mutable-revoke")
        caller.record_decision(revoke_ref, revoke)
        with self.assertRaises(CapabilityAuthorityError):
            reg.revoke(raw["grant_id"], revoke_ref, decision_source=caller)
        self.assertTrue(reg.authorize("deploy-observer", "execute", "project:alpha", "staging"))

        project, mission = dna(), task()
        corrupted = copy.deepcopy(project)
        corrupted["fingerprint"] = "0" * 64
        for p, t, items in (
            (corrupted, mission, []),
            (project, {"id": mission["id"], "goal": mission["goal"],
                       "tags": mission["tags"]}, []),
            (project, mission, [{**item(1), "category": "unknown"}]),
            (project, mission, [{**item(1), "tags": "context"}]),
            (project, mission, [{**item(1), "source": ""}]),
        ):
            with self.assertRaises(ValueError):
                compile_mission_context(project_dna=p, task=t, context_items=items)
        # context-compiler L34: abortar si excede límite serializado.
        with self.assertRaisesRegex(ContextCompilerError, "límite"):
            compile_mission_context(project_dna=project, task=mission,
                context_items=[item(i, text="x" * MAX_ITEM_CHARS)
                               for i in range(MAX_CONTEXT_ITEMS)])

    def test_sin_datos_reales(self):
        project, mission = dna(), task()
        email, phone = "nobody@example.invalid", "+00 123 456 7890"
        output = compile_mission_context(project_dna=project, task=mission,
            context_items=[item(1, text=f"Contact {email} or {phone}")])
        encoded = json.dumps(output)
        self.assertNotIn(email, encoded)
        self.assertNotIn(phone, encoded)
        self.assertIn("[REDACTED]", encoded)
        with self.assertRaises(ContextCompilerError):
            compile_mission_context(project_dna=project, task=mission,
                context_items=[{**item(2), "token": "synthetic-placeholder"}])
        with self.assertRaises(ContextCompilerError):
            compile_mission_context(project_dna=project,
                task={**mission, "password": "synthetic-placeholder"},
                context_items=[])


if __name__ == "__main__":
    unittest.main()
