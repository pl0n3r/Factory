"""Offline tests for Factory #1109, without real consumer data or external I/O."""
import json
import unittest
from collections.abc import Mapping
from pathlib import Path

from scripts.plan_sync_agentes_consumidores import (
    REPOSITORIES, SyncPlanError, _principles, _render_consumer, plan_sync,
)


def template():
    headings = "\n\n".join(
        ["### Regla 0 — alcance seguro\nparalelismo con límites"]
        + [f"### Principio {n} — ejemplo\nEjemplo seguro del principio {n}."
           for n in range(1, 9)]
    )
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

    def test_current_factory_template_is_compatible_with_offline_planner(self):
        # La API es pura; solo el test lee la fuente canónica del mismo árbol.
        source = (Path(__file__).resolve().parents[1] /
                  "template" / "AGENTES.md").read_text(encoding="utf-8")
        planned = plan_sync(source, consumers())
        self.assertEqual(planned["status"], "planned")
        self.assertFalse(planned["can_apply"])
        self.assertEqual(len(planned["consumers"]), 6)
        self.assertTrue(all(row["action"] == "insert"
                            for row in planned["consumers"]))

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

        # Headings in a fenced example are not authoritative principles.
        fenced_heading = template().replace(
            "## Principios de construcción de la fábrica",
            "```markdown\n" + "## Principios de construcción de la fábrica",
            1,
        ).replace(
            "### Límite explícito del template",
            "```\n" + "### Límite explícito del template", 1,
        )
        fenced_principle = template().replace(
            "### Principio 5 — ejemplo",
            "```markdown\n" + "### Principio 5 — ejemplo",
            1,
        ).replace(
            "### Principio 6 — ejemplo",
            "```\n" + "### Principio 6 — ejemplo", 1,
        )
        for fake_source in (fenced_heading, fenced_principle):
            with self.subTest(source=fake_source[:100]):
                with self.assertRaisesRegex(
                    SyncPlanError, "invalid_principles_source"
                ):
                    plan_sync(fake_source, consumers())

        # Una sección sin cuerpo, aunque retenga título y cierre auténticos,
        # no constituye un principio apto para planificar seis consumidores.
        empty_principle = template().replace(
            "### Principio 3 — ejemplo\nEjemplo seguro del principio 3.",
            "### Principio 3 — ejemplo",
        )
        with self.assertRaisesRegex(SyncPlanError, "invalid_principles_source"):
            plan_sync(empty_principle, consumers())
        # Sin cierre, los marcadores serían añadidos dentro de un fence literal.
        for opening in ("\x60\x60\x60markdown", "~~~text"):
            docs = consumers()
            docs[REPOSITORIES[0]] += opening + "\nEjemplo local sin cierre\n"
            with self.subTest(unclosed_fence=opening):
                with self.assertRaisesRegex(SyncPlanError, "invalid_sync_markers"):
                    plan_sync(template(), docs)

        class BrokenMapping(Mapping):
            def __init__(self, stage):
                self.stage = stage

            def __iter__(self):
                if self.stage == "keys":
                    raise RuntimeError("private-secret-fixture")
                return iter(REPOSITORIES)

            def __len__(self):
                return len(REPOSITORIES)

            def __getitem__(self, name):
                if self.stage == "value":
                    raise RuntimeError("private-secret-fixture")
                return consumers()[name]

        for stage in ("keys", "value"):
            with self.subTest(mapping_stage=stage):
                with self.assertRaisesRegex(
                    SyncPlanError, "incomplete_consumer_inventory"
                ) as raised:
                    plan_sync(template(), BrokenMapping(stage))
                self.assertNotIn("private-secret-fixture", str(raised.exception))

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
        # A literal example inside a fenced Markdown block is never
        # considered a managed sync section, even with exact markers.
        for opening, closing in (
            ("```markdown", "```"),
            ("~~~markdown", "~~~"),
            ("````text", "````"),
        ):
            document = consumers()
            document[REPOSITORIES[0]] = (
                "# AGENTES.md\n## Ejemplo local\n" + opening + "\n"
                "<!-- factory-principios-sync:start -->\n"
                "Ejemplo literal, no administrado\n"
                "<!-- factory-principios-sync:end -->\n"
                + closing + "\n"
            )
            with self.subTest(opening=opening):
                with self.assertRaisesRegex(SyncPlanError, "invalid_sync_markers"):
                    plan_sync(template(), document)
        valid_fence = consumers()
        valid_fence[REPOSITORIES[0]] += "```text\nUna regla local\n```\n"
        self.assertEqual(plan_sync(template(), valid_fence)["consumers"][0]["action"],
                         "insert")

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
