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
