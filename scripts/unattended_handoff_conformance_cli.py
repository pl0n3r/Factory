#!/usr/bin/env python3
"""CLI offline de conformidad para el handoff desatendido Factory v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import TextIO


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "config" / "unattended-handoff-v1.schema.json"
MAX_INPUT_BYTES = 1_048_576


class ConformanceError(ValueError):
    """Entrada o contrato local inválido."""


def _no_duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ConformanceError("duplicate_json_key")
        result[key] = value
    return result


def _decode_json(raw: str) -> object:
    if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ConformanceError("input_too_large")
    try:
        return json.loads(raw, object_pairs_hook=_no_duplicate_object)
    except ConformanceError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ConformanceError("invalid_json") from exc


def _load_schema() -> dict[str, object]:
    try:
        raw = SCHEMA_PATH.read_text(encoding="utf-8")
        schema = _decode_json(raw)
    except (OSError, ConformanceError) as exc:
        raise ConformanceError("canonical_schema_unavailable") from exc
    if not isinstance(schema, dict):
        raise ConformanceError("canonical_schema_invalid")
    return schema


def _resolve_ref(root: dict[str, object], ref: str) -> dict[str, object]:
    if not ref.startswith("#/"):
        raise ConformanceError("external_schema_ref_forbidden")
    current: object = root
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            raise ConformanceError("canonical_schema_invalid")
        current = current[key]
    if not isinstance(current, dict):
        raise ConformanceError("canonical_schema_invalid")
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
    raise ConformanceError("canonical_schema_invalid")


def _validate(
    value: object,
    schema: dict[str, object],
    *,
    root: dict[str, object],
) -> bool:
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return _validate(value, _resolve_ref(root, ref), root=root)

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        if any(
            not isinstance(branch, dict)
            or not _validate(value, branch, root=root)
            for branch in all_of
        ):
            return False

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        return any(
            isinstance(branch, dict)
            and _validate(value, branch, root=root)
            for branch in any_of
        )

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = sum(
            1
            for branch in one_of
            if isinstance(branch, dict)
            and _validate(value, branch, root=root)
        )
        return matches == 1

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not _type_matches(value, expected_type):
            return False
    elif isinstance(expected_type, list):
        allowed = [item for item in expected_type if isinstance(item, str)]
        if not allowed or not any(_type_matches(value, item) for item in allowed):
            return False

    if "const" in schema and value != schema["const"]:
        return False
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False

    if isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        pattern = schema.get("pattern")
        if isinstance(minimum, int) and len(value) < minimum:
            return False
        if isinstance(maximum, int) and len(value) > maximum:
            return False
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            return False

    if isinstance(value, list):
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                return False
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            if any(not _validate(item, item_schema, root=root) for item in value):
                return False

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            if any(isinstance(key, str) and key not in value for key in required):
                return False
        properties = schema.get("properties")
        if isinstance(properties, dict):
            if schema.get("additionalProperties") is False:
                if set(value) - set(properties):
                    return False
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    if not _validate(value[key], child_schema, root=root):
                        return False

    return True


def evaluate_document(payload: object) -> dict[str, object]:
    """Valida contra el schema canónico sin exponer el contenido del payload."""

    schema = _load_schema()
    try:
        conformant = _validate(payload, schema, root=schema)
    except ConformanceError:
        raise
    return {
        "version": 1,
        "conformant": conformant,
        "code": "conformant" if conformant else "schema_validation_failed",
    }


def _read_input(source: str, stdin: TextIO) -> object:
    if source == "-":
        raw = stdin.read(MAX_INPUT_BYTES + 1)
        if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ConformanceError("input_too_large")
        return _decode_json(raw)

    path = Path(source)
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ConformanceError("input_too_large")
        return _decode_json(path.read_text(encoding="utf-8"))
    except ConformanceError:
        raise
    except OSError as exc:
        raise ConformanceError("input_unavailable") from exc


def _emit(stdout: TextIO, *, conformant: bool, code: str) -> None:
    output = {"version": 1, "conformant": conformant, "code": code}
    stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Valida un handoff JSON local contra el contrato canónico v1."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="-",
        help="Ruta local del JSON; '-' o ausencia lee stdin.",
    )
    args = parser.parse_args(argv)
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout

    try:
        payload = _read_input(args.source, input_stream)
        result = evaluate_document(payload)
    except ConformanceError as exc:
        _emit(output_stream, conformant=False, code=str(exc))
        return 2

    _emit(
        output_stream,
        conformant=bool(result["conformant"]),
        code=str(result["code"]),
    )
    return 0 if result["conformant"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
