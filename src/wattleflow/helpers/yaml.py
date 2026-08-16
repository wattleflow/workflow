# Module name: helpers/yaml.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Minimal YAML subset loader compatible with PyYAML.safe_load for the
Wattleflow framework. Supports block mappings, block sequences, block scalars
(`|`, `>` with chomping and indent indicators), anchors, aliases and merge
keys, flow collections, scalars (quoted and plain), booleans, nulls, ints and
floats. It handles the `- key: value` list-item pattern, sequences indented at
their parent key's level, and non-uniform indentation without assuming a fixed
indent step.

Anything the subset cannot represent raises `yaml.YAMLError`. Silence is not an
option here: this module is the declared stdlib fallback for PyYAML
(DR-WFL-003), so a construct it parses differently must fail loudly rather than
return a truncated document.
"""


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterator

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["yaml", "validate", "ValidationError"]

# Marks a line whose value was already resolved during line preparation
# (block scalars), so the parser must not re-scan its text.
_NO_VALUE: Any = object()

_MAX_DEPTH = 200

# Plain-scalar resolution follows the YAML 1.1 core schema as PyYAML implements
# it, not JSON intuition. The differences are not cosmetic: `012` is octal (10,
# not 12), an exponent needs an explicit sign, and `None` is the string "None".
_BOOL_TRUE = frozenset({"yes", "Yes", "YES", "true", "True", "TRUE", "on", "On", "ON"})
_BOOL_FALSE = frozenset({"no", "No", "NO", "false", "False", "FALSE", "off", "Off", "OFF"})
_NULL = frozenset({"~", "null", "Null", "NULL", ""})

_INT_RE = re.compile(
    r"""^(?:[-+]?0b[01_]+
        |[-+]?0[0-7_]+
        |[-+]?(?:0|[1-9][0-9_]*)
        |[-+]?0x[0-9a-fA-F_]+
        |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$""",
    re.X,
)

_FLOAT_RE = re.compile(
    r"""^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?
        |\.[0-9_]+(?:[eE][-+][0-9]+)?
        |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
        |[-+]?\.(?:inf|Inf|INF)
        |\.(?:nan|NaN|NAN))$""",
    re.X,
)


# PyYAML resolves with a stricter pattern than it constructs with: a date-only
# value must use two-digit month and day, so `2026-8-4` stays a string.
_TIMESTAMP_RESOLVE_RE = re.compile(
    r"""^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]
        |[0-9][0-9][0-9][0-9] -[0-9][0-9]? -[0-9][0-9]?
         (?:[Tt]|[ \t]+)[0-9][0-9]?
         :[0-9][0-9] :[0-9][0-9] (?:\.[0-9]*)?
         (?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$""",
    re.X,
)

_TIMESTAMP_RE = re.compile(
    r"""^(?P<year>[0-9][0-9][0-9][0-9])
        -(?P<month>[0-9][0-9]?)
        -(?P<day>[0-9][0-9]?)
        (?:(?:[Tt]|[ \t]+)
        (?P<hour>[0-9][0-9]?)
        :(?P<minute>[0-9][0-9])
        :(?P<second>[0-9][0-9])
        (?:\.(?P<fraction>[0-9]*))?
        (?:[ \t]*(?P<tz>Z|(?P<tz_sign>[-+])(?P<tz_hour>[0-9][0-9]?)
        (?::(?P<tz_minute>[0-9][0-9]))?))?)?$""",
    re.X,
)


def _build_timestamp(match: re.Match) -> date | datetime:
    values = match.groupdict()
    year, month, day = (int(values[k]) for k in ("year", "month", "day"))
    if not values["hour"]:
        return date(year, month, day)

    fraction = 0
    if values["fraction"]:
        fraction = int(values["fraction"][:6].ljust(6, "0"))

    tzinfo = None
    if values["tz_sign"]:
        delta = timedelta(hours=int(values["tz_hour"]), minutes=int(values["tz_minute"] or 0))
        tzinfo = timezone(-delta if values["tz_sign"] == "-" else delta)
    elif values["tz"]:
        tzinfo = timezone.utc

    return datetime(
        year,
        month,
        day,
        int(values["hour"]),
        int(values["minute"]),
        int(values["second"]),
        fraction,
        tzinfo=tzinfo,
    )


def _build_int(value: str) -> int:
    value = value.replace("_", "")
    sign = -1 if value[0] == "-" else 1
    if value[0] in "+-":
        value = value[1:]
    if value == "0":
        return 0
    if value.startswith("0b"):
        return sign * int(value[2:], 2)
    if value.startswith("0x"):
        return sign * int(value[2:], 16)
    if value[0] == "0":
        return sign * int(value, 8)
    if ":" in value:
        total, base = 0, 1
        for digit in reversed(value.split(":")):
            total += int(digit) * base
            base *= 60
        return sign * total
    return sign * int(value)


def _build_float(value: str) -> float:
    value = value.replace("_", "").lower()
    sign = -1 if value[0] == "-" else 1
    if value[0] in "+-":
        value = value[1:]
    if value == ".inf":
        return sign * float("inf")
    if value == ".nan":
        return float("nan")
    if ":" in value:
        total, base = 0.0, 1
        for digit in reversed(value.split(":")):
            total += float(digit) * base
            base *= 60
        return sign * total
    return sign * float(value)


# --------------------------------------------------------------------------- #
# region Schema validation                                                    #
# --------------------------------------------------------------------------- #


class ValidationError(ValueError, TypeError):
    """Schema violation.

    Derives from both `ValueError` and `TypeError` because the previous
    implementation raised one or the other depending on the keyword; callers
    catching either keep working.
    """


_TYPE_MAP: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _is_type(instance: Any, name: str) -> bool:
    if name not in _TYPE_MAP:
        raise ValueError(f"Unsupported type: {name}")
    # JSON Schema keeps booleans out of the numeric types even though Python
    # makes bool a subclass of int.
    if isinstance(instance, bool):
        return name == "boolean"
    if name == "integer":
        return isinstance(instance, int) or (isinstance(instance, float) and instance.is_integer())
    return isinstance(instance, _TYPE_MAP[name])


def _equal(a: Any, b: Any) -> bool:
    """JSON Schema equality — 1 and True are distinct, 1 and 1.0 are not."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_equal(v, b[k]) for k, v in a.items())
    return a == b


def _valid(instance: Any, schema: Any) -> bool:
    try:
        validate(instance, schema)
        return True
    except ValidationError:
        return False


def validate(instance: Any, schema: Any) -> None:
    """Validate `instance` against a JSON Schema subset.

    Fallback for `jsonschema.validate`. Unsupported keywords raise instead of
    passing quietly — a validator that cannot see a constraint must not report
    conformance to it.
    """
    if schema is True:
        return
    if schema is False:
        raise ValidationError("Schema `false` rejects every instance")
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a dict or a boolean")

    for unsupported in ("$ref", "$dynamicRef", "dependentSchemas", "if"):
        if unsupported in schema:
            raise ValueError(f"Unsupported schema keyword: {unsupported}")

    # region type
    declared = schema.get("type")
    if declared is not None:
        names = declared if isinstance(declared, list) else [declared]
        if not any(_is_type(instance, name) for name in names):
            got = type(instance).__name__
            raise ValidationError(f"Expected type '{declared}', got '{got}'")
    # endregion

    # region enum / const
    if "enum" in schema:
        if not any(_equal(instance, option) for option in schema["enum"]):
            raise ValidationError(f"Value {instance!r} is not one of {schema['enum']!r}")
    if "const" in schema and not _equal(instance, schema["const"]):
        raise ValidationError(f"Value {instance!r} != const {schema['const']!r}")
    # endregion

    # region combinators
    for keyword in ("allOf", "anyOf", "oneOf"):
        if keyword not in schema:
            continue
        matched = sum(1 for sub in schema[keyword] if _valid(instance, sub))
        total = len(schema[keyword])
        if keyword == "allOf" and matched != total:
            raise ValidationError("Instance fails allOf")
        if keyword == "anyOf" and matched == 0:
            raise ValidationError("Instance matches no anyOf branch")
        if keyword == "oneOf" and matched != 1:
            raise ValidationError(f"Instance matches {matched} oneOf branches, expected 1")
    if "not" in schema and _valid(instance, schema["not"]):
        raise ValidationError("Instance must not match the `not` schema")
    # endregion

    # region object
    # Applied on any mapping instance, not only when `type: object` is declared —
    # JSON Schema keywords are conditional on the instance, not on a sibling type.
    if isinstance(instance, dict):
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
                validate(value, properties[key])
                matched = True
            for expression, sub in pattern_properties.items():
                if re.search(expression, str(key)):
                    validate(value, sub)
                    matched = True
            if matched:
                continue
            if additional is False:
                raise ValidationError(f"Additional property not allowed: {key}")
            if additional is not True:
                validate(value, additional)
    # endregion

    # region array
    if isinstance(instance, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, list):
            # Positional schemas; surplus items stay unconstrained.
            for item, sub in zip(instance, items_schema, strict=False):
                validate(item, sub)
        elif items_schema is not None:
            for item in instance:
                validate(item, items_schema)

        min_items, max_items = schema.get("minItems"), schema.get("maxItems")
        if min_items is not None and len(instance) < min_items:
            raise ValidationError(f"Array has {len(instance)} items < {min_items}")
        if max_items is not None and len(instance) > max_items:
            raise ValidationError(f"Array has {len(instance)} items > {max_items}")

        if schema.get("uniqueItems"):
            for i, item in enumerate(instance):
                if any(_equal(item, other) for other in instance[:i]):
                    raise ValidationError(f"Array items are not unique: {item!r}")
    # endregion

    # region string
    if isinstance(instance, str):
        min_len, max_len = schema.get("minLength"), schema.get("maxLength")
        if min_len is not None and len(instance) < min_len:
            raise ValidationError(f"String shorter than minLength {min_len}")
        if max_len is not None and len(instance) > max_len:
            raise ValidationError(f"String longer than maxLength {max_len}")
        expression = schema.get("pattern")
        if expression is not None and not re.search(expression, instance):
            raise ValidationError(f"String {instance!r} does not match {expression!r}")
    # endregion

    # region numeric
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
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


# --------------------------------------------------------------------------- #
# endregion Schema validation                                                 #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region yaml                                                                 #
# --------------------------------------------------------------------------- #


class yaml:
    """PyYAML-shaped facade. Lower-case by design — it stands in for
    `import yaml`, so the name is the contract (deviation from §2.3)."""

    class YAMLError(Exception):
        pass

    class _State:
        __slots__ = ("lines", "i")

        def __init__(self, lines):
            self.lines = lines
            self.i = 0

        def done(self) -> bool:
            return self.i >= len(self.lines)

        def peek(self):
            return self.lines[self.i]

        def advance(self) -> None:
            self.i += 1

    def __init__(self, file_path: str | None = None):
        self.yaml: Any = None
        self.file_path: str | None = file_path
        self._anchors: dict[str, Any] = {}

        if file_path is not None:
            self.yaml = self._load_yaml_file(file_path)

    # region scalar helpers
    def _strip_comment(self, s: str) -> str:
        """Drop a trailing comment. A quote only opens a quoted scalar at a
        token boundary, so an apostrophe inside a plain scalar (`John's file`)
        no longer swallows the rest of the line."""
        out: list[str] = []
        quote: str | None = None
        boundary = True
        i, n = 0, len(s)
        while i < n:
            c = s[i]
            if quote is not None:
                out.append(c)
                if c == quote:
                    if quote == "'" and i + 1 < n and s[i + 1] == "'":
                        out.append(s[i + 1])
                        i += 2
                        continue
                    quote = None
                elif quote == '"' and c == "\\" and i + 1 < n:
                    out.append(s[i + 1])
                    i += 2
                    continue
                i += 1
                continue
            if c in "\"'" and boundary:
                quote = c
                out.append(c)
                boundary = False
                i += 1
                continue
            if c == "#" and (i == 0 or s[i - 1] in (" ", "\t")):
                break
            out.append(c)
            boundary = c in " \t:,-[{"
            i += 1
        return "".join(out).rstrip()

    def _split_key(self, s: str) -> tuple[str, str, str]:
        """Split `key: rest`. Honours quoted keys and the YAML rule that a
        colon ends a plain key only when followed by a space or end of line."""
        n = len(s)
        if s[:1] in ('"', "'"):
            quote = s[0]
            i = 1
            while i < n:
                if s[i] == quote:
                    if quote == "'" and i + 1 < n and s[i + 1] == "'":
                        i += 2
                        continue
                    break
                if quote == '"' and s[i] == "\\":
                    i += 2
                    continue
                i += 1
            if i >= n:
                return s, "", ""
            after = s[i + 1 :]
            if after[:1] == ":" and (len(after) == 1 or after[1] == " "):
                return s[: i + 1], ":", after[1:]
            return s, "", ""

        depth = 0
        for i, c in enumerate(s):
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
            elif c == ":" and depth == 0 and (i + 1 == n or s[i + 1] == " "):
                return s[:i], ":", s[i + 1 :]
        return s, "", ""

    def _split_flow(self, body: str) -> list:
        """Split a flow-collection body on its top-level commas.

        Nesting and quoting are honoured, so `[a, [b, c], "d,e"]` yields three
        items rather than five.
        """
        items: list = []
        buf: list = []
        depth = 0
        in_s = in_d = False
        for c in body:
            if c == "'" and not in_d:
                in_s = not in_s
            elif c == '"' and not in_s:
                in_d = not in_d
            elif not in_s and not in_d:
                if c in "[{":
                    depth += 1
                elif c in "]}":
                    depth -= 1
                    if depth < 0:
                        raise yaml.YAMLError(f"unbalanced flow collection: {body!r}")
                elif c == "," and depth == 0:
                    items.append("".join(buf))
                    buf = []
                    continue
            buf.append(c)

        if depth != 0 or in_s or in_d:
            raise yaml.YAMLError(f"unterminated flow collection or quote: {body!r}")

        tail = "".join(buf).strip()
        if tail:
            items.append(tail)
        return [item.strip() for item in items if item.strip()]

    def _parse_scalar(self, s: str) -> Any:
        s = s.strip()
        if s == "":
            return ""

        if s.startswith("*"):
            return self._alias(s[1:].strip())

        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            _esc = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "\\": "\\",
                '"': '"',
                "0": "\0",
                "b": "\b",
                "f": "\f",
                "v": "\v",
                "/": "/",
                "'": "'",
            }
            return re.sub(
                r"\\(.)",
                lambda m: _esc.get(m.group(1), m.group(1)),
                s[1:-1],
            )

        if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
            return s[1:-1].replace("''", "'")

        # Flow collections — `[]`, `[a, b]`, `{}`, `{k: v}`. Without this branch
        # the shim returned the literal text, so a config saying
        # `repositories: []` produced the STRING "[]" and every consumer that
        # iterated it saw two characters instead of an empty collection. Quoted
        # forms are handled above, so `"[]"` stays a string, as in PyYAML.
        if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
            return [self._parse_scalar(item) for item in self._split_flow(s[1:-1])]

        if len(s) >= 2 and s[0] == "{" and s[-1] == "}":
            mapping: dict = {}
            for item in self._split_flow(s[1:-1]):
                key, sep, value = self._split_key(item)
                if not sep:
                    key, sep, value = item.partition(":")
                mapping[self._parse_scalar(key.strip())] = (
                    self._parse_scalar(value.strip()) if sep else None
                )
            return mapping

        if s in _NULL:
            return None
        if s in _BOOL_TRUE:
            return True
        if s in _BOOL_FALSE:
            return False

        if _INT_RE.match(s):
            try:
                return _build_int(s)
            except ValueError:
                pass

        if _FLOAT_RE.match(s):
            try:
                return _build_float(s)
            except ValueError:
                pass

        if _TIMESTAMP_RESOLVE_RE.match(s):
            # An out-of-range date raises, exactly as PyYAML does.
            return _build_timestamp(_TIMESTAMP_RE.match(s))

        # Tags change the constructed type, so guessing is not an option.
        if s.startswith("!"):
            raise yaml.YAMLError(f"tags are not supported by this loader: {s!r}")

        return s

    # endregion

    # region anchors and aliases
    def _alias(self, name: str) -> Any:
        if name not in self._anchors:
            raise yaml.YAMLError(f"undefined alias: *{name}")
        return self._anchors[name]

    def _take_anchor(self, rest: str) -> tuple[str | None, str]:
        """Peel a leading `&anchor` off a value, returning (name, remainder)."""
        if not rest.startswith("&"):
            return None, rest
        head, _, tail = rest.partition(" ")
        name = head[1:]
        if not name:
            raise yaml.YAMLError("anchor name must not be empty")
        return name, tail.strip()

    def _resolve_merge(self, rest: str) -> list[dict]:
        rest = rest.strip()
        items = self._split_flow(rest[1:-1]) if rest.startswith("[") else [rest]
        sources: list[dict] = []
        for item in items:
            item = item.strip()
            if not item.startswith("*"):
                raise yaml.YAMLError(f"merge key requires an alias, got {item!r}")
            value = self._alias(item[1:].strip())
            if not isinstance(value, dict):
                raise yaml.YAMLError("merge key alias must resolve to a mapping")
            sources.append(value)
        return sources

    # endregion

    # region block scalars
    @staticmethod
    def _block_header(s: str) -> tuple[str, str, int] | None:
        """Parse `|`, `>` and their chomping/indent indicators."""
        if not s or s[0] not in "|>":
            return None
        style, chomp, indent = s[0], "", 0
        for c in s[1:]:
            if c in "+-":
                if chomp:
                    return None
                chomp = c
            elif c.isdigit() and c != "0":
                if indent:
                    return None
                indent = int(c)
            else:
                return None
        return style, chomp, indent

    def _header_of(self, content: str) -> tuple[str, tuple[str, str, int]] | None:
        """Detect a block-scalar header, returning (line prefix, header)."""
        body, dash = content, ""
        if self._is_item(body):
            dash = "- "
            body = body[1:].lstrip(" ")
            if not body:
                return None
        key, sep, rest = self._split_key(body)
        if not sep:
            header = self._block_header(body) if dash else None
            return (dash.strip(), header) if header else None
        header = self._block_header(rest.strip())
        return (f"{dash}{key}:", header) if header else None

    @staticmethod
    def _fold(lines: list[str]) -> str:
        parts: list[str] = []
        pending: str | None = None
        for line in lines:
            if line.strip() == "":
                if pending is not None:
                    parts.append(pending)
                    pending = None
                parts.append("\n")
            elif line[:1] == " ":
                if pending is not None:
                    parts.append(pending)
                    parts.append("\n")
                    pending = None
                parts.append(line + "\n")
            else:
                pending = line if pending is None else f"{pending} {line}"
        if pending is not None:
            parts.append(pending)
        return "".join(parts)

    def _read_block(
        self,
        raw_lines: list[str],
        start: int,
        header_indent: int,
        style: str,
        chomp: str,
        indicator: int,
    ) -> tuple[str, int]:
        block_indent: int | None = header_indent + indicator if indicator else None
        body: list[str] = []
        i, n = start, len(raw_lines)

        while i < n:
            raw = raw_lines[i].replace("\t", "    ")
            if raw.strip() == "":
                body.append("")
                i += 1
                continue
            current = len(raw) - len(raw.lstrip(" "))
            if block_indent is None:
                if current <= header_indent:
                    break
                block_indent = current
            if current < block_indent:
                break
            body.append(raw[block_indent:])
            i += 1

        trailing = 0
        while body and body[-1] == "":
            body.pop()
            trailing += 1

        # `_fold` closes more-indented lines with a break, so normalise first and
        # let the chomping indicator alone decide the trailing newlines.
        text = ("\n".join(body) if style == "|" else self._fold(body)).rstrip("\n")
        if chomp == "-":
            return text, i
        if chomp == "+":
            return text + "\n" * (trailing + (1 if body else 0)), i
        return (text + "\n") if body else "", i

    # endregion

    # region line preparation
    @staticmethod
    def _is_item(content: str) -> bool:
        return content.startswith("-") and (len(content) == 1 or content[1] == " ")

    @staticmethod
    def _flow_balance(text: str) -> int:
        """Net `[`/`{` nesting outside quotes — >0 means the line stays open."""
        depth = 0
        in_s = in_d = False
        for c in text:
            if c == "'" and not in_d:
                in_s = not in_s
            elif c == '"' and not in_s:
                in_d = not in_d
            elif not in_s and not in_d:
                if c in "[{":
                    depth += 1
                elif c in "]}":
                    depth -= 1
        return depth

    def _prep_documents(self, text: str) -> list[list[tuple[int, str, Any]]]:
        """Split into documents of `(indent, content, resolved_value)` lines.

        Block-scalar bodies are consumed here, straight from the raw text, so
        comment stripping and blank-line removal never touch them.
        """
        documents: list[list[tuple[int, str, Any]]] = [[]]
        raw_lines = text.splitlines()
        i, n = 0, len(raw_lines)

        while i < n:
            raw = raw_lines[i]
            bare = raw.strip()
            if bare == "---" or bare.startswith("--- "):
                if documents[-1]:
                    documents.append([])
                remainder = bare[4:].strip()
                if remainder:
                    documents[-1].append((0, remainder, _NO_VALUE))
                i += 1
                continue
            if bare == "...":
                i += 1
                continue

            no_comment = self._strip_comment(raw)
            if not no_comment.strip():
                i += 1
                continue
            no_comment = no_comment.replace("\t", "    ")
            indent = len(no_comment) - len(no_comment.lstrip(" "))
            content = no_comment.strip()

            # A flow collection may span lines (plain JSON is valid YAML), so
            # keep folding until the brackets balance.
            while self._flow_balance(content) > 0 and i + 1 < n:
                i += 1
                nxt = self._strip_comment(raw_lines[i]).replace("\t", "    ").strip()
                if nxt:
                    content = f"{content} {nxt}"

            found = self._header_of(content)
            if found is not None:
                prefix, (style, chomp, indicator) = found
                value, i = self._read_block(raw_lines, i + 1, indent, style, chomp, indicator)
                documents[-1].append((indent, prefix, value))
                continue

            documents[-1].append((indent, content, _NO_VALUE))
            i += 1

        return [document for document in documents if document]

    # endregion

    # region recursive parser
    def _parse_block(
        self,
        st: _State,
        parent_indent: int,
        depth: int = 0,
        allow_seq_at_parent: bool = False,
    ) -> Any:
        if depth > _MAX_DEPTH:
            raise yaml.YAMLError("maximum nesting depth exceeded")
        if st.done():
            return None
        indent, content, _ = st.peek()
        # A sequence may sit at its parent *key's* indentation; before this the
        # parser returned None and silently abandoned the rest of the document.
        # It must not apply under a bare "-", where a same-indent item is the
        # next sibling entry, not a child.
        if indent == parent_indent:
            if allow_seq_at_parent and self._is_item(content):
                return self._parse_list(st, indent, depth)
            return None
        if indent < parent_indent:
            return None
        if self._is_item(content):
            return self._parse_list(st, indent, depth)
        # A deeper line carrying no `key:` is the parent key's plain scalar
        # value, not a malformed mapping.
        if not self._split_key(content)[1]:
            st.advance()
            text = content
            if self._is_plain(text):
                text = self._continuation(st, parent_indent, text)
            return self._parse_scalar(text)
        return self._parse_map(st, indent, depth)

    def _continuation(self, st: _State, owner_indent: int, text: str) -> str:
        """Fold a multi-line plain scalar into one line, per YAML."""
        parts = [text]
        while not st.done():
            indent, content, value = st.peek()
            # Inside a plain scalar every deeper line is text, dashes included.
            if indent <= owner_indent or value is not _NO_VALUE:
                break
            if self._split_key(content)[1]:
                raise yaml.YAMLError(f"mapping value not allowed here: {content!r}")
            parts.append(content)
            st.advance()
        return " ".join(parts)

    @staticmethod
    def _is_plain(text: str) -> bool:
        return not text.startswith(("[", "{", '"', "'", "*", "&"))

    def _parse_list(self, st: _State, list_indent: int, depth: int = 0) -> list:
        items: list = []
        while not st.done():
            indent, content, value = st.peek()
            if indent != list_indent or not self._is_item(content):
                break

            after = content[1:]
            after_stripped = after.lstrip(" ")

            if after_stripped == "" and value is _NO_VALUE:
                # bare "-": the item is the nested block that follows
                st.advance()
                items.append(self._parse_block(st, list_indent, depth + 1))
                continue

            if value is not _NO_VALUE and after_stripped == "":
                items.append(value)
                st.advance()
                continue

            prefix_len = 1 + (len(after) - len(after_stripped))
            anchor, remainder = self._take_anchor(after_stripped)
            if anchor is not None and remainder == "":
                st.advance()
                resolved = self._parse_block(st, list_indent, depth + 1)
                self._anchors[anchor] = resolved
                items.append(resolved)
                continue
            if anchor is not None:
                after_stripped = remainder

            _, sep, _ = self._split_key(after_stripped)
            if sep:
                # "- key: value" — the item is a mapping whose first line is
                # virtually indented to (list_indent + prefix_len)
                virtual_indent = list_indent + prefix_len
                st.lines[st.i] = (virtual_indent, after_stripped, value)
                resolved = self._parse_map(st, virtual_indent, depth + 1)
            else:
                st.advance()
                text = after_stripped
                if self._is_plain(text):
                    text = self._continuation(st, list_indent, text)
                resolved = self._parse_scalar(text)

            if anchor is not None:
                self._anchors[anchor] = resolved
            items.append(resolved)
        return items

    def _parse_map(self, st: _State, map_indent: int, depth: int = 0) -> dict:
        obj: dict = {}
        merges: list[dict] = []
        while not st.done():
            indent, content, value = st.peek()
            if indent != map_indent or self._is_item(content):
                break

            key, sep, rest = self._split_key(content)
            if not sep:
                raise yaml.YAMLError(f"expected ':' in mapping at indent {map_indent}: {content!r}")

            rest = rest.strip()
            st.advance()

            if key.strip() == "<<":
                merges.extend(self._resolve_merge(rest))
                continue

            key_parsed = self._parse_scalar(key.strip())
            anchor, rest = self._take_anchor(rest)

            if value is not _NO_VALUE:
                resolved = value
            elif rest == "":
                resolved = self._parse_block(st, map_indent, depth + 1, allow_seq_at_parent=True)
            else:
                if self._is_plain(rest):
                    rest = self._continuation(st, map_indent, rest)
                resolved = self._parse_scalar(rest)

            if anchor is not None:
                self._anchors[anchor] = resolved
            obj[key_parsed] = resolved

        # Explicit keys win over merged ones regardless of where `<<` appeared.
        for source in merges:
            for key_parsed, resolved in source.items():
                obj.setdefault(key_parsed, resolved)
        return obj

    # endregion

    # region public API
    def parse_yaml(self, text: str) -> Any:
        documents = list(self.parse_all(text))
        if not documents:
            return None
        if len(documents) > 1:
            raise yaml.YAMLError("expected a single document in the stream")
        return documents[0]

    def parse_all(self, text: str) -> Iterator[Any]:
        for lines in self._prep_documents(text):
            self._anchors = {}
            st = self._State(lines)
            document = self._parse_block(st, -1)
            # Anything left over means the parser stopped early. Previously this
            # was silent and the remainder of the document was simply lost.
            if not st.done():
                indent, content, _ = st.peek()
                raise yaml.YAMLError(f"unparsed content at indent {indent}: {content!r}")
            yield document

    def _load_yaml_file(self, path: str | Path, encoding: str = "utf-8") -> Any:
        return self.parse_yaml(Path(path).read_text(encoding=encoding))

    def __str__(self) -> str:
        return "" if self.yaml is None else str(self.yaml)

    @staticmethod
    def safe_load(source: Any) -> Any:
        """Parse a stream, `Path`, or YAML string.

        A `str` is always YAML text, never a path — the previous heuristic read
        any string that happened to name an existing file, which diverged from
        PyYAML and turned parsed content into a file read.
        """
        instance = yaml()
        if hasattr(source, "read"):
            return instance.parse_yaml(source.read())
        if isinstance(source, Path):
            return instance._load_yaml_file(source)
        if isinstance(source, str):
            return instance.parse_yaml(source)
        raise TypeError("safe_load accepts a file object, YAML string, or Path.")

    @staticmethod
    def safe_load_all(source: Any) -> Iterator[Any]:
        instance = yaml()
        if hasattr(source, "read"):
            text = source.read()
        elif isinstance(source, Path):
            text = source.read_text(encoding="utf-8")
        elif isinstance(source, str):
            text = source
        else:
            raise TypeError("safe_load_all accepts a file object, YAML string, or Path.")
        return instance.parse_all(text)

    # endregion


# --------------------------------------------------------------------------- #
# endregion yaml                                                              #
# --------------------------------------------------------------------------- #
