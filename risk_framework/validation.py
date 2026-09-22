"""Small strict validators shared by inputs and configuration."""
from __future__ import annotations

import json
import math
from typing import Any


class ValidationError(ValueError):
    """An input or policy cannot be interpreted safely."""


def identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValidationError(f"{name} must be a nonempty string without surrounding whitespace")
    return value


def number(value: Any, name: str, minimum: float | None = None,
           maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a finite number (not a string or boolean)")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValidationError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{name} must be finite")
    if minimum is not None and result < minimum or maximum is not None and result > maximum:
        raise ValidationError(f"{name} must be within [{minimum}, {maximum}]")
    return result


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"{name} must be an integer >= {minimum}")
    return value


def json_value(value: Any, name: str = "metadata") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        number(value, name)
    elif isinstance(value, list):
        for item in value:
            json_value(item, name)
    elif isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for item in value.values():
            json_value(item, name)
    else:
        raise ValidationError(f"{name} must contain only JSON values and string object keys")


def object_fields(value: Any, allowed: set[str], required: set[str], name: str) -> dict:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValidationError(f"{name} must be a JSON object")
    unknown, missing = set(value) - allowed, required - set(value)
    if unknown or missing:
        raise ValidationError(f"{name}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}")
    return value


def parse_json(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValidationError(f"Duplicate JSON object key: {key}")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValidationError(f"Non-finite JSON number: {value}")

    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
        json_value(result, "JSON input")
        return result
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON: {exc}") from exc
