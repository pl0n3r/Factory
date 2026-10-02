#!/usr/bin/env python3
"""Regresiones del schema interoperable del handoff desatendido Factory#797."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "unattended-handoff-v1.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "unattended_handoff_v1"
FIXTURE_NAMES = ("allow", "pause", "blocked", "unknown")


def _load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_ref(root: dict[str, object], ref: str) -> dict[str, object]:
    if not ref.startswith("#/"):
        raise AssertionError(f"external ref not allowed in test validator: {ref}")
    current: object = root
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            raise AssertionError(f"invalid schema ref: {ref}")
        current = current[key]
    if not isinstance(current, dict):
        raise AssertionError(f"schema ref must resolve to object: {ref}")
    return current


def _type_matches(value: object, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise AssertionError(f"unsupported schema type in test validator: {expected}")


def _validate(
    value: object,
    schema: dict[str, object],
    *,
    root: dict[str, object],
    path: str = "$",
) -> list[str]:
    errors: list[str] = []

    ref = schema.get("$ref")
    if isinstance(ref, str):
        return _validate(value, _resolve_ref(root, ref), root=root, path=path)

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for index, branch in enumerate(all_of):
            if not isinstance(branch, dict):
                errors.append(f"{path}: allOf[{index}] is not a schema object")
                continue
            errors.extend(_validate(value, branch, root=root, path=path))

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        if not any(
            isinstance(branch, dict)
            and not _validate(value, branch, root=root, path=path)
            for branch in any_of
        ):
            errors.append(f"{path}: does not match anyOf")
        return errors

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = sum(
            1
            for branch in one_of
            if isinstance(branch, dict)
            and not _validate(value, branch, root=root, path=path)
        )
        if matches != 1:
            errors.append(f"{path}: matches {matches} oneOf branches")
        return errors

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not _type_matches(value, expected_type):
            return [f"{path}: expected {expected_type}"]
    elif isinstance(expected_type, list):
        allowed = [item for item in expected_type if isinstance(item, str)]
        if not any(_type_matches(value, item) for item in allowed):
            return [f"{path}: expected one of {allowed}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const mismatch")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: enum mismatch")

    if isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        pattern = schema.get("pattern")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: shorter than minLength")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: longer than maxLength")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{path}: pattern mismatch")

    if isinstance(value, list):
        if schema.get("uniqueItems") is True:
            serialized = [json.dumps(item, sort_keys=True) for item in value]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{path}: items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate(item, item_schema, root=root, path=f"{path}[{index}]")
                )

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}: missing {key}")
        properties = schema.get("properties")
        if isinstance(properties, dict):
            if schema.get("additionalProperties") is False:
                extra = sorted(set(value) - set(properties))
                if extra:
                    errors.append(f"{path}: extra properties {extra}")
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(
                        _validate(
                            value[key],
                            child_schema,
                            root=root,
                            path=f"{path}.{key}",
                        )
                    )

    return errors


class UnattendedHandoffSchemaTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = _load_json(SCHEMA_PATH)
        assert isinstance(cls.schema, dict)

    def assertValid(self, payload: object) -> None:  # noqa: N802 - unittest idiom
        errors = _validate(payload, self.schema, root=self.schema)
        self.assertEqual(errors, [], "\n".join(errors))

    def assertInvalid(self, payload: object) -> None:  # noqa: N802 - unittest idiom
        errors = _validate(payload, self.schema, root=self.schema)
        self.assertTrue(errors, "payload unexpectedly matched the schema")

    def test_schema_accepts_canonical_allow_pause_blocked_unknown_fixtures(self):
        fixtures: dict[str, object] = {}
        for name in FIXTURE_NAMES:
            payload = _load_json(FIXTURE_DIR / f"{name}.json")
            self.assertValid(payload)
            fixtures[name] = payload

        self.assertEqual(fixtures["allow"]["action"], "ALLOW")
        self.assertEqual(fixtures["pause"]["action"], "PAUSE")
        self.assertEqual(fixtures["blocked"]["action"], "BLOCKED")
        self.assertEqual(fixtures["unknown"]["freshness"], "unknown")
        self.assertIsNone(fixtures["unknown"]["provenance"])

    def test_extra_sensitive_unknown_or_contradictory_fields_fail_closed(self):
        allow = _load_json(FIXTURE_DIR / "allow.json")
        assert isinstance(allow, dict)

        cases: dict[str, dict[str, object]] = {}

        payload = deepcopy(allow)
        payload["unexpected"] = True
        cases["extra"] = payload

        payload = deepcopy(allow)
        payload["token"] = "must-never-be-part-of-the-contract"
        cases["sensitive"] = payload

        payload = deepcopy(allow)
        payload["version"] = 2
        cases["unknown_version"] = payload

        payload = deepcopy(allow)
        payload["next_transition"] = "PAUSE"
        cases["action_transition_contradiction"] = payload

        payload = deepcopy(allow)
        provenance = payload["provenance"]
        assert isinstance(provenance, dict)
        provenance["freshness"] = "stale"
        cases["freshness_contradiction"] = payload

        payload = deepcopy(allow)
        permissions = payload["permissions"]
        assert isinstance(permissions, dict)
        permissions["merge"] = True
        cases["authority_expansion"] = payload

        payload = deepcopy(allow)
        provenance = payload["provenance"]
        assert isinstance(provenance, dict)
        provenance["secret"] = "nope"
        cases["nested_sensitive"] = payload

        for name, payload in cases.items():
            with self.subTest(name=name):
                self.assertInvalid(payload)


if __name__ == "__main__":
    import unittest

    unittest.main()
