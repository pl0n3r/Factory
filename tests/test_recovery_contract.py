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

        # AC-03: malformed JSON unicode must yield the same typed, sanitized
        # failure for both entry points, never a raw UnicodeEncodeError.
        lone_surrogate = json.loads('"\\ud800"')
        for field in ("project", "key_material"):
            malformed = manifest()
            if field == "project":
                malformed["project"] = lone_surrogate
            else:
                malformed["encryption"]["key_material"] = lone_surrogate
            for validator in (validate_recovery_manifest, canonical_recovery_manifest):
                with self.subTest(field=field, validator=validator.__name__):
                    with self.assertRaisesRegex(
                        RecoveryContractError, "manifest debe ser JSON finito"
                    ) as error:
                        validator(malformed)
                    self.assertIsNone(error.exception.__cause__)
                    self.assertIsNone(error.exception.__context__)
                    self.assertNotIn("token=", str(error.exception))


    def test_nonstring_catalog_enums_fail_closed_without_typeerror(self):
        # AC-03: cadenas de catálogo incorrectas producen solo el error público.
        for field in ("database", "media", "repository"):
            for invalid in ([], {}, None, 0, True):
                for validator in (validate_recovery_manifest, canonical_recovery_manifest):
                    value = manifest()
                    value["sources"][field] = invalid
                    with self.subTest(source=field, invalid=repr(invalid), fn=validator.__name__):
                        with self.assertRaisesRegex(
                            RecoveryContractError, "sources contiene estado fuera del catálogo"
                        ) as caught:
                            validator(value)
                        self.assertIsNone(caught.exception.__cause__)
        for invalid in ([], {}, None, 0, True):
            for validator in (validate_recovery_manifest, canonical_recovery_manifest):
                value = manifest()
                value["offsite"]["cold_copy"] = invalid
                with self.subTest(cold_copy=repr(invalid), fn=validator.__name__):
                    with self.assertRaisesRegex(
                        RecoveryContractError, "offsite incompatible con contrato 3-2-1-1-0"
                    ) as caught:
                        validator(value)
                    self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(validate_recovery_manifest(manifest()), manifest())


    def test_version_requires_strict_integer_one(self):
        valid = manifest()
        self.assertEqual(validate_recovery_manifest(valid)["version"], 1)
        self.assertIs(type(validate_recovery_manifest(valid)["version"]), int)
        for invalid in (True, False, 1.0, 0.0, "1", None, 2, -1):
            with self.subTest(version=repr(invalid)):
                value = manifest()
                value["version"] = invalid
                with self.assertRaises(RecoveryContractError) as ctx:
                    validate_recovery_manifest(value)
                self.assertEqual(str(ctx.exception), "version debe ser 1.")
                with self.assertRaises(RecoveryContractError):
                    canonical_recovery_manifest(value)

    def test_protection_numbers_reject_bool_and_float_aliases(self):
        expected = manifest()["protection"]
        self.assertEqual(validate_recovery_manifest(manifest())["protection"], expected)
        for key, number in expected.items():
            # True == 1, False == 0, and integer-valued floats compare equal
            # to their canonical integers; all are invalid JSON Schema types.
            for invalid in (True, False, float(number), str(number), None):
                with self.subTest(field=key, invalid=repr(invalid)):
                    value = manifest()
                    value["protection"][key] = invalid
                    with self.assertRaises(RecoveryContractError) as ctx:
                        validate_recovery_manifest(value)
                    self.assertEqual(
                        str(ctx.exception),
                        "protection debe cumplir exactamente 3-2-1-1-0.",
                    )
        for key, number in expected.items():
            value = manifest()
            value["protection"][key] = number + 1
            with self.subTest(field=key, invalid="noncanonical"):
                with self.assertRaises(RecoveryContractError):
                    validate_recovery_manifest(value)

    def test_valid_manifest_remains_canonical_after_strict_type_checks(self):
        value = manifest()
        before = json.dumps(
            value, sort_keys=True, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        )
        after = canonical_recovery_manifest(value)
        self.assertEqual(before, after)
        self.assertEqual(validate_recovery_manifest(value), value)
        reordered = copy.deepcopy(value)
        reordered["protection"] = dict(reversed(list(value["protection"].items())))
        self.assertEqual(canonical_recovery_manifest(reordered), after)
        import hashlib
        self.assertEqual(
            hashlib.sha256(after.encode("utf-8")).hexdigest(),
            hashlib.sha256(before.encode("utf-8")).hexdigest(),
        )
        secret = "token=private-secret-sentinel"
        hostile = manifest()
        hostile["project"] = secret
        with self.assertRaises(RecoveryContractError) as ctx:
            validate_recovery_manifest(hostile)
        self.assertNotIn(secret, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
