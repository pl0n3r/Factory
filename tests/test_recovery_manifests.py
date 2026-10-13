"""Acceptance #1088: five declarative Recovery Manifests, no production claims."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from recovery.contract import RecoveryContractError, validate_recovery_manifest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "recovery" / "manifests"
PROJECTS = ("autofactory", "brvtal", "condor", "controlbot", "grindflow")
PREFIX = "# factory-recovery-evidence "
LEGEND = "# Targets only: no backup, encryption, restore or RPO/RTO has been verified."
SOURCE = "https://github.com/pl0n3r/Factory/issues/305"
SOURCE_PROFILES = {
    "autofactory": ("NOT_APPLICABLE", "NOT_APPLICABLE", "REQUIRED", "NOT_APPLICABLE"),
    "brvtal": ("REQUIRED", "REQUIRED", "REQUIRED", "google_drive"),
    "condor": ("REQUIRED", "REQUIRED", "REQUIRED", "google_drive"),
    "controlbot": ("REQUIRED", "NOT_APPLICABLE", "REQUIRED", "google_drive"),
    "grindflow": ("REQUIRED", "REQUIRED", "REQUIRED", "google_drive"),
}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse(text):
    lines = text.splitlines()
    if not lines or not lines[0].startswith(PREFIX):
        raise ValueError("missing declaration evidence")
    marker = json.loads(lines[0][len(PREFIX):], object_pairs_hook=_unique_keys)
    if not isinstance(marker, dict):
        raise ValueError("invalid evidence marker")
    # Exactly one canonical header and one fixed informational legend.
    # Never silently discard an indented YAML comment or contradictory status.
    if len(lines) < 3 or lines[1] != LEGEND:
        raise ValueError("invalid recovery legend")
    if any(line.lstrip().startswith("#") for line in lines[2:]):
        raise ValueError("unexpected YAML comment")
    payload = json.loads("\n".join(lines[2:]), object_pairs_hook=_unique_keys)
    return marker, payload


class RecoveryManifestsTests(unittest.TestCase):
    def test_five_manifests_validate_against_closed_schema(self):
        self.assertEqual({path.name for path in DIRECTORY.glob("*.yml")},
                         {project + ".yml" for project in PROJECTS})
        schema = json.loads((ROOT / "recovery" / "contract.schema.json").read_text(encoding="utf-8"))
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        for project in PROJECTS:
            with self.subTest(project=project):
                text = (DIRECTORY / (project + ".yml")).read_text(encoding="utf-8")
                marker, payload = _parse(text)
                self.assertEqual(payload["project"], project)
                self.assertEqual(set(payload), set(schema["required"]))
                validated = validate_recovery_manifest(payload)
                self.assertEqual(validated, payload)
                self.assertEqual(validated["protection"], {
                    "copies": 3, "media_types": 2, "offsite_copies": 1,
                    "immutable_copies": 1, "undetected_restore_failures": 0,
                })
                db, media, repository, cold = SOURCE_PROFILES[project]
                self.assertEqual(validated["sources"], {
                    "database": db, "media": media, "repository": repository,
                })
                self.assertEqual(validated["offsite"], {
                    "object_storage": "REQUIRED", "cold_copy": cold,
                })
                self.assertEqual(validated["encryption"],
                                 {"required": True, "key_material": "EXTERNAL_ONLY"})
                self.assertEqual(validated["restore_drill"]["cadence_days"], 7)

    def test_objectives_are_explicitly_declared_not_measured(self):
        for project in PROJECTS:
            with self.subTest(project=project):
                text = (DIRECTORY / (project + ".yml")).read_text(encoding="utf-8")
                marker, payload = _parse(text)
                self.assertEqual(marker, {
                    "version": 1, "status": "DECLARED_NOT_MEASURED",
                    "observed_rpo": "UNKNOWN", "observed_rto": "UNKNOWN",
                    "operational_readiness": "UNKNOWN", "source": SOURCE,
                })
                self.assertEqual(payload["target"],
                                 {"rpo_minutes": 15, "rto_minutes": 60})
                self.assertEqual(payload["retention"], {
                    "hourly": 24, "daily": 7, "weekly": 8, "monthly": 12,
                })
                self.assertNotIn("observed_rpo", payload)
                self.assertNotIn("operational_readiness", payload)
                self.assertEqual(text.splitlines()[1], LEGEND)

    def test_rejects_invalid_manifest_and_requires_all_projects(self):
        paths = {p.stem for p in DIRECTORY.glob("*.yml")}
        self.assertEqual(paths, set(PROJECTS))
        template = (DIRECTORY / "condor.yml").read_text(encoding="utf-8")
        marker, original = _parse(template)
        with self.assertRaises(ValueError):
            _parse(template.replace(PREFIX, "# missing-evidence ", 1))
        with self.assertRaises(ValueError):
            _parse(template + "\n" + template.splitlines()[0] + "\n")
        # The exact bug in QA: an indented second recovery marker was
        # previously skipped both by duplicate detection and JSON parsing.
        adversarial_comments = (
            '  # factory-recovery-evidence {"status":"VALIDATED_IN_PRODUCTION",'
            '"operational_readiness":"GREEN"}',
            '  # operational_readiness=GREEN',
            '# unexpected recovery status override',
            '   ' + LEGEND,
        )
        for extra in adversarial_comments:
            with self.subTest(extra=extra):
                modified = template.replace(LEGEND, LEGEND + "\n" + extra, 1)
                with self.assertRaises(ValueError):
                    _parse(modified)
        with self.assertRaises(ValueError):
            _parse(template.replace('"project": "condor"',
                                    '"project": "condor", "project": "condor"', 1))
        with self.assertRaises(ValueError):
            _parse(template.replace('"status":"DECLARED_NOT_MEASURED"',
                                    '"status":"DECLARED_NOT_MEASURED","status":"READY"', 1))

        mutants = []
        bad = copy.deepcopy(original)
        bad["target"]["rpo_minutes"] = 0
        mutants.append(bad)
        bad = copy.deepcopy(original)
        bad["protection"]["copies"] = 2
        mutants.append(bad)
        bad = copy.deepcopy(original)
        bad["sources"] = {k: "NOT_APPLICABLE" for k in bad["sources"]}
        mutants.append(bad)
        bad = copy.deepcopy(original)
        bad["encryption"]["key_material"] = "inline-secret"
        mutants.append(bad)
        bad = copy.deepcopy(original)
        bad["observed_rpo"] = 15
        mutants.append(bad)
        bad = copy.deepcopy(original)
        bad["project"] = "token=sensitive-sentinel"
        mutants.append(bad)
        for value in mutants:
            with self.subTest(value=str(value)[:75]):
                with self.assertRaises(RecoveryContractError) as caught:
                    validate_recovery_manifest(value)
                self.assertNotIn("sensitive-sentinel", str(caught.exception))
        self.assertEqual(marker["operational_readiness"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
