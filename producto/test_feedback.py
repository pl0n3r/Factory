import json
import tempfile
import unittest
from pathlib import Path

from producto.feedback import (
    FAMILIES,
    FeedbackValidationError,
    aggregate,
    load_catalog,
    load_epic_markers,
    load_records,
    parse_epic_marker,
    render_markdown,
    validate_record,
)


CATALOG = {
    "usage_rate": {"family": "usage", "unit": "ratio", "direction": "increase"},
    "error_rate": {"family": "error", "unit": "ratio", "direction": "decrease"},
    "conversion_rate": {"family": "conversion", "unit": "ratio", "direction": "increase"},
    "lcp_p75_ms": {"family": "cwv", "unit": "ms", "direction": "decrease"},
    "seo_clicks": {"family": "seo", "unit": "count", "direction": "increase"},
}


def record(**changes):
    value = {
        "project": "pl0n3r/factory",
        "epic": "pl0n3r/factory#100",
        "metric": "error_rate",
        "surface": "home",
        "phase": "baseline",
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-09-08T00:00:00Z",
        "value": 0.02,
        "sample_size": 120,
    }
    value.update(changes)
    return value


def markers_for(rows, target=10.0):
    markers = {}
    for row in rows:
        existing = markers.get(row["epic"])
        marker = {
            "metric": row["metric"],
            "surface": row["surface"],
            "target_improvement_pct": float(target),
            "direction": CATALOG[row["metric"]]["direction"],
        }
        if existing is not None and existing != marker:
            raise AssertionError("Fixture mezcla objetivos incompatibles para el mismo épico.")
        markers[row["epic"]] = marker
    return markers


def aggregate_rows(rows, min_sample_size=100, markers=None):
    return aggregate(
        rows,
        CATALOG,
        min_sample_size=min_sample_size,
        epic_markers=markers if markers is not None else markers_for(rows),
    )


class FeedbackTests(unittest.TestCase):
    def test_catalog_covers_all_required_families(self):
        catalog = load_catalog()
        self.assertEqual({spec["family"] for spec in catalog.values()}, FAMILIES)

    def test_closed_schema_blocks_pii_shaped_extra_fields(self):
        raw = record()
        raw["email"] = "persona@example.com"
        with self.assertRaisesRegex(FeedbackValidationError, "exactamente"):
            validate_record(raw, CATALOG, "fixture")

    def test_epic_must_belong_to_project(self):
        raw = record(epic="pl0n3r/otro#100")
        with self.assertRaisesRegex(FeedbackValidationError, "mismo project"):
            validate_record(raw, CATALOG, "fixture")

    def test_metric_units_and_timestamps_fail_closed(self):
        ratio = record(value=1.2)
        without_zone = record(period_start="2026-09-01T00:00:00")
        with self.assertRaisesRegex(FeedbackValidationError, "ratio"):
            validate_record(ratio, CATALOG, "fixture")
        with self.assertRaisesRegex(FeedbackValidationError, "zona horaria"):
            validate_record(without_zone, CATALOG, "fixture")

    def test_huge_sample_and_nonfinite_value_fail_closed(self):
        huge_sample = record(sample_size=1_000_000_001)
        nonfinite = record(value=float("inf"))
        with self.assertRaisesRegex(FeedbackValidationError, "sample_size"):
            validate_record(huge_sample, CATALOG, "fixture")
        with self.assertRaisesRegex(FeedbackValidationError, "finito"):
            validate_record(nonfinite, CATALOG, "fixture")

    def test_count_metric_requires_integer_without_float_coercion(self):
        raw = record(metric="seo_clicks", value=10.5)
        with self.assertRaisesRegex(FeedbackValidationError, "count"):
            validate_record(raw, CATALOG, "fixture")

    def test_epic_marker_declares_metric_surface_and_target(self):
        body = (
            'Objetivo\n<!-- factory-product-metric '
            '{"metric":"conversion_rate","surface":"checkout",'
            '"target_improvement_pct":10} -->'
        )
        marker = parse_epic_marker(body, CATALOG)
        self.assertEqual(marker["metric"], "conversion_rate")
        self.assertEqual(marker["direction"], "increase")
        self.assertEqual(marker["target_improvement_pct"], 10.0)

    def test_malformed_epic_marker_fails_closed(self):
        with self.assertRaisesRegex(FeedbackValidationError, "malformado"):
            parse_epic_marker(
                "<!-- factory-product-metric ??? -->",
                CATALOG,
            )

    def test_insufficient_sample_never_proposes_issue(self):
        rows = [
            validate_record(record(sample_size=20), CATALOG, "baseline"),
            validate_record(
                record(
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                    value=0.05,
                    sample_size=20,
                ),
                CATALOG,
                "post",
            ),
        ]
        report = aggregate_rows(rows, min_sample_size=100)
        self.assertEqual(report["results"][0]["status"], "insufficient-data")
        self.assertEqual(report["proposals"], [])

    def test_zero_baseline_never_invents_percent_change(self):
        rows = [
            validate_record(record(value=0.0), CATALOG, "baseline"),
            validate_record(
                record(
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                    value=0.03,
                ),
                CATALOG,
                "post",
            ),
        ]
        report = aggregate_rows(rows, min_sample_size=100)
        result = report["results"][0]
        self.assertEqual(result["status"], "non-comparable-zero-baseline")
        self.assertIsNone(result["delta_pct"])
        self.assertEqual(report["proposals"], [])

    def test_overlapping_before_after_windows_fail_closed(self):
        rows = [
            validate_record(
                record(
                    period_end="2026-09-10T00:00:00Z",
                ),
                CATALOG,
                "baseline",
            ),
            validate_record(
                record(
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                ),
                CATALOG,
                "post",
            ),
        ]
        with self.assertRaisesRegex(FeedbackValidationError, "Baseline"):
            aggregate_rows(rows)

    def test_overlapping_windows_within_phase_fail_closed(self):
        rows = [
            validate_record(record(), CATALOG, "one"),
            validate_record(
                record(
                    period_start="2026-09-07T00:00:00Z",
                    period_end="2026-09-14T00:00:00Z",
                ),
                CATALOG,
                "two",
            ),
        ]
        with self.assertRaisesRegex(FeedbackValidationError, "solapadas"):
            aggregate_rows(rows)

    def test_cwv_percentiles_are_not_averaged_across_windows(self):
        rows = [
            validate_record(
                record(
                    metric="lcp_p75_ms",
                    period_start="2026-09-01T00:00:00Z",
                    period_end="2026-09-04T00:00:00Z",
                    value=2200,
                ),
                CATALOG,
                "one",
            ),
            validate_record(
                record(
                    metric="lcp_p75_ms",
                    period_start="2026-09-04T00:00:00Z",
                    period_end="2026-09-08T00:00:00Z",
                    value=2100,
                ),
                CATALOG,
                "two",
            ),
        ]
        with self.assertRaisesRegex(FeedbackValidationError, "no se promedian percentiles"):
            aggregate_rows(rows)

    def test_count_metrics_normalize_per_day_across_different_windows(self):
        rows = [
            validate_record(
                record(
                    metric="seo_clicks",
                    value=2000,
                    sample_size=200,
                    period_start="2026-09-01T00:00:00Z",
                    period_end="2026-09-15T00:00:00Z",
                ),
                CATALOG,
                "baseline",
            ),
            validate_record(
                record(
                    metric="seo_clicks",
                    phase="post-deploy",
                    value=1000,
                    sample_size=200,
                    period_start="2026-09-16T00:00:00Z",
                    period_end="2026-09-23T00:00:00Z",
                ),
                CATALOG,
                "post",
            ),
        ]
        report = aggregate_rows(rows)
        result = report["results"][0]
        self.assertEqual(result["baseline"], result["post_deploy"])
        self.assertEqual(result["delta_pct"], 0.0)
        self.assertEqual(result["status"], "stable")
        self.assertEqual(report["proposals"], [])

    def test_report_requires_matching_epic_marker_and_includes_target(self):
        rows = [
            validate_record(
                record(value=0.02, sample_size=200),
                CATALOG,
                "baseline",
            ),
            validate_record(
                record(
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                    value=0.04,
                    sample_size=300,
                ),
                CATALOG,
                "post",
            ),
        ]
        with self.assertRaisesRegex(FeedbackValidationError, "requiere markers"):
            aggregate(rows, CATALOG, epic_markers={})

        mismatched = markers_for(rows)
        mismatched["pl0n3r/factory#100"] = {
            **mismatched["pl0n3r/factory#100"],
            "surface": "otra",
        }
        with self.assertRaisesRegex(FeedbackValidationError, "no coincide"):
            aggregate(rows, CATALOG, epic_markers=mismatched)

        report = aggregate_rows(rows, markers=markers_for(rows, target=12.5))
        self.assertEqual(report["results"][0]["target_improvement_pct"], 12.5)
        self.assertEqual(report["proposals"][0]["target_improvement_pct"], 12.5)

    def test_marker_file_requires_exact_observed_epics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epic-markers.json"
            body = (
                '<!-- factory-product-metric '
                '{"metric":"error_rate","surface":"home",'
                '"target_improvement_pct":10} -->'
            )
            path.write_text(
                json.dumps({"pl0n3r/factory#100": body}),
                encoding="utf-8",
            )
            loaded = load_epic_markers(
                path,
                CATALOG,
                ["pl0n3r/factory#100"],
            )
            self.assertEqual(loaded["pl0n3r/factory#100"]["metric"], "error_rate")
            with self.assertRaisesRegex(FeedbackValidationError, "exactamente"):
                load_epic_markers(
                    path,
                    CATALOG,
                    ["pl0n3r/factory#100", "pl0n3r/factory#101"],
                )

    def test_regression_generates_deterministic_prioritized_proposal(self):
        rows = [
            validate_record(record(value=0.02, sample_size=200), CATALOG, "baseline"),
            validate_record(
                record(
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                    value=0.04,
                    sample_size=300,
                ),
                CATALOG,
                "post",
            ),
        ]
        report = aggregate_rows(rows, min_sample_size=100)
        result = report["results"][0]
        proposal = report["proposals"][0]
        self.assertEqual(result["status"], "regressed")
        self.assertEqual(result["delta_pct"], 100.0)
        self.assertEqual(proposal["regression_pct"], 100.0)
        self.assertEqual(proposal["epic"], "pl0n3r/factory#100")
        self.assertGreater(proposal["impact_score"], 0)
        self.assertEqual(report, aggregate_rows(rows, min_sample_size=100))

    def test_improvement_is_reported_but_not_proposed_as_regression(self):
        rows = [
            validate_record(
                record(metric="conversion_rate", value=0.10),
                CATALOG,
                "baseline",
            ),
            validate_record(
                record(
                    metric="conversion_rate",
                    phase="post-deploy",
                    period_start="2026-09-09T00:00:00Z",
                    period_end="2026-09-16T00:00:00Z",
                    value=0.13,
                ),
                CATALOG,
                "post",
            ),
        ]
        report = aggregate_rows(rows)
        self.assertEqual(report["results"][0]["status"], "improved")
        self.assertEqual(report["proposals"], [])

    def test_duplicate_aggregates_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "datos.jsonl"
            row = json.dumps(record())
            path.write_text(row + "\n" + row + "\n", encoding="utf-8")
            with self.assertRaisesRegex(FeedbackValidationError, "duplicado"):
                load_records(directory, CATALOG)

    def test_empty_report_has_no_fabricated_proposals(self):
        report = aggregate_rows([])
        text = render_markdown(report)
        self.assertEqual(report["proposals"], [])
        self.assertIn("No hay telemetría suficiente", text)


if __name__ == "__main__":
    unittest.main()
