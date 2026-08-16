# Module name: helpers/macros.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence
#
# History:
#   2024-06-01: Initial version created.
#   2026-03-16: Updated run: error handling for invalid macro formats.


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import logging
import re

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #
ADD_VALUE_ERROR = (
    "Tuple macro must be: (pattern, replacement) or (pattern, replacement, flags)."
)

# Detects common catastrophic backtracking structures:
#   (a+)+  (a*)* (a+)* (a?)+  and quantified groups followed by { repetition
_REDOS_RE = re.compile(r"\([^()]*[+*?][^()]*\)[+*{]")


def _check_redos(pattern: str) -> None:
    if _REDOS_RE.search(pattern):
        raise ValueError(
            f"Regex pattern rejected — contains a structure prone to catastrophic "
            f"backtracking (ReDoS): {pattern!r}"
        )


CompiledMacros = list[tuple[re.Pattern, str]]


class TextMacros:
    __slot__ = ("_compiled", "log")

    def __init__(self, list_of_macros: list = None, flag=re.IGNORECASE):
        self._compiled: CompiledMacros = []
        self.log = logging.getLogger(__name__)
        self.flag = flag
        if list_of_macros is not None:
            if not isinstance(list_of_macros, list):
                raise TypeError(f"Expected list, found {type(list_of_macros).__name__}")
            self.add(list_of_macros)

    def _validate_replacement(self, pattern: re.Pattern, replacement) -> None:
        if not isinstance(pattern, re.Pattern):
            raise TypeError(
                f"_validate_replacement expects compiled re.Pattern, "
                f"got {type(pattern).__name__}: {pattern!r}"
            )

        if not (isinstance(replacement, (str, bytes)) or callable(replacement)):
            raise TypeError(
                f"Replacement must be str/bytes/callable, "
                f"got {type(replacement).__name__}: {replacement!r} "
                f"for pattern {pattern.pattern!r}"
            )

        try:
            pattern.sub(replacement, "")
        except re.error as e:
            raise re.error(
                f"Invalid replacement {replacement!r} for pattern {pattern.pattern!r}: {e}"
            ) from e

    @property
    def compiled(self) -> CompiledMacros:
        return self._compiled

    @property
    def count(self) -> int:
        return len(self._compiled)

    def add(self, list_of_macros: list):
        self.log.debug("TextMacros.add()")
        for macro in list_of_macros:
            try:
                if isinstance(macro, tuple):
                    if len(macro) == 2:
                        pattern, replacement = macro
                        flags = self.flag
                    elif len(macro) == 3:
                        pattern, replacement, flags = macro
                    else:
                        raise ValueError(ADD_VALUE_ERROR)
                elif isinstance(macro, dict):
                    if "pattern" not in macro or "replacement" not in macro:
                        raise ValueError(
                            "Dict macro must contain 'pattern' and 'replacement'."
                        )
                    pattern = macro["pattern"]
                    replacement = macro["replacement"]
                    flags = macro.get("flags", self.flag)
                else:
                    raise ValueError(
                        f"Macro must be tuple or dict, got {type(macro).__name__}"
                    )

                _check_redos(pattern)
                try:
                    compiled = re.compile(pattern, flags)
                except re.error as e:
                    raise re.error(
                        f"Invalid pattern {pattern!r} (flags={flags}): {e}"
                    ) from e

                self._compiled.append((compiled, replacement))
            except Exception as e:
                self.log.error(
                    "TextMacros.add() failed for macro %r: %s: %s",
                    macro,
                    type(e).__name__,
                    e,
                )
                continue

    def run(self, text: str) -> str:
        # Flags are baked into each compiled pattern during add().
        # Pattern.sub's 3rd positional arg is `count`, not flags — passing
        # re.IGNORECASE (int value 2) here silently capped substitutions at 2.
        result = text
        for pattern, replacement in self._compiled:
            result = pattern.sub(replacement, result)
        return result
