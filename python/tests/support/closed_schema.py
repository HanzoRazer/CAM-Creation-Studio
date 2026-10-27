"""Closed-schema checks for witness documents.

This is a test helper for the subset of JSON Schema used by the local
contracts. It is not a general validator and it is not a runtime dependency.
"""

from __future__ import annotations

import re
from pathlib import Path


def load_schema(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance: object, schema: dict) -> list[str]:
    """Return a list of errors. An empty list means the instance matches."""
    errors: list[str] = []
    _check(instance, schema, schema, "$", errors)
    return errors


def _check(instance, schema: dict, root: dict, where: str, errors: list[str]) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            errors.append(f"{where}: unsupported ref {ref!r}")
            return
        name = ref.split("/")[-1]
        target = root.get("$defs", {}).get(name)
        if not isinstance(target, dict):
            errors.append(f"{where}: missing $defs/{name}")
            return
        _check(instance, target, root, where, errors)
        return
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{where}: expected const {schema['const']!r}")
        return
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{where}: value not in enum")
        return
    expected = schema.get("type")
    if expected is not None and not _type_ok(instance, expected):
        errors.append(f"{where}: type {type(instance).__name__} is not {expected}")
        return
    if isinstance(instance, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(instance) < minimum:
            errors.append(f"{where}: shorter than minLength")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{where}: does not match {pattern}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "exclusiveMinimum" in schema and not instance > schema["exclusiveMinimum"]:
            errors.append(f"{where}: not above exclusiveMinimum")
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{where}: below minimum")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{where}: missing {key}")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{where}: unexpected {key}")
        for key, value in instance.items():
            if key in properties:
                _check(value, properties[key], root, f"{where}.{key}", errors)
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            _check(item, schema["items"], root, f"{where}[{index}]", errors)


def _type_ok(instance: object, expected: object) -> bool:
    if isinstance(expected, list):
        return any(_type_ok(instance, item) for item in expected)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    return False
