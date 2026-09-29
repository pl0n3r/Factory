import copy
import json
import unittest
from pathlib import Path

from recovery.contract import (
    RecoveryContractError, canonical_recovery_manifest, validate_recovery_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return {
        "version": 1, "project": "condor",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {
            "copies": 3, "media_types": 2, "offsite_copies": 1,
            "immutable_copies": 1, "undetected_restore_failures": 0,
        },
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {
            "database": "REQUIRED", "media": "NOT_APPLICABLE",
            "repository": "REQUIRED",
        },
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "google_drive"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


class RecoveryContractTests(unittest.TestCase):
    def test_manifest_v1_schema_and_validator_are_closed_and_deterministic(self):
        first = manifest()
        second = copy.deepcopy(first)
        second["sources"] = dict(reversed(list(second["sources"].items())))
        self.assertEqual(canonical_recovery_manifest(first), canonical_recovery_manifest(second))
        schema = json.loads((ROOT / "recovery" / "contract.schema.json").read_text())
        self.assertEqual(schema["properties"]["version"]["const"], 1)
        self.assertFalse(schema["additionalProperties"])
        extra = manifest(); extra["future"] = True
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(extra)

    def test_manifest_models_32110_rpo_rto_retention_and_explicit_not_applicable(self):
        value = validate_recovery_manifest(manifest())
        self.assertEqual(
            value["protection"],
            {"copies": 3, "media_types": 2, "offsite_copies": 1,
             "immutable_copies": 1, "undetected_restore_failures": 0},
        )
        self.assertEqual(value["sources"]["media"], "NOT_APPLICABLE")
        self.assertEqual(value["target"], {"rpo_minutes": 15, "rto_minutes": 60})
        self.assertEqual(value["retention"]["monthly"], 12)
        self.assertEqual(value["offsite"]["cold_copy"], "google_drive")

    def test_invalid_sensitive_or_incoherent_manifest_fails_closed_without_echo(self):
        invalid = []
        value = manifest(); value["protection"]["copies"] = 2; invalid.append(value)
        value = manifest(); value["sources"] = {key: "NOT_APPLICABLE" for key in value["sources"]}; invalid.append(value)
        value = manifest(); value["retention"] = {key: 0 for key in value["retention"]}; invalid.append(value)
        value = manifest(); value["target"]["rpo_minutes"] = True; invalid.append(value)
        secret = "token=supersecretvalue"
        value = manifest(); value["project"] = secret; invalid.append(value)
        for value in invalid:
            with self.subTest(case=str(value)[:50]), self.assertRaises(RecoveryContractError) as ctx:
                validate_recovery_manifest(value)
            self.assertNotIn("supersecretvalue", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
