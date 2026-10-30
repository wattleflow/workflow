# Module name: drivers/identity/recognition.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Normalisation, validity checks and recognition of entities in text
(SyRS-DRV-identity §2.5 steps 1, 2 and 2a; kinds in §2.6)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "CheckDigit",
    "DateForms",
    "EntityKind",
    "EntityKinds",
    "EntityRecognition",
    "IdentityNormaliser",
    "KeywordAutomaton",
    "Mention",
]

import re
import unicodedata
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from wattleflow.core import IProduct, IStrategy, IWattleflow
from wattleflow.concrete.base import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Kinds                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EntityKind(IProduct):
    """One row of the closed list of kinds (StRS BR18)."""

    code: str
    category: str
    role: str
    sensitivity: str
    recognition: str
    comparison: str

    @property
    def name(self) -> str:
        return type(self).__name__


class EntityKinds:
    """The closed list of SyRS-DRV-identity §2.6; a new kind is a documented change."""

    ROWS: tuple[tuple[str, str, str, str, str, str], ...] = (
        ("PER", "subject", "direct", "ordinary", "name", "statistical"),
        ("ORN", "subject", "direct", "ordinary", "name", "statistical"),
        ("NRP", "subject", "descriptive", "ordinary", "name", "exact"),
        ("GPE", "place", "indirect", "ordinary", "name", "exact"),
        ("LOC", "place", "descriptive", "ordinary", "name", "exact"),
        ("FCL", "place", "indirect", "ordinary", "name", "statistical"),
        ("ADR", "place", "indirect", "ordinary", "context", "statistical"),
        ("NID", "identifier", "direct", "ordinary", "checked", "exact"),
        ("BID", "identifier", "direct", "ordinary", "checked", "exact"),
        ("DCN", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("TEL", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("EML", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("ACC", "identifier", "direct", "ordinary", "checked", "exact"),
        ("ONL", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("VEH", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("DEV", "identifier", "direct", "ordinary", "pattern", "exact"),
        ("CAS", "identifier", "indirect", "ordinary", "pattern", "exact"),
        ("DOB", "time", "indirect", "ordinary", "context", "difference"),
        ("DAT", "time", "descriptive", "ordinary", "pattern", "difference"),
        ("TIM", "time", "descriptive", "ordinary", "pattern", "difference"),
        ("AGE", "quantity", "indirect", "ordinary", "context", "difference"),
        ("MON", "quantity", "descriptive", "ordinary", "pattern", "difference"),
        ("PCT", "quantity", "descriptive", "ordinary", "pattern", "difference"),
        ("QTY", "quantity", "descriptive", "ordinary", "pattern", "difference"),
        ("NUM", "quantity", "descriptive", "ordinary", "pattern", "difference"),
        ("OCC", "person-attribute", "indirect", "ordinary", "name", "statistical"),
        ("EDU", "person-attribute", "indirect", "ordinary", "name", "statistical"),
        ("PHY", "person-attribute", "indirect", "ordinary", "context", "exact"),
        ("HLT", "person-attribute", "indirect", "special", "context", "exact"),
        ("BLF", "person-attribute", "descriptive", "special", "context", "exact"),
        ("POL", "person-attribute", "descriptive", "special", "context", "exact"),
        ("ETH", "person-attribute", "indirect", "special", "context", "exact"),
        ("SXO", "person-attribute", "descriptive", "special", "context", "exact"),
        ("PRD", "work-and-event", "descriptive", "ordinary", "name", "statistical"),
        ("EVT", "work-and-event", "descriptive", "ordinary", "name", "statistical"),
        ("ART", "work-and-event", "descriptive", "ordinary", "name", "statistical"),
        ("LAW", "work-and-event", "descriptive", "ordinary", "name", "statistical"),
        ("LNG", "work-and-event", "descriptive", "ordinary", "name", "exact"),
    )

    @classmethod
    def all(cls) -> dict[str, EntityKind]:
        return {row[0]: EntityKind(*row) for row in cls.ROWS}

    @classmethod
    def unknown(cls, codes: Iterable[str]) -> list[str]:
        known = {row[0] for row in cls.ROWS}
        return sorted(c for c in codes if c not in known)


# --------------------------------------------------------------------------- #
# endregion Kinds                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Normalisation and check digits                                       #
# --------------------------------------------------------------------------- #


class IdentityNormaliser:
    """Step 1: one comparable form per kind."""

    @staticmethod
    def text(value: str, titles: Iterable[str] = ()) -> str:
        folded = unicodedata.normalize("NFKC", value).casefold()
        stripped = "".join(c for c in unicodedata.normalize("NFD", folded) if unicodedata.category(c) != "Mn")
        words = re.sub(r"[^\w\s]", " ", stripped).split()
        drop = {t.casefold().rstrip(".") for t in titles}
        return " ".join(w for w in words if w not in drop)

    @staticmethod
    def digits(value: str) -> str:
        return "".join(c for c in value if c.isdigit())

    @classmethod
    def value(cls, kind: str, value: str, titles: Iterable[str] = ()) -> str:
        if kind == "EML":
            return value.strip().casefold()
        if kind == "TEL":
            plus = "+" if value.strip().startswith("+") else ""
            return plus + cls.digits(value)
        if kind in ("NID", "BID", "ACC", "DCN", "VEH", "DEV", "CAS"):
            return re.sub(r"[\s.-]", "", value).upper()
        if kind in ("DAT", "DOB"):
            return DateForms.iso(value) or cls.text(value)
        if kind in ("TIM", "AGE", "MON", "PCT", "QTY", "NUM"):
            return re.sub(r"\s+", "", value).casefold()
        return cls.text(value, titles)


class CheckDigit:
    """Step 2a: check digits defined by each standard."""

    TFN_WEIGHTS = (1, 4, 3, 7, 5, 8, 6, 9, 10)
    ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    ACN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 1)
    MEDICARE_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9)

    @staticmethod
    def luhn(digits: str) -> bool:
        if not digits.isdigit() or len(digits) < 2:
            return False
        total = 0
        for i, c in enumerate(reversed(digits)):
            d = int(c)
            if i % 2:
                d = d * 2 - 9 if d > 4 else d * 2
            total += d
        return total % 10 == 0

    @staticmethod
    def iban(value: str) -> bool:
        text = value.replace(" ", "").upper()
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", text):
            return False
        moved = text[4:] + text[:4]
        return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1

    @staticmethod
    def oib(digits: str) -> bool:
        if not re.fullmatch(r"\d{11}", digits):
            return False
        r = 10
        for c in digits[:10]:
            s = (int(c) + r) % 10 or 10
            r = (s * 2) % 11
        check = 11 - r
        return (0 if check == 10 else check) == int(digits[10])

    @classmethod
    def tfn(cls, digits: str) -> bool:
        if not re.fullmatch(r"\d{9}", digits):
            return False
        return sum(int(c) * w for c, w in zip(digits, cls.TFN_WEIGHTS, strict=False)) % 11 == 0

    @classmethod
    def abn(cls, digits: str) -> bool:
        if not re.fullmatch(r"\d{11}", digits) or digits[0] == "0":
            return False
        values = [int(digits[0]) - 1] + [int(c) for c in digits[1:]]
        return sum(v * w for v, w in zip(values, cls.ABN_WEIGHTS, strict=False)) % 89 == 0

    @classmethod
    def acn(cls, digits: str) -> bool:
        if not re.fullmatch(r"\d{9}", digits):
            return False
        total = sum(int(c) * w for c, w in zip(digits, cls.ACN_WEIGHTS, strict=False))
        return (10 - total % 10) % 10 == int(digits[8])

    @classmethod
    def medicare(cls, digits: str) -> bool:
        if not re.fullmatch(r"[2-6]\d{9,10}", digits):
            return False
        total = sum(int(c) * w for c, w in zip(digits, cls.MEDICARE_WEIGHTS, strict=False))
        return total % 10 == int(digits[8])


class DateForms:
    """Dates to ISO 8601. English month names, the only language of the first phase."""

    MONTHS = {
        m: i
        for i, names in enumerate(
            (
                ("january", "jan"),
                ("february", "feb"),
                ("march", "mar"),
                ("april", "apr"),
                ("may",),
                ("june", "jun"),
                ("july", "jul"),
                ("august", "aug"),
                ("september", "sep", "sept"),
                ("october", "oct"),
                ("november", "nov"),
                ("december", "dec"),
            ),
            1,
        )
        for m in names
    }
    MONTH = r"(?:%s)\.?" % "|".join(sorted(MONTHS, key=len, reverse=True))
    PATTERNS = (
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b",
        r"\b\d{1,2}\s+%s\s+\d{4}\b" % MONTH,
        r"\b%s\s+\d{1,2},?\s+\d{4}\b" % MONTH,
    )

    @classmethod
    def iso(cls, value: str) -> str | None:
        text = value.strip().casefold()
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
        if m:
            y, mo, d = (int(g) for g in m.groups())
        elif m := re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", text):
            d, mo, y = (int(g) for g in m.groups())
        elif m := re.fullmatch(r"(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})", text):
            d, mo, y = int(m[1]), cls.MONTHS.get(m[2], 0), int(m[3])
        elif m := re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", text):
            d, mo, y = int(m[2]), cls.MONTHS.get(m[1], 0), int(m[3])
        else:
            return None
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return f"{y:04d}-{mo:02d}-{d:02d}"


# --------------------------------------------------------------------------- #
# endregion Normalisation and check digits                                    #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Keyword automaton                                                    #
# --------------------------------------------------------------------------- #


class KeywordAutomaton(Wattleflow, IStrategy):
    """Aho-Corasick (1975): every dictionary phrase in one pass over the text.
    Matching is on casefolded text and keeps only whole words."""

    __slots__ = ("_goto", "_fail", "_out")

    def __init__(self, phrases: Mapping[str, str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._goto: list[dict[str, int]] = [{}]
        self._fail: list[int] = [0]
        self._out: list[list[tuple[str, int]]] = [[]]
        for phrase, kind in (phrases or {}).items():
            self._add(phrase.casefold(), kind)
        self._link()

    def _add(self, phrase: str, kind: str) -> None:
        if not phrase:
            return
        node = 0
        for c in phrase:
            if c not in self._goto[node]:
                self._goto.append({})
                self._fail.append(0)
                self._out.append([])
                self._goto[node][c] = len(self._goto) - 1
            node = self._goto[node][c]
        self._out[node].append((kind, len(phrase)))

    def _link(self) -> None:
        queue = deque(self._goto[0].values())
        while queue:
            node = queue.popleft()
            for c, child in self._goto[node].items():
                queue.append(child)
                f = self._fail[node]
                while f and c not in self._goto[f]:
                    f = self._fail[f]
                self._fail[child] = self._goto[f].get(c, 0) if self._goto[f].get(c, 0) != child else 0
                self._out[child] = self._out[child] + self._out[self._fail[child]]

    def find(self, text: str) -> list[tuple[int, int, str]]:
        folded = text.casefold()
        if len(folded) != len(text):
            folded = "".join(c.casefold()[:1] or c for c in text)
        found: list[tuple[int, int, str]] = []
        node = 0
        for i, c in enumerate(folded):
            while node and c not in self._goto[node]:
                node = self._fail[node]
            node = self._goto[node].get(c, 0)
            for kind, length in self._out[node]:
                start, end = i - length + 1, i + 1
                before = folded[start - 1] if start > 0 else " "
                after = folded[end] if end < len(folded) else " "
                if not before.isalnum() and not after.isalnum():
                    found.append((start, end, kind))
        return found

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> list[tuple[int, int, str]]:
        return self.find(kwargs["text"])


# --------------------------------------------------------------------------- #
# endregion Keyword automaton                                                 #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Recognition                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Mention(IProduct):
    """One entity found in the text: where it is, what kind, its comparable value."""

    start: int
    end: int
    kind: str
    value: str

    @property
    def name(self) -> str:
        return type(self).__name__


class EntityRecognition(Wattleflow, IStrategy):
    """Step 2: finds entities of the requested kinds.

    Patterns and check digits are constants of their standards. Dictionaries,
    titles and context words come from configuration. English word forms below
    (street types, legal suffixes, age phrases) belong to `language: en`, the
    only language of the first phase (SyRS §11 t. 5).
    """

    __slots__ = ("_automaton", "_context", "_jurisdictions", "_kinds", "_titles")

    # Order is priority: an earlier pattern wins an overlap.
    PATTERNS: tuple[tuple[str, str], ...] = (
        ("EML", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        ("ONL", r"https?://[^\s<>\"']+|\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        ("ACC", r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b"),
        ("ACC", r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])"),
        ("ID", r"(?<![\d-])\d(?:[ -]?\d){7,10}(?![\d-])"),
        ("DEV", r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"),
        ("VEH", r"\b(?=[A-HJ-NPR-Z0-9]*\d)(?=[A-HJ-NPR-Z0-9]*[A-HJ-NPR-Z])[A-HJ-NPR-Z0-9]{17}\b"),
        ("DAT", "|".join(DateForms.PATTERNS)),
        ("TIM", r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s?[ap]\.?m\.?)?"),
        ("TEL", r"(?<![\w+])\+?\d[\d\s().-]{6,}\d(?!\w)"),
        (
            "ADR",
            r"\b\d{1,5}[A-Za-z]?\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|"
            r"Drive|Dr|Court|Ct|Place|Pl|Boulevard|Blvd|Way|Parade|Pde|Terrace|Tce|Crescent|"
            r"Cres|Highway|Hwy)\b\.?",
        ),
        ("AGE", r"\b(?:aged\s+\d{1,3}|\d{1,3}\s?(?:years?|yrs?)\s?old)\b"),
        ("MON", r"[$€£¥]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?[A-Z]{3}\b"),
        ("PCT", r"\b\d+(?:\.\d+)?\s?%"),
        ("QTY", r"\b\d+(?:\.\d+)?\s?(?:kg|mg|km|cm|mm|ml|g|m|l|t)\b"),
        ("NUM", r"\b\d+(?:st|nd|rd|th)?\b"),
    )
    PERSON = r"\b(?:%s)\.?\s+((?:[A-Z][\w'-]+\s?){1,3})"
    ORGANISATION = r"\b((?:[A-Z][\w&'-]*\s){1,4}(?:Pty\.?\s+Ltd|Ltd|Limited|Inc|LLC|PLC|Corporation|Corp))\b\.?"
    CONTEXT_WINDOW = 15

    def __init__(
        self,
        kinds: Iterable[str],
        dictionary: Mapping[str, str] | None = None,
        titles: Iterable[str] = (),
        context: Mapping[str, Iterable[str]] | None = None,
        jurisdictions: Iterable[str] = (),
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._kinds = set(kinds)
        self._automaton = KeywordAutomaton(
            {phrase: kind for phrase, kind in (dictionary or {}).items() if kind in self._kinds}
        )
        self._titles = tuple(titles)
        self._context = {k: tuple(w.casefold() for w in v) for k, v in (context or {}).items()}
        self._jurisdictions = set(jurisdictions)

    # region Public

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> list[Mention]:
        return self.find(kwargs["text"])

    def find(self, text: str) -> list[Mention]:
        candidates: list[tuple[int, int, int, str]] = []
        for start, end, kind in self._automaton.find(text):
            candidates.append((start, end, -1, kind))
        for priority, (kind, pattern) in enumerate(self.PATTERNS):
            for m in re.finditer(pattern, text, flags=re.IGNORECASE if kind in ("AGE", "DAT") else 0):
                resolved = self._resolve(kind, m.group(0), text, m.start())
                if resolved:
                    candidates.append((m.start(), m.end(), priority, resolved))
        if "PER" in self._kinds and self._titles:
            titles = "|".join(re.escape(t.rstrip(".")) for t in self._titles)
            for m in re.finditer(self.PERSON % titles, text):
                candidates.append((m.start(1), m.start(1) + len(m.group(1).rstrip()), 0, "PER"))
        if "ORN" in self._kinds:
            for m in re.finditer(self.ORGANISATION, text):
                candidates.append((m.start(1), m.end(1), 0, "ORN"))
        return self._select(text, candidates)

    # endregion Public

    # region Private

    def _resolve(self, kind: str, raw: str, text: str, start: int) -> str | None:
        digits = IdentityNormaliser.digits(raw)
        if kind == "ACC":
            if raw[:2].isalpha():
                return "ACC" if CheckDigit.iban(raw) and "ACC" in self._kinds else None
            return "ACC" if CheckDigit.luhn(digits) and "ACC" in self._kinds else None
        if kind == "ID":
            return self._national(digits)
        if kind == "ONL" and not raw.lower().startswith("http"):
            if not all(int(p) <= 255 for p in raw.split(".")):
                return None
        if kind == "TEL" and not 8 <= len(digits) <= 15:
            return None
        if kind == "DAT":
            if DateForms.iso(raw) is None:
                return None
            if "DOB" in self._kinds and self._near(text, start, "DOB"):
                return "DOB"
        if kind == "DEV" and "DEV" not in self._kinds:
            return None
        return kind if kind in self._kinds else None

    def _national(self, digits: str) -> str | None:
        checks: list[tuple[str, str, bool]] = []
        if "AU" in self._jurisdictions:
            checks += [
                ("NID", "tfn", CheckDigit.tfn(digits)),
                ("BID", "abn", CheckDigit.abn(digits)),
                ("BID", "acn", CheckDigit.acn(digits)),
                ("NID", "medicare", CheckDigit.medicare(digits)),
            ]
        if "HR" in self._jurisdictions:
            checks.append(("NID", "oib", CheckDigit.oib(digits)))
        for kind, _, valid in checks:
            if valid and kind in self._kinds:
                return kind
        return None

    def _near(self, text: str, start: int, kind: str) -> bool:
        words = self._context.get(kind, ())
        window = text[max(0, start - self.CONTEXT_WINDOW) : start].casefold()
        return any(w in window for w in words)

    def _select(self, text: str, candidates: list[tuple[int, int, int, str]]) -> list[Mention]:
        ordered = sorted(candidates, key=lambda c: (c[2], -(c[1] - c[0]), c[0]))
        taken: list[tuple[int, int]] = []
        chosen: list[Mention] = []
        for start, end, _, kind in ordered:
            if any(start < e and s < end for s, e in taken):
                continue
            taken.append((start, end))
            chosen.append(Mention(start, end, kind, IdentityNormaliser.value(kind, text[start:end], self._titles)))
        return sorted(chosen, key=lambda m: m.start)

    # endregion Private


# --------------------------------------------------------------------------- #
# endregion Recognition                                                       #
# --------------------------------------------------------------------------- #
