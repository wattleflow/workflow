# Module name: helpers/macros.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["TextMacros", "CompiledMacros", "Replacements"]

import logging
import re

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #
CompiledMacros = list[tuple[re.Pattern, str]]
Replacements = list[dict[str, str]]

class TextMacros:
    __slot__ = ("_compiled", "log")

    ADD_VALUE_ERROR = (
        "Tuple macro must be: (pattern, replacement) or (pattern, replacement, flags)."
    )

    PLACEHOLDER_PREFIX = "ENTITET"

    REDOS = re.compile(r"\([^()]*[+*?][^()]*\)[+*{]")

    def __init__(self, list_of_macros: list = None, flag=re.IGNORECASE):
        self._compiled: CompiledMacros = []
        self.log = logging.getLogger(__name__)
        self.flag = flag
        if list_of_macros is not None:
            if not isinstance(list_of_macros, list):
                raise TypeError(f"Expected list, found {type(list_of_macros).__name__}")
            self.add(list_of_macros)

    @classmethod
    def _check_redos(cls, pattern: str) -> None:
        if cls.REDOS.search(pattern):
            raise ValueError(
                f"Regex pattern rejected — contains a structure prone to catastrophic "
                f"backtracking (ReDoS): {pattern!r}"
            )

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

        error = self._replacement_error(pattern, replacement)
        if error:
            raise re.error(
                f"Invalid replacement {replacement!r} for pattern {pattern.pattern!r}: {error}"
            )

    @staticmethod
    def _replacement_error(pattern: re.Pattern, replacement) -> str | None:
        try:
            pattern.sub(replacement, "")
        except re.error as e:
            return type(e).__name__
        return None

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
                        raise ValueError(self.ADD_VALUE_ERROR)
                elif isinstance(macro, dict):
                    if "pattern" not in macro or "replacement" not in macro:
                        raise ValueError("Dict macro must contain 'pattern' and 'replacement'.")
                    pattern = macro["pattern"]
                    replacement = macro["replacement"]
                    flags = macro.get("flags", self.flag)
                else:
                    raise ValueError(f"Macro must be tuple or dict, got {type(macro).__name__}")

                self._check_redos(pattern)
                compiled = re.compile(pattern, flags)

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
        result = text
        for pattern, replacement in self._compiled:
            result = pattern.sub(replacement, result)
        return result

    def anonymise(
        self,
        text: str,
        ignore: list[re.Pattern] | None = None,
        prefix: str | None = None,
    ) -> tuple[str, Replacements]:
        """`run()` with a generated placeholder per distinct surface, and a
        report of what was replaced.

        `run()` substitutes each macro's own replacement, so two occurrences of
        different entities collapse to the same token and nothing records what
        stood there. Where the substitution has to stay reversible — building
        training data, or handing redacted text to a third party — each surface
        needs its own placeholder and a map back. That is this method.

        `ignore` drops a surface a macro over-matched (an allow-list of known
        false positives). `prefix` names the placeholder series; the macro's own
        replacement travels in the report as `entity`, since a PII macro table
        spells the entity kind there.
        """
        placeholders: dict[str, str] = {}
        replaced: Replacements = []
        ignored = ignore or []
        series = prefix or self.PLACEHOLDER_PREFIX

        for pattern, replacement in self._compiled:
            for match in pattern.finditer(text):
                surface = (match.group(0) or "").strip()
                if not surface or surface in placeholders:
                    continue
                if any(rule.search(surface) for rule in ignored):
                    continue
                placeholder = f"{series}{len(placeholders) + 1}"
                placeholders[surface] = placeholder
                replaced.append(
                    {
                        "text": surface,
                        "replacement": placeholder,
                        "entity": str(replacement),
                    }
                )

        result = text
        for surface in sorted(placeholders, key=len, reverse=True):
            result = result.replace(surface, placeholders[surface])
        return result, replaced
