# Module name: textnorm.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides helper classes for working with text documents within
the Wattleflow framework. It includes utilities for normalising and managing text data efficiently.
"""


from __future__ import annotations
import re
import unicodedata
from pathlib import Path

WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


class CaseText(str):
    def __format__(self, spec: str) -> str:
        if spec == "upper":
            return self.upper()
        if spec == "lower":
            return self.lower()
        if spec in ("title", "capitalize"):
            return self.title()
        return super().__format__(spec)


class Normaliser:
    @staticmethod
    def transform(
        filename: str,
        max_len: int = 40,
        replacement: str = "-",
    ) -> str:
        """
        Normalise 'stem' (without ekstension) u: ascii, [a-z0-9-], withot dobule dashes,
        stem length <= max_len. Exstension remains (lowercase). If stem turns empty,
        use 'file'. Protect from reserved Windows names.
        """
        p = Path(filename)
        basename = p.name.strip().lower()
        stem, ext = Path(basename).stem, Path(basename).suffix.lower()

        # 1) Remove diacritics (NFKD → ASCII)
        # kao jedan znak (č = U+010D),
        # cannonic c + ˇ = U+0063 + U+030C
        norm = unicodedata.normalize("NFKD", stem)
        norm = norm.encode("ascii", "ignore").decode("ascii")

        # 2) Any character appart from letter or digit with the separator
        norm = re.sub(r"[^a-z0-9]+", replacement, norm)

        # 3) Merge multiple separators into one and trim edges
        if replacement:
            rep_esc = re.escape(replacement)
            norm = re.sub(rf"{rep_esc}{{2,}}", replacement, norm).strip(replacement)

        # 4) Fallback if empty
        if not norm:
            norm = "file"

        # 5) Reserved Windows names – add suffix
        if norm in WINDOWS_RESERVED:
            norm = f"{norm}_"

        # 6) Limit stem length
        if len(norm) > max_len:
            norm = norm[:max_len].rstrip(replacement) or "file"

        return f"{norm}{ext}"
