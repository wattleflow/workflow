# Module Name: name helpers/macros.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete macro classes.

import re


class TextMacros:
    def __init__(self, macros=[]):
        self._macros = []
        if macros is not None:
            if not isinstance(macros, list):
                raise TypeError(f"Expected list, got {type(macros).__name__}")
            self.add(macros)

    def add(self, macros: list):
        for macro in macros:
            if len(macro) == 2:
                pattern, replacement = macro
                pattern = re.compile(pattern)
            elif len(macro) == 3:
                pattern, replacement, flags = macro
                pattern = re.compile(pattern, flags)
            else:
                raise ValueError("Macro must be: (pattern, replacement and flags).")

            self._macros.append((pattern, replacement))

    def run(self, text):
        for pattern, replacement in self._macros:
            try:
                text = pattern.sub(replacement, text)
            except Exception:
                continue
        return text
