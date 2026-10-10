"""Offline tests for Factory #1109, without real consumer data or external I/O."""
import json
import unittest

from scripts.plan_sync_agentes_consumidores import (
    REPOSITORIES, SyncPlanError, _principles, _render_consumer, plan_sync,
)


def template():
    headings = "\n".join(["### Regla 0 — alcance seguro", "paralelismo con límites"]
                         + [f"### Principio {n} — ejemplo" for n in range(1, 9)])
    return ("# AGENTES.md\n\nEsta plantilla no otorga permisos de ejecución\n\n"
            "## Principios de construcción de la fábrica\n\n" + headings
            + "\n\n### Límite explícito del template\n"
              "Este texto no sincroniza ni modifica consumidores.\n")


def consumers():
    return {r: f"# AGENTES.md\n## Reglas locales\nTexto privado solo-test de {i}.\n"
            for i, r in enumerate(REPOSITORIES)}


class PlanSyncAgentesConsumidoresTests(unittest.TestCase):
    def test_plans_six_consumers_without_overwriting_local_rules(self):
        plan = plan_sync(template(), consumers())
        self.assertEqual(plan["status"], "planned")
        self.assertFalse(plan["can_apply"])
        self.assertEqual([e["repository_ref"] for e in plan["consumers"]], list(REPOSITORIES))
        self.assertEqual([e["action"] for e in plan["consumers"]], ["insert"] * 6)
        for original in consumers().values():
            rendered, action = _render_consumer(original, _principles(template()))
            self.assertEqual(action, "insert")
            self.assertTrue(rendered.startswith(original))
            self.assertIn("## Reglas locales", rendered)
            self.assertIn("### Principio 8", rendered)

    def test_idempotent_sync_and_stable_fingerprints(self):
        originals = consumers()
        once = plan_sync(template(), originals)
        updated = {repo: _render_consumer(value, _principles(template()))[0]
                   for repo, value in originals.items()}
        twice = plan_sync(template(), updated)
        thrice = plan_sync(template(), updated)
        self.assertEqual(twice, thrice)
        self.assertTrue(all(e["action"] == "noop" for e in twice["consumers"]))
        for before, after in zip(once["consumers"], twice["consumers"]):
            self.assertEqual(before["proposed_sha256"], after["original_sha256"])
            self.assertEqual(after["original_sha256"], after["proposed_sha256"])

    def test_incomplete_or_ambiguous_input_fails_closed(self):
        for bad in ({}, {**consumers(), "pl0n3r/Unexpected": "# AGENTES.md\n"}):
            with self.subTest(bad_keys=list(bad)), self.assertRaises(SyncPlanError):
                plan_sync(template(), bad)
        with self.assertRaises(SyncPlanError):
            plan_sync("# AGENTES.md\n", consumers())
        # Un template que añade reglas privadas como subsección tras el
        # límite o antes de él no contiene exclusivamente los principios.
        for source in (
            template() + "\n### Reglas privadas posteriores\nCLAVE_FAKE=solo-test\n",
            template().replace(
                "### Límite explícito del template",
                "### Reglas privadas anteriores\nCLAVE_FAKE=solo-test\n\n"
                "### Límite explícito del template",
            ),
        ):
            with self.subTest(location=source.find("Reglas privadas")):
                with self.assertRaisesRegex(SyncPlanError, "invalid_principles_source"):
                    plan_sync(source, consumers())

        # Unheaded text appended to the final section must not leak into
        # the projected content; a canonical footer still works.
        for suffix in ("\nCLAVE_FAKE=solo-test\n",
                       "\n\ncontact_email=private@example.invalid\n"):
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(SyncPlanError, "invalid_principles_source"):
                    plan_sync(template() + suffix, consumers())
        self.assertEqual(plan_sync(template(), consumers())["status"], "planned")

        # Unicode con sustitutos sueltos no debe escapar como error Unicode
        # sin tipificar, tanto en fuente como en uno de los consumidores.
        for bad_text in ("\ud800", "\udfff"):
            with self.subTest(kind="source", bad_text=ascii(bad_text)):
                with self.assertRaisesRegex(SyncPlanError, "invalid_document"):
                    plan_sync(template() + bad_text, consumers())
            docs = consumers()
            docs[REPOSITORIES[0]] += bad_text
            with self.subTest(kind="consumer", bad_text=ascii(bad_text)):
                with self.assertRaisesRegex(SyncPlanError, "invalid_document"):
                    plan_sync(template(), docs)

        # The original is under budget but the projected principles are not.
        oversized_projection = consumers()
        prefix = "# AGENTES.md\n"
        oversized_projection[REPOSITORIES[0]] = (
            prefix + "x" * (200_000 - len(prefix.encode("utf-8")) - 1)
        )
        with self.assertRaisesRegex(SyncPlanError, "invalid_document"):
            plan_sync(template(), oversized_projection)
        # Partial or malformed reserved markers must never be treated as absent.
        for broken_marker in (
            "<!-- factory-principios-sync:start",
            "<!-- factory-principios-sync:end",
            "<!-- factory-principios-sync:star -->",
            "<!-- factory-principios-sync:start --> junk",
            "prefix <!-- factory-principios-sync:end -->",
            "<!-- factory-principios-sync:start -->\n"
            "<!-- factory-principios-sync:en -->",
        ):
            docs = consumers()
            docs[REPOSITORIES[0]] = "# AGENTES.md\n" + broken_marker + "\n"
            with self.subTest(broken_marker=broken_marker):
                with self.assertRaisesRegex(SyncPlanError, "invalid_sync_markers"):
                    plan_sync(template(), docs)
        with self.assertRaisesRegex(SyncPlanError, "invalid_principles_source"):
            plan_sync(template() + "\n<!-- factory-principios-sync:star -->\n", consumers())

        for content in (
            "# AGENTES.md\n<!-- factory-principios-sync:start -->\n",
            "# AGENTES.md\n## Principios de construcción de la fábrica\n",
            "# AGENTES.md\n<!-- factory-principios-sync:start -->\n"
            "<!-- factory-principios-sync:start -->\n"
            "<!-- factory-principios-sync:end -->\n",
            "# AGENTES.md\n" + "x" * 200001,
            ("# AGENTES.md\n## Principios de construcción de la fábrica\n"
             "<!-- factory-principios-sync:start -->\n"
             "Texto previo\n<!-- factory-principios-sync:end -->\n"),
        ):
            documents = consumers()
            documents[REPOSITORIES[0]] = content
            with self.subTest(content=content[:45]), self.assertRaises(SyncPlanError):
                plan_sync(template(), documents)

    def test_plan_is_private_and_never_authorizes_apply(self):
        docs = consumers()
        docs[REPOSITORIES[0]] += "contact_email=private@example.invalid\n"
        plan = plan_sync(template(), docs)
        self.assertEqual(set(plan), {"status", "can_apply", "consumers"})
        self.assertFalse(plan["can_apply"])
        self.assertEqual(len(plan["consumers"]), 6)
        for item in plan["consumers"]:
            self.assertEqual(set(item), {"repository_ref", "action", "original_sha256", "proposed_sha256"})
        text = json.dumps(plan)
        self.assertNotIn("private@example.invalid", text)
        self.assertNotIn("Texto privado", text)
        self.assertNotIn("new_content", text)


if __name__ == "__main__":
    unittest.main()
