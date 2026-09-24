import json
import tempfile
import unittest
from pathlib import Path

from lecciones.memoria import LessonValidationError, load_lessons, summarize, token_comparison, validate_lesson


def lesson(identifier="factory-bootstrap", project="pl0n3r/factory", **changes):
    item = {
        "id": identifier,
        "project": project,
        "kind": "rework",
        "occurred_at": "2026-09-24T05:00:00Z",
        "what": "Un workflow de bootstrap intentó ejecutar una herramienta ausente en la base.",
        "why": "El workflow asumió que su script ya existía en main.",
        "prevention": "Separar validación de candidato y enforcement sobre base confiable.",
        "source": "pl0n3r/factory#14",
    }
    item.update(changes)
    return item


class MemoryTests(unittest.TestCase):
    def test_summary_is_project_scoped_and_bounded(self):
        rows = [
            validate_lesson(lesson("factory-one"), "1"),
            validate_lesson(lesson("condor-one", project="pl0n3r/Condor"), "2"),
        ]
        text = summarize(rows, "pl0n3r/factory", max_lessons=1, max_chars=1000)
        self.assertIn("factory-one", text)
        self.assertNotIn("condor-one", text)
        self.assertLessEqual(len(text), 1000)

    def test_summary_skips_oversized_recent_lesson_and_uses_older_one(self):
        recent = validate_lesson(
            lesson(
                "factory-large",
                occurred_at="2026-09-24T06:00:00Z",
                what="x" * 260,
                why="y" * 260,
                prevention="z" * 260,
            ),
            "recent",
        )
        older = validate_lesson(
            lesson(
                "factory-small",
                occurred_at="2026-09-24T05:00:00Z",
                what="corto",
                why="corto",
                prevention="corto",
            ),
            "older",
        )
        text = summarize(
            [recent, older],
            "pl0n3r/factory",
            max_lessons=5,
            max_chars=400,
        )
        self.assertIn("factory-small", text)
        self.assertNotIn("factory-large", text)
        self.assertLessEqual(len(text), 400)

    def test_duplicate_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lessons.jsonl"
            path.write_text(
                "\n".join(json.dumps(lesson()) for _ in range(2)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LessonValidationError, "id duplicado"):
                load_lessons([path])

    def test_unknown_fields_and_multiline_text_are_rejected(self):
        bad = lesson()
        bad["unexpected_field"] = "x"
        with self.assertRaisesRegex(LessonValidationError, "campos no permitidos"):
            validate_lesson(bad, "x")
        multiline = lesson("factory-two", what="a\nb")
        with self.assertRaisesRegex(LessonValidationError, "una línea"):
            validate_lesson(multiline, "x")

    def test_lesson_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "real.jsonl"
            target.write_text(json.dumps(lesson()), encoding="utf-8")
            link = directory / "linked.jsonl"
            link.symlink_to(target)
            with self.assertRaisesRegex(LessonValidationError, "enlaces simbólicos"):
                load_lessons([link])

    def test_missing_metrics_file_is_insufficient_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = token_comparison(
                Path(tmp) / "missing.jsonl",
                "2026-09-15T00:00:00Z",
                "pl0n3r/factory",
            )
            self.assertEqual(result["status"], "insufficient-data")
            self.assertEqual(result["before_samples"], 0)
            self.assertEqual(result["after_samples"], 0)

    def test_token_comparison_requires_real_before_after_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "task_id": "pl0n3r/factory#101",
                        "task_type": "agent-bootstrap",
                        "tokens_input": 100,
                        "completed_at": "2026-09-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            result = token_comparison(
                path,
                "2026-09-15T00:00:00Z",
                "pl0n3r/factory",
            )
            self.assertEqual(result["status"], "insufficient-data")
            self.assertIsNone(result["reduction_pct"])

    def test_token_comparison_measures_reported_tokens(self):
        rows = []
        for issue, stamp, value in [
            (201, "2026-09-01T00:00:00Z", 100),
            (202, "2026-09-02T00:00:00Z", 120),
            (203, "2026-09-16T00:00:00Z", 60),
            (204, "2026-09-17T00:00:00Z", 50),
        ]:
            rows.append(
                json.dumps(
                    {
                        "task_id": f"pl0n3r/factory#{issue}",
                        "task_type": "agent-bootstrap",
                        "tokens_input": value,
                        "completed_at": stamp,
                    }
                )
            )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.jsonl"
            path.write_text("\n".join(rows), encoding="utf-8")
            result = token_comparison(
                path,
                "2026-09-15T00:00:00Z",
                "pl0n3r/factory",
            )
            self.assertEqual(result["status"], "measured")
            self.assertEqual(result["project"], "pl0n3r/factory")
            self.assertEqual(result["change_at"], "2026-09-15T00:00:00+00:00")
            self.assertEqual(result["before_avg_tokens"], 110)
            self.assertEqual(result["after_avg_tokens"], 55)
            self.assertEqual(result["reduction_pct"], 50.0)

    def test_token_comparison_is_project_scoped(self):
        rows = []
        fixtures = [
            ("pl0n3r/factory#301", "2026-09-01T00:00:00Z", 100),
            ("pl0n3r/factory#302", "2026-09-02T00:00:00Z", 100),
            ("pl0n3r/factory#303", "2026-09-16T00:00:00Z", 50),
            ("pl0n3r/factory#304", "2026-09-17T00:00:00Z", 50),
            ("pl0n3r/Condor#401", "2026-09-01T00:00:00Z", 10),
            ("pl0n3r/Condor#402", "2026-09-02T00:00:00Z", 10),
            ("pl0n3r/Condor#403", "2026-09-16T00:00:00Z", 200),
            ("pl0n3r/Condor#404", "2026-09-17T00:00:00Z", 200),
        ]
        for task_id, stamp, value in fixtures:
            rows.append(json.dumps({
                "task_id": task_id,
                "task_type": "agent-bootstrap",
                "tokens_input": value,
                "completed_at": stamp,
            }))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.jsonl"
            path.write_text("\n".join(rows), encoding="utf-8")
            result = token_comparison(
                path,
                "2026-09-15T00:00:00Z",
                "pl0n3r/factory",
            )
            self.assertEqual(result["reduction_pct"], 50.0)
            self.assertEqual(result["before_samples"], 2)
            self.assertEqual(result["after_samples"], 2)

    def test_bootstrap_metric_requires_unambiguous_project_identity(self):
        row = {
            "task_id": "factory#501",
            "task_type": "agent-bootstrap",
            "tokens_input": 100,
            "completed_at": "2026-09-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.jsonl"
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(LessonValidationError, "owner/repo#N"):
                token_comparison(
                    path,
                    "2026-09-15T00:00:00Z",
                    "pl0n3r/factory",
                )

    def test_safe_context_limits_are_enforced(self):
        rows = [validate_lesson(lesson("factory-three"), "1")]
        with self.assertRaisesRegex(LessonValidationError, "fuera de rango"):
            summarize(rows, "pl0n3r/factory", max_chars=399)


if __name__ == "__main__":
    unittest.main()
