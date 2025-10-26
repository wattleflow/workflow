# Module name: yaml.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides a workaround for handling YAML files within the
Wattleflow framework, aiming to minimise dependency on external YAML
packages. It serves as an interim solution currently in the alpha phase.
"""


import os
import re
from pathlib import Path
from typing import Union, List, Dict, Optional


class yaml:
    class _State:
        def __init__(self, lines, step):
            self.lines = lines
            self.i = 0
            self.step = step

        def done(self):
            return self.i >= len(self.lines)

    def __init__(self, file_path: Optional[str] = None):
        self.yaml: Optional[Union[List[str], Dict[str, str]]] = None
        self.file_path: Optional[str] = file_path

        if self.file_path:
            if os.path.exists(self.file_path):
                self.yaml = self._load_yaml_file(self.file_path)

    def _strip_comment(self, s: str) -> str:
        out, in_s, in_d = [], False, False
        i = 0
        while i < len(s):
            c = s[i]
            if c == "'" and not in_d:
                in_s = not in_s
            elif c == '"' and not in_s:
                in_d = not in_d
            elif c == "#" and not in_s and not in_d:
                break  # počinje komentar
            out.append(c)
            i += 1
        return "".join(out).rstrip()

    def _parse_scalar(self, s: str):
        s = s.strip()
        if s == "":
            return ""
        # quoted string
        if (s.startswith('"') and s.endswith('"')) or (
            s.startswith("'") and s.endswith("'")
        ):
            if s[0] == '"':
                # obradi escape sekvence
                return bytes(s[1:-1], "utf-8").decode("unicode_escape")
            else:
                return s[1:-1]
        # null
        if s.lower() in ("null", "none", "~"):
            return None
        # bool
        if s.lower() in ("true", "yes", "on"):
            return True
        if s.lower() in ("false", "no", "off"):
            return False
        # int
        if re.fullmatch(r"[+-]?\d+", s):
            try:
                return int(s)
            except ValueError:
                pass
        # float
        if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", s):
            try:
                return float(s)
            except ValueError:
                pass
        # fallback: raw string
        return s

    def _prep_lines(self, text: str):
        lines = []
        for raw in text.splitlines():
            no_comm = self._strip_comment(raw)
            if not no_comm.strip():
                continue
            if "\t" in no_comm:
                # YAML formalno ne dopušta tabove za uvlaku
                no_comm = no_comm.replace("\t", "    ")
            indent = len(no_comm) - len(no_comm.lstrip(" "))
            lines.append((indent, no_comm.strip()))
        return lines

    def _detect_indent_step(self, lines):
        diffs = sorted({b - a for (a, _), (b, _) in zip(lines, lines[1:]) if b > a})
        return diffs[0] if diffs else 2  # pretpostavi 2 ako nema dublje uvlake

    def _parse_block(self, st: _State, expected_indent: int):
        if st.done() or st.lines[st.i][0] < expected_indent:
            return None  # prazno
        # odluči: lista ili mapa na ovoj razini
        indent, content = st.lines[st.i]
        is_list = content.startswith("- ")
        if is_list:
            items = []
            while not st.done():
                indent, content = st.lines[st.i]
                if indent != expected_indent or not content.startswith("-"):
                    break
                # variants: "- value" or "-" + indent
                after = content[1:].lstrip()
                if after:  # "- nešto"
                    if after[0] == " ":
                        after = after[1:]
                    # inline scalar
                    items.append(self._parse_scalar(after))
                    st.i += 1
                    # Ako sljedeca linija ima vecu uvlaku, tretiraj kao podblok istog elementa (spoji dict/list)  # noqa: E501
                    if not st.done() and st.lines[st.i][0] > expected_indent:
                        child = self._parse_block(st, expected_indent + st.step)
                        if isinstance(child, dict):
                            # spoji skalar -> pod "value"
                            items[-1] = {"value": items[-1], **child}
                        elif child is not None:
                            items[-1] = [items[-1], child]
                    continue
                else:  # samo "-" pa podblok
                    st.i += 1
                    child = self._parse_block(st, expected_indent + st.step)
                    items.append(child)
            return items
        else:
            obj = {}
            while not st.done():
                indent, content = st.lines[st.i]
                if indent != expected_indent or content.startswith("- "):
                    break
                if ":" not in content:
                    raise ValueError(f"Očekivan ':' u mapi, linija: {content!r}")
                key, after = content.split(":", 1)
                key = key.strip()
                after = after.strip()
                if after == "":  # key:
                    st.i += 1
                    val = self._parse_block(st, expected_indent + st.step)
                else:  # key: value
                    val = self._parse_scalar(after)
                    st.i += 1
                    # Ako slijedi dublja uvlaka, spoji s podblokom
                    if not st.done() and st.lines[st.i][0] > expected_indent:
                        child = self._parse_block(st, expected_indent + st.step)
                        if isinstance(child, dict):
                            val = {"value": val, **child}
                        elif child is not None:
                            val = [val, child]
                obj[key] = val
            return obj

    def _load_yaml_file(
        self, path: Union[str, Path], encoding="utf-8"
    ) -> Optional[Union[List[str], Dict[str, str]]]:
        return self.parse_yaml(Path(path).read_text(encoding=encoding))

    def parse_yaml(self, text: str) -> Optional[Union[List[str], Dict[str, str]]]:
        lines = self._prep_lines(text)

        if not lines:
            return None

        step = self._detect_indent_step(lines)
        st = self._State(lines, step)
        result = self._parse_block(st, lines[0][0])

        return result

    def __str__(self) -> str:
        if self.yaml:
            return str(self.yaml)
        return ""

    @staticmethod
    def safe_load(
        source: Union[str, Path],
    ) -> Optional[Union[list, dict, str, int, float, bool, None]]:
        instance = yaml()
        if isinstance(source, (str, Path)) and os.path.exists(source):
            return instance._load_yaml_file(source)
        elif isinstance(source, (str, Path)):
            return instance.parse_yaml(str(source))
        else:
            raise TypeError("safe_load accepts YAML string or path to the file.")
