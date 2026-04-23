# Module name: yaml.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Minimal YAML subset loader compatible with PyYAML.safe_load for the
Wattleflow framework. Supports block mappings, block sequences, scalars
(quoted and plain), booleans, nulls, ints and floats. It handles the
`- key: value` list-item pattern and non-uniform indentation (e.g. mixing
two and four space blocks) without assuming a fixed indent step.
"""


import os
import re
from pathlib import Path
from typing import Any, Optional, Union


_KEY_RE = re.compile(r"^([^:\s\"'\[\]\{\}][^:\s]*)\s*:(?=\s|$)")


class yaml:
    class YAMLError(Exception):
        """Raised when the YAML source cannot be parsed."""

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

    def __init__(self, file_path: Optional[str] = None):
        self.yaml: Any = None
        self.file_path: Optional[str] = file_path

        if file_path and os.path.exists(file_path):
            self.yaml = self._load_yaml_file(file_path)

    # region scalar helpers
    def _strip_comment(self, s: str) -> str:
        out = []
        in_s = False
        in_d = False
        for i, c in enumerate(s):
            if c == "'" and not in_d:
                in_s = not in_s
            elif c == '"' and not in_s:
                in_d = not in_d
            elif c == "#" and not in_s and not in_d:
                # a '#' only starts a comment when at start of line or
                # preceded by whitespace — otherwise it belongs to the value
                if i == 0 or s[i - 1] in (" ", "\t"):
                    break
            out.append(c)
        return "".join(out).rstrip()

    def _parse_scalar(self, s: str) -> Any:
        s = s.strip()
        if s == "":
            return ""

        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            _esc = {
                "n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"',
                "0": "\0", "b": "\b", "f": "\f", "v": "\v", "/": "/", "'": "'",
            }
            return re.sub(
                r"\\(.)",
                lambda m: _esc.get(m.group(1), m.group(1)),
                s[1:-1],
            )

        if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
            return s[1:-1].replace("''", "'")

        low = s.lower()
        if low in ("null", "none", "~"):
            return None
        if low in ("true", "yes", "on"):
            return True
        if low in ("false", "no", "off"):
            return False

        if re.fullmatch(r"[+-]?\d+", s):
            try:
                return int(s)
            except ValueError:
                pass

        if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", s):
            try:
                return float(s)
            except ValueError:
                pass

        return s
    # endregion

    # region line preparation
    def _prep_lines(self, text: str):
        lines = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if stripped in ("---", "..."):
                continue
            no_comm = self._strip_comment(raw)
            if not no_comm.strip():
                continue
            if "\t" in no_comm:
                # tabs are not allowed for indentation — normalise to spaces
                no_comm = no_comm.replace("\t", "    ")
            indent = len(no_comm) - len(no_comm.lstrip(" "))
            lines.append((indent, no_comm.strip()))
        return lines
    # endregion

    # region recursive parser
    def _parse_block(self, st: _State, parent_indent: int) -> Any:
        if st.done():
            return None
        indent, content = st.peek()
        if indent <= parent_indent:
            return None
        if content.startswith("-") and (len(content) == 1 or content[1] == " "):
            return self._parse_list(st, indent)
        return self._parse_map(st, indent)

    def _parse_list(self, st: _State, list_indent: int) -> list:
        items: list = []
        while not st.done():
            indent, content = st.peek()
            if indent != list_indent:
                break
            if not (content.startswith("-") and (len(content) == 1 or content[1] == " ")):
                break

            after = content[1:]
            after_stripped = after.lstrip(" ")

            if after_stripped == "":
                # bare "-": the item is the nested block that follows
                st.advance()
                child = self._parse_block(st, list_indent)
                items.append(child)
                continue

            prefix_len = 1 + (len(after) - len(after_stripped))
            m = _KEY_RE.match(after_stripped)
            if m:
                # "- key: value" — the item is a mapping whose first line is
                # virtually indented to (list_indent + prefix_len)
                virtual_indent = list_indent + prefix_len
                st.lines[st.i] = (virtual_indent, after_stripped)
                items.append(self._parse_map(st, virtual_indent))
                continue

            # plain scalar item
            items.append(self._parse_scalar(after_stripped))
            st.advance()
        return items

    def _parse_map(self, st: _State, map_indent: int) -> dict:
        obj: dict = {}
        while not st.done():
            indent, content = st.peek()
            if indent != map_indent:
                break
            if content.startswith("-") and (len(content) == 1 or content[1] == " "):
                break

            key, sep, rest = content.partition(":")
            if not sep:
                raise yaml.YAMLError(
                    f"expected ':' in mapping at indent {map_indent}: {content!r}"
                )

            key_parsed = self._parse_scalar(key.strip())
            rest = rest.strip()
            st.advance()

            if rest == "":
                val = self._parse_block(st, map_indent)
            else:
                val = self._parse_scalar(rest)

            obj[key_parsed] = val
        return obj
    # endregion

    # region public API
    def parse_yaml(self, text: str) -> Any:
        lines = self._prep_lines(text)
        if not lines:
            return None
        st = self._State(lines)
        return self._parse_block(st, -1)

    def _load_yaml_file(
        self,
        path: Union[str, Path],
        encoding: str = "utf-8",
    ) -> Any:
        return self.parse_yaml(Path(path).read_text(encoding=encoding))

    def __str__(self) -> str:
        return str(self.yaml) if self.yaml else ""

    @staticmethod
    def safe_load(source: Any) -> Any:
        instance = yaml()
        if hasattr(source, "read"):
            return instance.parse_yaml(source.read())
        if isinstance(source, Path):
            return instance._load_yaml_file(source)
        if isinstance(source, str):
            # path vs inline YAML heuristic: treat as path only if it contains
            # no newline and actually points to an existing file
            if "\n" not in source and len(source) < 4096:
                try:
                    if os.path.exists(source):
                        return instance._load_yaml_file(source)
                except (OSError, ValueError):
                    pass
            return instance.parse_yaml(source)
        raise TypeError("safe_load accepts a file object, YAML string, or path.")
    # endregion
