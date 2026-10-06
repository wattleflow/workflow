# Module name: helpers/datetime.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
import os
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
        """Now, written by `ZonedDateTimeHelper` in UTC (NFRQ-DEF-04)."""
        return ZonedDateTimeHelper.convert(datetime.now(timezone.utc), zone="UTC")

    @staticmethod
    def timestamp() -> float:
        return datetime.now(timezone.utc).timestamp()


class Zone:
    """Moves a datetime to one reference zone before it is compared or printed.

    A timestamp that carries the offset it was written with is correct and
    useless for ordering: two records of the SAME moment, one written `+1000`
    and one `+0000`, format as different times and sometimes different days.
    Anything that names, sorts or buckets by time has to convert first — this is
    where that conversion lives, so it is done one way everywhere."""

    @staticmethod
    def of(name: str | None = None) -> tzinfo | None:
        """The named IANA zone. None — for no name — means the SYSTEM zone, and
        is returned as None on purpose: the system offset must be resolved for
        the moment being converted, not snapshotted now. Snapshotting it
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
        """Abbreviation the zone uses at that moment (AEST/AEDT, CET/CEST) —
        for reporting, never for parsing: the abbreviations are not unique."""
        return Zone.convert(moment, zone).strftime("%Z") or "?"

    @classmethod
    def utc(cls, moment: datetime, default: str | None = None) -> datetime:
        return cls.convert(moment, "UTC", default)


class ZonedDateTimeHelper:
    """A zoned datetime as RFC 3339 text (the Internet profile of ISO 8601), and back.

    The zoned datetime is the norm (NFRQ-DEF-04): it names one point in time for every reader.
    `write` gives the default form, `convert` a declared deviation from it, `read` the zoned
    datetime a text names. The defaults are the installation's settings, read once at import:
    the zone from `ENV_ZONE` when set, else the system zone (`Zone.of(None)`); microseconds; UTC
    marked `Z`. A datetime without a zone is the other model (`DateTimeHelper`, NFRQ-DEF-05) and is
    refused here; nothing assumes a zone for it.
    """

    #: The environment variable naming the default zone (IANA name or "UTC").
    ENV_ZONE: ClassVar[str] = "WATTLEFLOW_TIME_ZONE"
    #: Zone the default form is written in; None is the system zone.
    DEFAULT_ZONE: ClassVar[str | None] = os.getenv("WATTLEFLOW_TIME_ZONE") or None
    #: Precision of the default form (`datetime.isoformat(timespec=...)`).
    DEFAULT_TIMESPEC: ClassVar[str] = "microseconds"
    #: How a UTC offset is written: "Z" (RFC 3339 §4.3), or None for "+00:00".
    DEFAULT_UTC_MARKER: ClassVar[str | None] = "Z"

    _UTC_OFFSET: ClassVar[str] = "+00:00"
    _UNSET: ClassVar[object] = object()

    @classmethod
    def write(cls, moment: datetime) -> str:
        """`moment` in the default form; a datetime without a zone is a ValueError."""
        return cls.convert(moment)

    @classmethod
    def convert(
        cls,
        moment: datetime,
        *,
        zone: str | tzinfo | None | object = _UNSET,
        timespec: str | None = None,
        utc_marker: str | None | object = _UNSET,
    ) -> str:
        """`moment` written in `zone` with `timespec`, UTC marked `utc_marker`.

        Each argument left out is the class default. `zone` is an IANA name, "UTC", None for the
        system zone, or a `tzinfo` (`moment.tzinfo` keeps the offset the value carries).
        """
        cls._refuse_naive(moment)
        target = cls.DEFAULT_ZONE if zone is cls._UNSET else zone
        marker = cls.DEFAULT_UTC_MARKER if utc_marker is cls._UNSET else utc_marker
        moved = (
            moment.astimezone(target)
            if isinstance(target, tzinfo)
            else Zone.convert(moment, target)
        )
        text = moved.isoformat(timespec=timespec or cls.DEFAULT_TIMESPEC)
        if marker and text.endswith(cls._UTC_OFFSET):
            text = text[: -len(cls._UTC_OFFSET)] + marker
        return text

    @staticmethod
    def read(text: str) -> datetime:
        """The zoned datetime `text` names (RFC 3339, `Z` or ±HH:MM); other text is a ValueError."""
        moment = datetime.fromisoformat(str(text).strip())
        if moment.tzinfo is None:
            raise ValueError(
                f"{text!r} carries no offset, so it is a datetime without a zone. Fix: write the "
                "offset (Z or ±HH:MM), or read it with DateTimeHelper.read()"
            )
        return moment

    @staticmethod
    def _refuse_naive(moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError(
                f"{moment.isoformat()} is a datetime without a zone. Fix: make it zoned with "
                "DateTimeHelper.zoned(value, zone=...), or write it with DateTimeHelper.write()"
            )


class DateTimeHelper:
    """A datetime without a zone as ISO 8601 text without an offset, and back (NFRQ-DEF-05).

    Not the norm: it names no single point in time, so it is held only where its source gives no
    zone. `zoned` is the one crossing into the norm (`ZonedDateTimeHelper`), and the zone is always
    the caller's to name. A zoned datetime is refused here.
    """

    #: Precision of `write` (`datetime.isoformat(timespec=...)`).
    DEFAULT_TIMESPEC: ClassVar[str] = "microseconds"

    @classmethod
    def write(cls, moment: datetime, timespec: str | None = None) -> str:
        """`moment` as ISO 8601 text without an offset; a zoned datetime is a ValueError."""
        cls._refuse_zoned(moment)
        return moment.isoformat(timespec=timespec or cls.DEFAULT_TIMESPEC)

    @staticmethod
    def read(text: str) -> datetime:
        """The datetime without a zone `text` names; text with an offset is a ValueError."""
        moment = datetime.fromisoformat(str(text).strip())
        if moment.tzinfo is not None:
            raise ValueError(
                f"{text!r} carries an offset, so it is a zoned datetime. Fix: read it with "
                "ZonedDateTimeHelper.read()"
            )
        return moment

    @classmethod
    def zoned(cls, moment: datetime, *, zone: str | None) -> datetime:
        """`moment` read in `zone` (an IANA name, "UTC", or None for the system zone, named by the
        caller): the zoned datetime of the norm."""
        cls._refuse_zoned(moment)
        return Zone.convert(moment, zone, default=zone)

    @staticmethod
    def _refuse_zoned(moment: datetime) -> None:
        if moment.tzinfo is not None:
            raise ValueError(
                f"{moment.isoformat()} is a zoned datetime. Fix: write it with "
                "ZonedDateTimeHelper.write() or ZonedDateTimeHelper.convert()"
            )


class DateTimeKind:
    """Hands a datetime whose model its source decides (metadata of a document, a mail header) to the
    helper of that model, unchanged: zoned to `ZonedDateTimeHelper`, without a zone to
    `DateTimeHelper`. It converts nothing and assumes no zone (NFRQ-DEF-04, NFRQ-DEF-05)."""

    @staticmethod
    def text(moment: datetime) -> str:
        """A zoned datetime with the offset it carries; one without a zone as such."""
        if moment.tzinfo is None:
            return DateTimeHelper.write(moment)
        return ZonedDateTimeHelper.convert(moment, zone=moment.tzinfo)

    @staticmethod
    def parse(text: str) -> datetime:
        """ISO 8601 text as the model it names; text that is not ISO 8601 is a ValueError."""
        try:
            return ZonedDateTimeHelper.read(text)
        except ValueError:
            return DateTimeHelper.read(text)


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
                f"created_from ({DateTimeKind.text(self._from)}) is later than "
                f"created_to ({DateTimeKind.text(self._to)})"
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
        return datetime.fromtimestamp(ts).astimezone()  # zoned: the norm (NFRQ-DEF-04)

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
        # so no branch here wraps and re-raises.
        try:
            return DateTimeKind.parse(text)
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
            return self._zoned(value)
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
            return self._zoned(dt)
        if end_of_day:
            dt = datetime.combine(dt.date(), time(23, 59, 59, 999999))
        return self._zoned(dt)

    @staticmethod
    def _zoned(moment: datetime) -> datetime:
        # A bound from the configuration without a zone is read in the installation's zone before it
        # is compared with the zoned file time (NFRQ-DEF-05 c.3).
        if moment.tzinfo is not None:
            return moment
        return DateTimeHelper.zoned(moment, zone=ZonedDateTimeHelper.DEFAULT_ZONE)


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
        the caller's to interpret, so neither branch raises.
        """
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return DateTimeKind.parse(text)
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
        if moment.tzinfo is None:
            moment = DateTimeHelper.zoned(moment, zone=cls.ASSUME)
        return Zone.convert(moment, zone).strftime(cls.FORMAT)

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

__all__ = [
    "Now",
    "Zone",
    "ZonedDateTimeHelper",
    "DateTimeHelper",
    "DateTimeKind",
    "Stamp",
    "CreatedWithin",
    "CreatedVerdict",
]
