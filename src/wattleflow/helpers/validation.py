# Module name: helpers/validation.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
JSON Schema subset validator, stdlib only. Stands in for `jsonschema.validate`
(DR-WFL-003) and is the schema check every configuration format uses — it
belongs to no single format, so it lives as a capability rather than inside a
parser (NFRQ-ORG-01).

Unsupported keywords raise rather than pass quietly: a validator that cannot
see a constraint must not report conformance to it.
"""


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import re
from typing import Any, ClassVar

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["SchemaValidator", "ValidationError"]


# --------------------------------------------------------------------------- #
# region Schema validation                                                    #
# --------------------------------------------------------------------------- #


class ValidationError(ValueError, TypeError):
    """Schema violation.

    Derives from both `ValueError` and `TypeError` because the previous
    implementation raised one or the other depending on the keyword; callers
    catching either keep working.
    """


# v0.0.0.97 (NFRQ-ORG-05): the keyword table and the checks that read it are one
# qualified unit — constants as class attributes, no module-level helpers.
class SchemaValidator:
    """Validates an instance against a JSON Schema subset."""

    TYPES: ClassVar[dict[str, Any]] = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }

    UNSUPPORTED: ClassVar[tuple[str, ...]] = (
        "$ref",
        "$dynamicRef",
        "dependentSchemas",
        "if",
    )

    @classmethod
    def validate(cls, instance: Any, schema: Any) -> None:
        """Validate `instance` against a JSON Schema subset.

        Fallback for `jsonschema.validate`. Unsupported keywords raise instead
        of passing quietly — a validator that cannot see a constraint must not
        report conformance to it.
        """
        if schema is True:
            return
        if schema is False:
            raise ValidationError("Schema `false` rejects every instance")
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a dict or a boolean")

        for unsupported in cls.UNSUPPORTED:
            if unsupported in schema:
                raise ValueError(f"Unsupported schema keyword: {unsupported}")

        cls._check_type(instance, schema)
        cls._check_choice(instance, schema)
        cls._check_combinators(instance, schema)

        # Applied on the instance, not on a sibling `type` declaration — JSON
        # Schema keywords are conditional on the instance itself.
        if isinstance(instance, dict):
            cls._check_object(instance, schema)
        if isinstance(instance, list):
            cls._check_array(instance, schema)
        if isinstance(instance, str):
            cls._check_string(instance, schema)
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            cls._check_numeric(instance, schema)

    # region Keyword groups

    @classmethod
    def _check_type(cls, instance: Any, schema: dict) -> None:
        declared = schema.get("type")
        if declared is None:
            return
        names = declared if isinstance(declared, list) else [declared]
        if not any(cls._is_type(instance, name) for name in names):
            got = type(instance).__name__
            raise ValidationError(f"Expected type '{declared}', got '{got}'")

    @classmethod
    def _check_choice(cls, instance: Any, schema: dict) -> None:
        if "enum" in schema:
            if not any(cls._equal(instance, option) for option in schema["enum"]):
                raise ValidationError(f"Value {instance!r} is not one of {schema['enum']!r}")
        if "const" in schema and not cls._equal(instance, schema["const"]):
            raise ValidationError(f"Value {instance!r} != const {schema['const']!r}")

    @classmethod
    def _check_combinators(cls, instance: Any, schema: dict) -> None:
        for keyword in ("allOf", "anyOf", "oneOf"):
            if keyword not in schema:
                continue
            matched = sum(1 for sub in schema[keyword] if cls._valid(instance, sub))
            total = len(schema[keyword])
            if keyword == "allOf" and matched != total:
                raise ValidationError("Instance fails allOf")
            if keyword == "anyOf" and matched == 0:
                raise ValidationError("Instance matches no anyOf branch")
            if keyword == "oneOf" and matched != 1:
                raise ValidationError(f"Instance matches {matched} oneOf branches, expected 1")
        if "not" in schema and cls._valid(instance, schema["not"]):
            raise ValidationError("Instance must not match the `not` schema")

    @classmethod
    def _check_object(cls, instance: dict, schema: dict) -> None:
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})

        for key in schema.get("required", []):
            if key not in instance:
                raise ValidationError(f"Missing required property: {key}")

        min_props, max_props = schema.get("minProperties"), schema.get("maxProperties")
        if min_props is not None and len(instance) < min_props:
            raise ValidationError(f"Object has {len(instance)} properties < {min_props}")
        if max_props is not None and len(instance) > max_props:
            raise ValidationError(f"Object has {len(instance)} properties > {max_props}")

        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            matched = False
            if key in properties:
                cls.validate(value, properties[key])
                matched = True
            for expression, sub in pattern_properties.items():
                if re.search(expression, str(key)):
                    cls.validate(value, sub)
                    matched = True
            if matched:
                continue
            if additional is False:
                raise ValidationError(f"Additional property not allowed: {key}")
            if additional is not True:
                cls.validate(value, additional)

    @classmethod
    def _check_array(cls, instance: list, schema: dict) -> None:
        items_schema = schema.get("items")
        if isinstance(items_schema, list):
            # Positional schemas; surplus items stay unconstrained.
            for item, sub in zip(instance, items_schema, strict=False):
                cls.validate(item, sub)
        elif items_schema is not None:
            for item in instance:
                cls.validate(item, items_schema)

        min_items, max_items = schema.get("minItems"), schema.get("maxItems")
        if min_items is not None and len(instance) < min_items:
            raise ValidationError(f"Array has {len(instance)} items < {min_items}")
        if max_items is not None and len(instance) > max_items:
            raise ValidationError(f"Array has {len(instance)} items > {max_items}")

        if schema.get("uniqueItems"):
            for i, item in enumerate(instance):
                if any(cls._equal(item, other) for other in instance[:i]):
                    raise ValidationError(f"Array items are not unique: {item!r}")

    @classmethod
    def _check_string(cls, instance: str, schema: dict) -> None:
        min_len, max_len = schema.get("minLength"), schema.get("maxLength")
        if min_len is not None and len(instance) < min_len:
            raise ValidationError(f"String shorter than minLength {min_len}")
        if max_len is not None and len(instance) > max_len:
            raise ValidationError(f"String longer than maxLength {max_len}")
        expression = schema.get("pattern")
        if expression is not None and not re.search(expression, instance):
            raise ValidationError(f"String {instance!r} does not match {expression!r}")

    @classmethod
    def _check_numeric(cls, instance: int | float, schema: dict) -> None:
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if minimum is not None and instance < minimum:
            raise ValidationError(f"Value {instance} < minimum {minimum}")
        if maximum is not None and instance > maximum:
            raise ValidationError(f"Value {instance} > maximum {maximum}")

        exclusive_min = schema.get("exclusiveMinimum")
        exclusive_max = schema.get("exclusiveMaximum")
        if isinstance(exclusive_min, (int, float)) and instance <= exclusive_min:
            raise ValidationError(f"Value {instance} <= exclusiveMinimum {exclusive_min}")
        if isinstance(exclusive_max, (int, float)) and instance >= exclusive_max:
            raise ValidationError(f"Value {instance} >= exclusiveMaximum {exclusive_max}")

        multiple = schema.get("multipleOf")
        if multiple:
            quotient = instance / multiple
            if abs(quotient - round(quotient)) > 1e-9:
                raise ValidationError(f"Value {instance} is not a multiple of {multiple}")

    # endregion

    # region Predicates

    @classmethod
    def _is_type(cls, instance: Any, name: str) -> bool:
        if name not in cls.TYPES:
            raise ValueError(f"Unsupported type: {name}")
        # JSON Schema keeps booleans out of the numeric types even though Python
        # makes bool a subclass of int.
        if isinstance(instance, bool):
            return name == "boolean"
        if name == "integer":
            return isinstance(instance, int) or (
                isinstance(instance, float) and instance.is_integer()
            )
        return isinstance(instance, cls.TYPES[name])

    @classmethod
    def _equal(cls, a: Any, b: Any) -> bool:
        """JSON Schema equality — 1 and True are distinct, 1 and 1.0 are not."""
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a == b
        if type(a) is not type(b):
            return False
        if isinstance(a, list):
            return len(a) == len(b) and all(cls._equal(x, y) for x, y in zip(a, b, strict=True))
        if isinstance(a, dict):
            return a.keys() == b.keys() and all(cls._equal(v, b[k]) for k, v in a.items())
        return a == b

    @classmethod
    def _valid(cls, instance: Any, schema: Any) -> bool:
        try:
            cls.validate(instance, schema)
            return True
        except ValidationError:
            return False

    # endregion


# --------------------------------------------------------------------------- #
# endregion Schema validation                                                 #
# --------------------------------------------------------------------------- #
