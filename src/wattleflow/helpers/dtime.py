# Module name: helpers/datetime.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timezone, tzinfo
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, ClassVar, Iterable
from wattleflow.core.transactional import IParser


# --------------------------------------------------------------------------- #
# region Clasess                                                              #
# --------------------------------------------------------------------------- #


class Now:
    @staticmethod
    def utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def local() -> datetime:
        return datetime.now().astimezone()

    @staticmethod
    def iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def timestamp() -> float:
        return datetime.now(timezone.utc).timestamp()


class Zone:
    """Moves a datetime to one reference zone before it is compared or printed.

    A timestamp that carries the offset it was written with is correct and
    useless for ordering: two records of the SAME instant, one written `+1000`
    and one `+0000`, format as different times and sometimes different days.
    Anything that names, sorts or buckets by time has to convert first — this is
    where that conversion lives, so it is done one way everywhere.

    Naive input is assumed to be in `default` (the machine zone unless another
    is named) rather than in UTC: a value written without an offset was written
    by a clock somewhere, and treating it as UTC silently shifts it. The
    assumption cannot be avoided, only declared — which is why it is a
    parameter."""

    @staticmethod
    def of(name: str | None = None) -> tzinfo | None:
        """The named IANA zone. None — for no name — means the SYSTEM zone, and
        is returned as None on purpose: the system offset must be resolved for
        the instant being converted, not snapshotted now. Snapshotting it
        (`datetime.now().astimezone().tzinfo`) yields today's offset and then
        stamps every summer date with the winter offset, or the reverse."""
        if not name:
            return None
        if name.upper() == "UTC":
            return timezone.utc
        return ZoneInfo(name)

    @classmethod
    def convert(
        cls,
        moment: datetime,
        zone: str | None = None,
        default: str | None = None,
    ) -> datetime:
        """`moment` seen from `zone`; a naive value is first read as `default`."""
        if moment.tzinfo is None:
            source = cls.of(default)
            # `naive.astimezone()` reads the value as system local time, applying
            # the rules in force on THAT date.
            moment = moment.replace(tzinfo=source) if source else moment.astimezone()
        target = cls.of(zone)
        return moment.astimezone(target) if target else moment.astimezone()

    @staticmethod
    def label(moment: datetime, zone: str | None = None) -> str:
        """Abbreviation the zone uses at that instant (AEST/AEDT, CET/CEST) —
        for reporting, never for parsing: the abbreviations are not unique."""
        return Zone.convert(moment, zone).strftime("%Z") or "?"

    @classmethod
    def utc(cls, moment: datetime, default: str | None = None) -> datetime:
        return cls.convert(moment, "UTC", default)


@dataclass(frozen=True)
class CreatedVerdict:
    """Outcome of one file's date-window check; the caller owns the logging."""

    ok: bool
    created_at: datetime | None = None
    reason: str | None = None  # "before-window" | "after-window" | "stat-failed"
    error: str | None = None


class CreatedWithin(IParser):
    """Selects files by their date, a concern distinct from filename matching.
    Looks only at the file's timestamp: the filesystem birth time when the
    platform exposes it, falling back to last-modified time when it does not
    (Linux without statx). Name/glob filtering is a separate axis and is not
    handled here.
    """

    __slots__ = ("_from", "_to")

    def __init__(
        self,
        created_from: str | datetime | None,
        created_to: str | datetime | None,
    ) -> None:
        self._from: datetime | None = self.parse(value=created_from, end_of_day=False)
        self._to: datetime | None = self.parse(value=created_to, end_of_day=True)
        if self._from and self._to and self._from > self._to:
            raise ValueError(
                f"created_from ({self._from.isoformat()}) is later than "
                f"created_to ({self._to.isoformat()})"
            )

    @property
    def active(self) -> bool:
        return bool(self._from or self._to)

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def start(self) -> datetime | None:
        return self._from

    @property
    def end(self) -> datetime | None:
        return self._to

    @staticmethod
    def created_at(path: Path) -> datetime:
        # "Created" = when the file came into being AT THIS LOCATION. The right
        # stat field is OS-dependent, so this is deliberately not st_mtime:
        #   - Birth time (macOS/BSD, Linux 3.12+ statx, Windows 3.12+) is the
        #     true creation time — always preferred when the platform exposes it.
        #   - Windows: st_ctime IS the creation time (per os.stat docs).
        #   - Linux/WSL (incl. NTFS via /mnt/c): no birth time on 3.11; st_ctime
        #     is inode change/creation-here — it is set when a file is copied
        #     into an inbox even though st_mtime stays the source's old date.
        #     Using st_mtime would misclassify freshly-copied files as old.
        st = path.stat()
        ts = getattr(st, "st_birthtime", None)
        if ts is None:
            ts = st.st_ctime
        return datetime.fromtimestamp(ts)

    def check(self, path: Path) -> CreatedVerdict:
        try:
            created_at = self.created_at(path)
        except OSError as e:
            return CreatedVerdict(False, reason="stat-failed", error=str(e))
        if self._from and created_at < self._from:
            return CreatedVerdict(False, created_at=created_at, reason="before-window")
        if self._to and created_at > self._to:
            return CreatedVerdict(False, created_at=created_at, reason="after-window")
        return CreatedVerdict(True, created_at=created_at)

    @staticmethod
    def _iso(text: str) -> datetime | None:
        # A probe, not a gate: the caller decides what an unreadable value means,
        # so no branch here wraps and re-raises (DR-WFL-018 t.2).
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def parse(
        self,
        value: str | datetime | None,
        *,
        end_of_day: bool,
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        with_time = "T" in text or " " in text and ":" in text
        dt = self._iso(text.replace(" ", "T") if with_time else text)
        if dt is None:
            raise ValueError(
                f"Invalid date '{text}': expected ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            )
        if with_time:
            return dt
        if end_of_day:
            dt = datetime.combine(dt.date(), time(23, 59, 59, 999999))
        return dt


class Stamp:
    """One reading of a moment as a file-name stamp, so every name agrees.

    Naming, sorting and bucketing by time need the same three answers — which
    value states the time, on which clock it is read, and how it is written —
    and a second copy of them produces a second name for one document. The
    clock policy is `Zone`'s: a value without an offset is read on the machine's
    own clock, never as UTC.

    `parse` is the seam a vocabulary with its own date grammar overrides (RFC
    5322 headers, for one); FORMAT and the zone reading stay fixed underneath,
    so an override changes what can be read and never what a stamp means.
    """

    #: `2026-09-16-101500` — sorts as text in the order it sorts in time.
    FORMAT: ClassVar[str] = "%Y-%m-%d-%H%M%S"
    #: Zone a value without an offset is read as; None is the machine's own.
    ASSUME: ClassVar[str | None] = None

    @classmethod
    def parse(cls, value: Any) -> datetime | None:
        """`value` as a moment, or None when it states none.

        ISO first, then RFC 5322 — a probe, not a gate: an unreadable value is
        the caller's to interpret, so neither branch raises (DR-WFL-018 t.2).
        """
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
        try:
            return parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None

    @classmethod
    def of(cls, value: Any, zone: str | None = None) -> str:
        """`value` as a stamp read from `zone`, or "" when it states no time."""
        moment = cls.parse(value)
        if moment is None:
            return ""
        return Zone.convert(moment, zone, default=cls.ASSUME).strftime(cls.FORMAT)

    @classmethod
    def first(cls, values: Iterable[Any], zone: str | None = None) -> str:
        """The first candidate that states a time; "" when none does."""
        for value in values:
            stamp = cls.of(value, zone)
            if stamp:
                return stamp
        return ""

    @classmethod
    def of_file(cls, path: Path, zone: str | None = None) -> str:
        """When the file came into being here, as a stamp (`CreatedWithin.created_at`)."""
        try:
            return cls.of(CreatedWithin.created_at(path), zone)
        except OSError:
            return ""


# --------------------------------------------------------------------------- #
# endregion Clasess                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["Now", "Zone", "Stamp", "CreatedWithin", "CreatedVerdict"]
