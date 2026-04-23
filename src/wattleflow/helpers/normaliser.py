# Module name: helpers/normaliser.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_TSEP = r"(?:\s+at\s+|[\sT,_-]+)"

# (regex, kind) — kompilira se jednom na razini modula
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # ISO: 2024-01-24 [T 14:30[:00]]
    (
        re.compile(
            r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
            rf"(?:{_TSEP}(?P<h>\d{{1,2}}):(?P<mn>\d{{2}})(?::\d{{2}})?)?"
        ),
        "numeric",
    ),
    # Kompaktni numerički: 20240124[T1430 | _1430]
    (
        re.compile(
            r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})"
            r"(?:[T_]?(?P<h>\d{2})(?P<mn>\d{2}))?(?!\d)"
        ),
        "numeric",
    ),
    # DMY s razdjelnicima: 24/01/2024 [ 14:30]
    (
        re.compile(
            r"(?<!\d)(?P<d>\d{1,2})[./](?P<m>\d{1,2})[./](?P<y>\d{2,4})"
            rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\d)"
        ),
        "numeric",
    ),
    # 24 Jan 2024 [ 14:30]
    (
        re.compile(
            r"(?<!\w)(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<y>\d{2,4})"
            rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
        ),
        "textual",
    ),
    # Jan 24, 2024 [ 14:30]
    (
        re.compile(
            r"(?<!\w)(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{2,4})"
            rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
        ),
        "textual",
    ),
    # Kompaktni tekstualni bez razmaka: 24JAN20, 24Jan2020
    (re.compile(r"(?<!\w)(?P<d>\d{1,2})(?P<mon>[A-Za-z]{3})(?P<y>\d{2,4})(?!\w)"), "textual"),
]


def _format_match(match: re.Match[str], kind: str, pivot: int) -> str | None:
    """Iz regex pogodka gradi 'YYYY-MM-DD' ili 'YYYY-MM-DD-HHMM'.
    Vraća None ako su komponente nevažeće (npr. mjesec 13)."""
    try:
        g = match.groupdict()
        if kind == "textual":
            key = g["mon"].lower().rstrip(".")
            if key not in _MONTHS:
                return None
            mo = _MONTHS[key]
        else:
            mo = int(g["m"])

        y = int(g["y"])
        d = int(g["d"])
        if y < 100:
            y = 2000 + y if y < pivot else 1900 + y

        has_time = g.get("h") is not None
        h = int(g["h"]) if has_time else 0
        mi = int(g["mn"]) if g.get("mn") else 0

        dt = datetime(y, mo, d, h, mi)
        return f"{dt:%Y-%m-%d-%H%M}" if has_time else f"{dt:%Y-%m-%d}"
    except (ValueError, KeyError):
        return None


class Normaliser(str):
    """
    str podklasa s lancanim transformacijama.

    Svaka metoda vraća NOVU instancu Normaliser-a (ili samu sebe
    ako transformacija nije primjenjiva), što omogućuje fluent API:

        Normaliser(Path("Izvještaj 24JAN20.PDF")).name().date().title()
    """

    def __new__(cls, value: Any = "") -> "Normaliser":
        # Prihvaća str, Path, ili bilo što što se može pretvoriti u str.
        return super().__new__(cls, "" if value is None else str(value))

    # ───────────── unutarnji helper ─────────────
    def _wrap(self, value: str) -> "Normaliser":
        """Vraća novu Normaliser instancu (ili self ako je sadržaj isti)."""
        return self if value == str(self) else Normaliser(value)

    # ───────────── case transformacije ─────────────
    # Preklapamo str metode da vraćaju Normaliser umjesto str,
    # inače lanac puca poslije prve transformacije.
    def upper(self) -> "Normaliser":  # type: ignore[override]
        return self._wrap(str.upper(self))

    def lower(self) -> "Normaliser":  # type: ignore[override]
        return self._wrap(str.lower(self))

    def title(self) -> "Normaliser":  # type: ignore[override]
        return self._wrap(str.title(self))

    def capitalize(self) -> "Normaliser":  # type: ignore[override]
        return self._wrap(str.capitalize(self))

    # Hrvatski alias
    def capitalise(self) -> "Normaliser":
        return self.capitalize()

    # ───────────── datum ─────────────
    def date(self, pivot: int = 70) -> "Normaliser":
        """
        Pronalazi sve prepoznatljive datume u sadržaju i zamjenjuje ih
        kanonskim oblikom 'YYYY-MM-DD' (ili 'YYYY-MM-DD-HHMM' ako
        sadrže vrijeme). Ostatak teksta ostaje netaknut.

        Ako nema poklapanja, vraća self (izvorni sadržaj).

        Dvoznamenkaste godine: y < pivot → 2000+y, inače 1900+y.
        """
        if not self:
            return self

        text = str(self)
        changed = False

        for rx, kind in _PATTERNS:

            def _sub(m: re.Match[str], _kind: str = kind) -> str:
                nonlocal changed
                result = _format_match(m, _kind, pivot)
                if result is None:
                    return m.group(0)  # nevažeći datum, ostavi kako je
                changed = True
                return result

            text = rx.sub(_sub, text)

        return self._wrap(text) if changed else self

    # ───────────── naziv datoteke ─────────────
    def name(self, max_len: int = 40, replacement: str = "-") -> "Normaliser":
        """
        Normalizira naziv datoteke: ascii, [a-z0-9-], bez dvostrukih razdjelnika,
        duljina stema <= max_len. Ekstenzija ostaje (lowercase).
        Ako stem postane prazan, koristi se 'file'.
        Štiti od rezerviranih Windows naziva.
        """
        if not self:
            return self

        # Tretiramo cijeli sadržaj kao basename — ako put sadrži razdjelnike
        # ('/' ili '\'), pretvaramo ih u dio naziva da se sadržaj ne izgubi.
        raw = str(self).strip().lower().replace("\\", "/")
        if "/" in raw:
            head, _, tail = raw.rpartition("/")
            ext = Path(tail).suffix
            stem_full = f"{head}/{Path(tail).stem}" if head else Path(tail).stem
        else:
            ext = Path(raw).suffix
            stem_full = Path(raw).stem

        # 1) Uklanjanje dijakritika (NFKD → ASCII)
        norm = unicodedata.normalize("NFKD", stem_full)
        norm = norm.encode("ascii", "ignore").decode("ascii")

        # 2) Zamjena svih ne-alfanumeričkih znakova razdjelnikom
        norm = re.sub(r"[^a-z0-9]+", replacement, norm)

        # 3) Sažimanje višestrukih razdjelnika i obrezivanje rubova
        if replacement:
            rep_esc = re.escape(replacement)
            norm = re.sub(rf"{rep_esc}{{2,}}", replacement, norm).strip(replacement)

        # 4) Fallback ako je prazno
        if not norm:
            norm = "file"

        # 5) Rezervirani Windows nazivi
        if norm in WINDOWS_RESERVED:
            norm = f"{norm}_"

        # 6) Ograničenje duljine stema
        if len(norm) > max_len:
            trimmed = norm[:max_len].rstrip(replacement) if replacement else norm[:max_len]
            norm = trimmed or "file"

        return self._wrap(f"{norm}{ext}")


class CaseText(str):
    def __format__(self, spec: str) -> str:
        if spec == "upper":
            return self.upper()
        if spec == "lower":
            return self.lower()
        if spec in ("title", "capitalise"):
            return self.title()
        return super().__format__(spec)


class Normalise1r(str):
    def __format__(self, spec: str) -> str:
        if spec == "upper":
            return self.upper()
        if spec == "lower":
            return self.lower()
        if spec in ("title", "capitalise"):
            return self.title()
        if spec == "date":
            return self._build_date()
        if spec == "name":
            return self._build_name()

        return super().__format__(spec)

    def _build_date(self, pivot: int = 70) -> str | None:
        if self == "":
            return self

        MONTHS = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "sept": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        _TSEP = r"(?:\s+at\s+|[\sT,_]+)"

        _PATTERNS = [
            (
                re.compile(
                    r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
                    rf"(?:{_TSEP}(?P<h>\d{{1,2}}):(?P<mn>\d{{2}})(?::\d{{2}})?)?"
                ),
                "numeric",
            ),
            (
                re.compile(
                    r"(?<!\d)(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>\d{2,4})"
                    rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\d)"
                ),
                "numeric",
            ),
            (
                re.compile(
                    r"(?<!\w)(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<y>\d{2,4})"
                    rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
                ),
                "textual",
            ),
            (
                re.compile(
                    r"(?<!\w)(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{2,4})"
                    rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
                ),
                "textual",
            ),
            (
                re.compile(
                    r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})"
                    r"(?:[T_]?(?P<h>\d{2})(?P<mn>\d{2}))?(?!\d)"
                ),
                "numeric",
            ),
        ]

        for rx, kind in _PATTERNS:
            for match in rx.finditer(self):
                try:
                    g = match.groupdict()
                    if kind == "textual":
                        key = g["mon"].lower().rstrip(".")
                        if key not in MONTHS:
                            raise ValueError("unknown month")
                        mo = MONTHS[key]
                    else:
                        mo = int(g["m"])

                    y = int(g["y"])
                    d = int(g["d"])
                    if y < 100:
                        y = 2000 + y if y < pivot else 1900 + y

                    h = int(g["h"]) if g.get("h") else 0
                    mi = int(g["mn"]) if g.get("mn") else 0

                    dt = datetime(y, mo, d, h, mi)
                    return f"{dt:%Y-%m-%d-%H%M}"
                except ValueError:
                    continue

        return None

    def _build_name(
        self,
        max_len: int = 40,
        replacement: str = "-",
    ) -> str:
        """
        Normalise stem (without extension) to: ascii, [a-z0-9-], without double dashes,
        stem length <= max_len. Extension remains (lowercase). If stem turns empty,
        use 'file'. Protect from reserved Windows names.
        """
        p = Path(self)
        basename = p.name.strip().lower()
        stem, ext = Path(basename).stem, Path(basename).suffix

        # 1) Remove diacritics (NFKD → ASCII)
        norm = unicodedata.normalize("NFKD", stem)
        norm = norm.encode("ascii", "ignore").decode("ascii")

        # 2) Replace any non-alphanumeric character with the separator
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


# class NormaliserDate:
#     """Detect a date (and optional time) in a string and render as YYYY-MM-DD-HHMM.
#     Missing time defaults to 0000. Returns None when no valid date is found."""

#     MONTHS = {
#         "jan": 1,
#         "january": 1,
#         "feb": 2,
#         "february": 2,
#         "mar": 3,
#         "march": 3,
#         "apr": 4,
#         "april": 4,
#         "may": 5,
#         "jun": 6,
#         "june": 6,
#         "jul": 7,
#         "july": 7,
#         "aug": 8,
#         "august": 8,
#         "sep": 9,
#         "sept": 9,
#         "september": 9,
#         "oct": 10,
#         "october": 10,
#         "nov": 11,
#         "november": 11,
#         "dec": 12,
#         "december": 12,
#     }

#     # Date↔time separator: whitespace / T / comma / underscore, or the word "at"
#     _TSEP = r"(?:\s+at\s+|[\sT,_]+)"

#     # (pattern, kind) — order matters: specific formats first
#     _PATTERNS = [
#         # ISO: 2025-01-15 | 2025-01-15T14:30 | 2025-01-15 14:30:00
#         (
#             re.compile(
#                 r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
#                 rf"(?:{_TSEP}(?P<h>\d{{1,2}}):(?P<mn>\d{{2}})(?::\d{{2}})?)?"
#             ),
#             "numeric",
#         ),
#         # DMY: 15.01.2025 | 15/01/2025 | 15-01-2025 [ 14:30 | 14.30 ]
#         (
#             re.compile(
#                 r"(?<!\d)(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>\d{2,4})"
#                 rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\d)"
#             ),
#             "numeric",
#         ),
#         # Textual DMY: "15 Jan 2025" | "15 January 2025 14:30"
#         (
#             re.compile(
#                 r"(?<!\w)(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<y>\d{2,4})"
#                 rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
#             ),
#             "textual",
#         ),
#         # Textual MDY: "Jan 15, 2025" | "January 15 2025 14:30"
#         (
#             re.compile(
#                 r"(?<!\w)(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{2,4})"
#                 rf"(?:{_TSEP}(?P<h>\d{{1,2}})[:.](?P<mn>\d{{2}}))?(?!\w)"
#             ),
#             "textual",
#         ),
#         # Compact: 20250115 | 20250115T1430 | 20250115_1430 | 202501151430
#         (
#             re.compile(
#                 r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})"
#                 r"(?:[T_]?(?P<h>\d{2})(?P<mn>\d{2}))?(?!\d)"
#             ),
#             "numeric",
#         ),
#     ]

#     @staticmethod
#     def transform(text: str, year_pivot: int = 70) -> Optional[str]:
#         if not text:
#             return None
#         for rx, kind in DateNormaliser._PATTERNS:
#             for match in rx.finditer(text):
#                 try:
#                     return DateNormaliser._build(match, kind, year_pivot)
#                 except ValueError:
#                     continue
#         return None

#     @staticmethod
#     def _build_date(match: re.Match, kind: str, pivot: int) -> str:
#         g = match.groupdict()
#         if kind == "textual":
#             key = g["mon"].lower().rstrip(".")
#             if key not in DateNormaliser.MONTHS:
#                 raise ValueError("unknown month")
#             mo = DateNormaliser.MONTHS[key]
#         else:
#             mo = int(g["m"])

#         y = int(g["y"])
#         d = int(g["d"])
#         # 2-digit year pivot: < pivot → 20xx, else 19xx
#         if y < 100:
#             y = 2000 + y if y < pivot else 1900 + y

#         h = int(g["h"]) if g.get("h") else 0
#         mi = int(g["mn"]) if g.get("mn") else 0

#         dt = datetime(y, mo, d, h, mi)  # raises ValueError on invalid combos
#         return f"{dt:%Y-%m-%d-%H%M}"
