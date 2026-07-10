# Module name: helpers/datetime.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path

__all__ = ["Now", "CreatedWithin", "CreatedVerdict"]


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


# --------------------------------------------------------------------------- #
# region CreatedWithin — date-window file selection                           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CreatedVerdict:
    """Outcome of one file's date-window check; the caller owns the logging."""

    ok: bool
    created_at: datetime | None = None
    reason: str | None = None  # "before-window" | "after-window" | "stat-failed"
    error: str | None = None


class CreatedWithin:
    """Selects files by their date, a concern distinct from filename matching.

    Looks only at the file's timestamp: the filesystem birth time when the
    platform exposes it, falling back to last-modified time when it does not
    (Linux without statx). Name/glob filtering is a separate axis and is not
    handled here.
    """

    def __init__(
        self,
        created_from: str | datetime | None,
        created_to: str | datetime | None,
    ) -> None:
        self._from: datetime | None = self._parse(created_from, end_of_day=False)
        self._to: datetime | None = self._parse(created_to, end_of_day=True)
        if self._from and self._to and self._from > self._to:
            raise ValueError(
                f"created_from ({self._from.isoformat()}) is later than "
                f"created_to ({self._to.isoformat()})"
            )

    @property
    def active(self) -> bool:
        return bool(self._from or self._to)

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
    def _parse(value: str | datetime | None, *, end_of_day: bool) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            if "T" in text or " " in text and ":" in text:
                return datetime.fromisoformat(text.replace(" ", "T"))
            dt = datetime.fromisoformat(text)
        except ValueError as e:
            raise ValueError(
                f"Invalid date '{text}': expected ISO format "
                "YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            ) from e
        if end_of_day:
            dt = datetime.combine(dt.date(), time(23, 59, 59, 999999))
        return dt


# --------------------------------------------------------------------------- #
# endregion CreatedWithin                                                     #
# --------------------------------------------------------------------------- #
