#!/usr/bin/env python3
"""Pruebas de procedencia e intención de las puertas de release Factory."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts import release_window as rw


NOW = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
SHA = "4" * 40
TICK = chr(96)


def issue_row(number: int, title: str, body: str) -> dict[str, object]:
    return {
        "issue": {
            "number": number,
            "state": "open",
            "title": title,
            "body": body,
            "updated_at": "2026-10-03T09:55:00Z",
        },
        "comments": [],
    }


class ReleaseMarkerScopeTests(unittest.TestCase):
    def test_unrelated_issue_with_markdown_marker_example_is_not_a_release_gate(self) -> None:
        # Un hallazgo QA no es una puerta, aunque la búsqueda de GitHub lo
        # encuentre por mencionar factory-human-gate y factory-release.
        qa_body = (
            "QA: factory-human-gate y factory-release son ejemplos.\n"
            "El fragmento de documentación es "
            + TICK + "<!-- factory-release-window ENCABEZADO_TRUNCADO -->" + TICK
            + ".\nNo autoriza una publicación.\n"
        )
        self.assertEqual(
            rw.gate_records([issue_row(1273, "fix(seguridad release): encabezados", qa_body)]),
            [],
        )
        # Ni siquiera un JSON completo de ventana concede autoridad sin gate.
        window_example = (
            "Ejemplo Markdown: " + TICK + '<!-- factory-release-window '
            '{"version":1,"sha":"' + SHA + '",'
            '"opened_at":"2026-10-03T10:00:00Z",'
            '"expires_at":"2026-10-03T11:00:00Z"} -->' + TICK
            + ".\nfactory-human-gate factory-release son menciones documentales."
        )
        self.assertEqual(
            rw.gate_records([issue_row(1280, "docs: contrato de releases", window_example)]),
            [],
        )
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        self.assertEqual(len(rw.gate_records([
            issue_row(900, rendered["title"], rendered["body"]),
        ])), 1)

    def test_canonical_gate_complete_invalid_schema_fails_closed_without_window(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        title = rendered["title"]
        malformed = (
            '<!-- factory-human-gate {"category":"factory-release"} -->',
            '<!-- factory-human-gate {"category":"factory-release","context":"'
            + "Factory v1.0.23 main@" + SHA + '"} -->',
        )
        for body in malformed:
            with self.subTest(body=body), self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([issue_row(1200, title, body)])

    def test_legacy_noncanonical_invalid_gate_is_not_authoritative(self) -> None:
        bad_legacy = (
            '<!-- factory-human-gate {"category":"factory-release"} -->'
        )
        self.assertEqual(
            rw.gate_records([issue_row(1201, "docs: old gate schema", bad_legacy)]),
            [],
        )
        unrelated = (
            '<!-- factory-human-gate {"category":"product-direction"} -->'
        )
        self.assertEqual(
            rw.gate_records([issue_row(1202, "docs: another category", unrelated)]),
            [],
        )

    def test_canonical_valid_gate_and_documentation_examples_preserved(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        records = rw.gate_records([issue_row(1203, rendered["title"], rendered["body"])])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sha"], SHA)
        self.assertIsNotNone(records[0]["window"])
        self.assertEqual(
            rw.freeze_gate(records, NOW)["number"], 1203,
        )
        legacy_body = "\n".join(
            line for line in rendered["body"].splitlines()
            if "factory-release-window" not in line
            and "factory-release-rearm" not in line
        )
        legacy = rw.gate_records([issue_row(1204, "legacy", legacy_body)])
        self.assertEqual(len(legacy), 1)
        self.assertIsNone(legacy[0]["window"])
        example = (
            "Example: " + TICK
            + '<!-- factory-release-window {"version":1,"sha":"' + SHA
            + '","opened_at":"2026-10-03T10:00:00Z",'
            + '"expires_at":"2026-10-03T11:00:00Z"} -->' + TICK
            + "\nReferenced: factory-human-gate factory-release"
        )
        self.assertEqual(
            rw.gate_records([issue_row(1205, "docs: release marker", example)]),
            [],
        )
        broken = "release gate " + TICK + "<!-- factory-human-gate {" + TICK
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([issue_row(1206, rendered["title"], broken)])

    def test_edited_release_gate_title_with_malformed_marker_keeps_fail_closed(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        body = "\n".join(
            "<!-- factory-human-gate {"
            if line.startswith("<!-- factory-human-gate ")
            else line
            for line in rendered["body"].splitlines()
        )
        self.assertIn("factory-release-window", body)
        self.assertIn("factory-release-rearm", body)
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([
                issue_row(1207, "docs: revisión con título editado", body),
            ])

    def test_markdown_window_with_unrelated_complete_gate_is_not_authority(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        window = next(
            line for line in rendered["body"].splitlines()
            if line.startswith("<!-- factory-release-window ")
        )
        doc_body = (
            "Markdown example with unrelated gate:\n"
            + '<!-- factory-human-gate {"category":"brand"} -->'
            + "\n" + window
        )
        # Hay exactamente un encabezado humano y un marker completo, pero
        # no una puerta factory-release ni un título de autoridad.
        self.assertEqual(len(rw.GATE_HEADER_RE.findall(doc_body)), 1)
        self.assertEqual(len(rw.MARKER_RE.findall(doc_body)), 1)
        self.assertEqual(
            rw.gate_records([issue_row(1208, "docs: unrelated gate", doc_body)]),
            [],
        )

    def test_canonical_title_missing_gate_does_not_silently_disappear(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([issue_row(1209, rendered["title"], "plain text")])

    def test_edited_title_rejects_duplicate_incomplete_headers_with_window(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        window = next(
            line for line in rendered["body"].splitlines()
            if line.startswith("<!-- factory-release-window ")
        )
        malformed = (
            window + "\n"
            + "<!-- FACTORY - HUMAN - GATE {\n"
            + "<!-- factory-human-gate TRUNCATED -->"
        )
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([
                issue_row(1210, "docs: renamed canonical release", malformed),
            ])

    def test_real_release_gate_with_extra_malformed_header_remains_fail_closed(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        fragments = (
            TICK + "<!-- factory-release-window TRUNCATED -->" + TICK,
            TICK + "<!-- factory-human-gate TRUNCATED -->" + TICK,
            TICK + "<!-- FACTORY - RELEASE - WINDOW {" + TICK,
            TICK + "<!-- FACTORY - HUMAN - GATE {" + TICK,
        )
        for fragment in fragments:
            for body in (
                rendered["body"] + "\n" + fragment,
                fragment + "\n" + rendered["body"],
            ):
                with self.subTest(fragment=fragment, prefix=body.startswith(fragment)):
                    with self.assertRaises(rw.ReleaseWindowError):
                        rw.gate_records([issue_row(901, rendered["title"], body)])

    def test_malformed_authoritative_gate_cannot_be_silently_ignored(self) -> None:
        rendered = rw._render_gate("1.0.23", SHA, NOW, source_issue=900)
        title = rendered["title"]
        # La identidad de una puerta de release real implica rechazo ante
        # marcadores incompletos, aunque no haya JSON parseable.
        for body in (
            "Release canónico incompleto: <!-- factory-human-gate {",
            "Release canónico incompleto: <!-- factory-release-window {",
            "<!-- FACTORY-HUMAN-GATE TRUNCATED -->",
            "<!-- FACTORY-RELEASE-WINDOW TRUNCATED -->",
        ):
            with self.subTest(body=body), self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([issue_row(902, title, body)])

        # Un gate real legacy conserva el contrato sin depender del título.
        legacy = "\n".join(
            line for line in rendered["body"].splitlines()
            if "factory-release-window" not in line and "factory-release-rearm" not in line
        )
        self.assertEqual(
            len(rw.gate_records([issue_row(903, "puerta legacy histórica", legacy)])),
            1,
        )
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([issue_row(
                904, "puerta legacy histórica",
                legacy + "\n" + TICK + "<!-- factory-release-window TRUNCATED -->" + TICK,
            )])
        unrelated = (
            '<!-- factory-human-gate '
            '{"category":"product-direction","context":"legacy schema"} -->'
        )
        self.assertEqual(
            rw.gate_records([issue_row(905, "docs: puerta ajena", unrelated)]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
