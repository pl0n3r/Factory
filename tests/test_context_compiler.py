import copy
import json
import unittest

from intelligence.context_compiler import (
    ContextCompilerError,
    MAX_CONTEXT_ITEMS,
    compile_mission_context,
)
from intelligence.project_dna import discover_project_dna


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


class ContextCompilerTests(unittest.TestCase):
    def test_mission_package_contains_only_relevant_context(self):
        package = compile_mission_context(
            project_dna=dna(),
            task=task(),
            context_items=[
                {
                    "category": "decision",
                    "source": "factory#143",
                    "text": "Living Software uses bounded context.",
                    "tags": ["living", "context"],
                },
                {
                    "category": "lesson",
                    "source": "factory#12",
                    "text": "Legacy release note unrelated to this mission.",
                    "tags": ["release"],
                },
            ],
        )

        self.assertEqual(len(package["context"]), 1)
        self.assertEqual(package["context"][0]["source"], "factory#143")
        self.assertEqual(package["project_dna"]["version"], 1)

    def test_package_is_bounded_and_deterministic(self):
        items = [
            {
                "category": "lesson",
                "source": f"factory#{index:03d}",
                "text": f"context lesson {index}",
                "tags": ["context"],
            }
            for index in range(MAX_CONTEXT_ITEMS + 5)
        ]
        first = compile_mission_context(
            project_dna=dna(),
            task=task(),
            context_items=items,
        )
        second = compile_mission_context(
            project_dna=dna(),
            task=task(),
            context_items=list(reversed(items)),
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first["context"]), MAX_CONTEXT_ITEMS)
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")

    def test_sources_are_traceable(self):
        package = compile_mission_context(
            project_dna=dna(),
            task=task(),
            context_items=[
                {
                    "category": "constraint",
                    "source": "PLAN-AGENTES.md#privacy",
                    "text": "Do not emit secrets.",
                    "tags": ["context"],
                }
            ],
        )

        item = package["context"][0]
        self.assertEqual(item["source"], "PLAN-AGENTES.md#privacy")
        self.assertEqual(item["category"], "constraint")

    def test_secrets_and_personal_values_are_not_emitted(self):
        package = compile_mission_context(
            project_dna=dna(),
            task=task(),
            context_items=[
                {
                    "category": "evidence",
                    "source": "factory#147",
                    "text": "Contact alice@example.com or +57 300 555 1212.",
                    "tags": ["context"],
                }
            ],
        )
        serialized = json.dumps(package)
        self.assertNotIn("alice@example.com", serialized)
        self.assertNotIn("300 555 1212", serialized)
        self.assertIn("[REDACTED]", serialized)

        sensitive = {
            "category": "evidence",
            "source": "factory#147",
            "text": "opaque",
            "tags": ["context"],
            "token": "should-never-emit",
        }
        with self.assertRaisesRegex(ContextCompilerError, "context item inválido"):
            compile_mission_context(
                project_dna=dna(),
                task=task(),
                context_items=[sensitive],
            )

        nested = copy.deepcopy(task())
        nested["goal"] = {"password": "secret"}
        with self.assertRaises(ContextCompilerError):
            compile_mission_context(
                project_dna=dna(),
                task=nested,
                context_items=[],
            )


if __name__ == "__main__":
    unittest.main()
