# Module name: drivers/identity/similarity.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""String comparators of the identity driver (SyRS-DRV-identity §2.5 step 4).

Each comparator is a strategy: `algorithm(caller, left=…, right=…)` returns a
similarity in [0, 1]; 1 means equal.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "DamerauLevenshtein",
    "Jaro",
    "JaroWinkler",
    "Levenshtein",
    "NGramJaccard",
    "Soundex",
    "TfIdfCosine",
]

import math
from collections import Counter
from collections.abc import Iterable
from typing import Any

from wattleflow.core import IStrategy, IWattleflow
from wattleflow.concrete.base import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Edit distances                                                       #
# --------------------------------------------------------------------------- #


class Levenshtein(Wattleflow, IStrategy):
    """Levenshtein (1966): insertions, deletions and substitutions."""

    __slots__ = ()

    @staticmethod
    def distance(left: str, right: str) -> int:
        if left == right:
            return 0
        if not left or not right:
            return len(left) or len(right)
        previous = list(range(len(right) + 1))
        for i, a in enumerate(left, 1):
            current = [i]
            for j, b in enumerate(right, 1):
                current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
            previous = current
        return previous[-1]

    @classmethod
    def similarity(cls, left: str, right: str) -> float:
        longest = max(len(left), len(right))
        return 1.0 if longest == 0 else 1.0 - cls.distance(left, right) / longest

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"])


class DamerauLevenshtein(Wattleflow, IStrategy):
    """Optimal string alignment (Damerau 1964): edits plus adjacent swaps,
    each substring edited at most once."""

    __slots__ = ()

    @staticmethod
    def distance(left: str, right: str) -> int:
        rows, cols = len(left) + 1, len(right) + 1
        d = [[0] * cols for _ in range(rows)]
        for i in range(rows):
            d[i][0] = i
        for j in range(cols):
            d[0][j] = j
        for i in range(1, rows):
            for j in range(1, cols):
                cost = left[i - 1] != right[j - 1]
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
                if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                    d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
        return d[-1][-1]

    @classmethod
    def similarity(cls, left: str, right: str) -> float:
        longest = max(len(left), len(right))
        return 1.0 if longest == 0 else 1.0 - cls.distance(left, right) / longest

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"])


# --------------------------------------------------------------------------- #
# endregion Edit distances                                                    #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Jaro family                                                          #
# --------------------------------------------------------------------------- #


class Jaro(Wattleflow, IStrategy):
    """Jaro (1989): shared characters within a window, and their transpositions."""

    __slots__ = ()

    @staticmethod
    def similarity(left: str, right: str) -> float:
        if left == right:
            return 1.0
        if not left or not right:
            return 0.0
        window = max(max(len(left), len(right)) // 2 - 1, 0)
        left_hits = [False] * len(left)
        right_hits = [False] * len(right)
        matches = 0
        for i, a in enumerate(left):
            for j in range(max(0, i - window), min(i + window + 1, len(right))):
                if not right_hits[j] and right[j] == a:
                    left_hits[i] = right_hits[j] = True
                    matches += 1
                    break
        if matches == 0:
            return 0.0
        left_seq = [a for a, hit in zip(left, left_hits, strict=False) if hit]
        right_seq = [b for b, hit in zip(right, right_hits, strict=False) if hit]
        transpositions = sum(a != b for a, b in zip(left_seq, right_seq, strict=False)) / 2
        return (matches / len(left) + matches / len(right) + (matches - transpositions) / matches) / 3

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"])


class JaroWinkler(Wattleflow, IStrategy):
    """Winkler (1990): Jaro with a bonus for a shared prefix of up to four
    characters, scaled by 0.1 as in the original definition."""

    __slots__ = ()
    PREFIX = 4
    SCALE = 0.1

    @classmethod
    def similarity(cls, left: str, right: str) -> float:
        base = Jaro.similarity(left, right)
        prefix = 0
        for a, b in zip(left[: cls.PREFIX], right[: cls.PREFIX], strict=False):
            if a != b:
                break
            prefix += 1
        return base + prefix * cls.SCALE * (1.0 - base)

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"])


# --------------------------------------------------------------------------- #
# endregion Jaro family                                                       #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Token measures                                                       #
# --------------------------------------------------------------------------- #


class NGramJaccard(Wattleflow, IStrategy):
    """Jaccard overlap of character n-grams; insensitive to word order."""

    __slots__ = ()

    @staticmethod
    def grams(text: str, size: int = 2) -> set[str]:
        padded = f" {text} "
        return {padded[i : i + size] for i in range(max(len(padded) - size + 1, 1))}

    @classmethod
    def similarity(cls, left: str, right: str, size: int = 2) -> float:
        a, b = cls.grams(left, size), cls.grams(right, size)
        union = a | b
        return 1.0 if not union else len(a & b) / len(union)

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"], kwargs.get("size", 2))


class TfIdfCosine(Wattleflow, IStrategy):
    """Cosine similarity of TF-IDF word vectors; a rare shared word weighs more
    than a common one. `corpus` gives the document frequencies."""

    __slots__ = ()

    @staticmethod
    def _vector(words: list[str], frequency: Counter, total: int) -> dict[str, float]:
        counts = Counter(words)
        return {w: c * (math.log((1 + total) / (1 + frequency[w])) + 1) for w, c in counts.items()}

    @classmethod
    def similarity(cls, left: str, right: str, corpus: Iterable[str] = ()) -> float:
        documents = [set(text.split()) for text in corpus] or [set(left.split()), set(right.split())]
        frequency: Counter = Counter(w for doc in documents for w in doc)
        a = cls._vector(left.split(), frequency, len(documents))
        b = cls._vector(right.split(), frequency, len(documents))
        dot = sum(a[w] * b.get(w, 0.0) for w in a)
        norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
        return 0.0 if norm == 0 else dot / norm

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"], kwargs.get("corpus", ()))


# --------------------------------------------------------------------------- #
# endregion Token measures                                                    #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Phonetic                                                             #
# --------------------------------------------------------------------------- #


class Soundex(Wattleflow, IStrategy):
    """American Soundex: first letter and three digits for similar sounds."""

    __slots__ = ()
    CODES = {
        **dict.fromkeys("bfpv", "1"),
        **dict.fromkeys("cgjkqsxz", "2"),
        **dict.fromkeys("dt", "3"),
        "l": "4",
        **dict.fromkeys("mn", "5"),
        "r": "6",
    }

    @classmethod
    def encode(cls, word: str) -> str:
        letters = [c for c in word.lower() if c.isascii() and c.isalpha()]
        if not letters:
            return ""
        first = letters[0]
        code = [first.upper()]
        previous = cls.CODES.get(first, "")
        for c in letters[1:]:
            digit = cls.CODES.get(c, "")
            if digit and digit != previous:
                code.append(digit)
            if c not in "hw":
                previous = digit
        return ("".join(code) + "000")[:4]

    @classmethod
    def similarity(cls, left: str, right: str) -> float:
        a, b = cls.encode(left), cls.encode(right)
        return 1.0 if a and a == b else 0.0

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float:
        return self.similarity(kwargs["left"], kwargs["right"])


# --------------------------------------------------------------------------- #
# endregion Phonetic                                                          #
# --------------------------------------------------------------------------- #
