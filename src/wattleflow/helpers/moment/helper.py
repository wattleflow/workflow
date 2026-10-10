# Module name: helpers/moment/helper.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""MomentHelper (base) + MomentAwareHelper + MomentNaiveHelper.

int: UTC ns (aware) or wall-time ns (naive). The wrong kind raises TypeError.
Conversion runs one way only: MomentAwareHelper.strip (aware -> naive); the reverse does
not exist, because a zone must not be invented (DST fold and gap).
An aware Moment is built from a datetime with a tzinfo.
Every method is a classmethod; a subclass may override it.
"""

from __future__ import annotations

__all__ = ["MomentHelper", "MomentAwareHelper", "MomentNaiveHelper"]

import os
import warnings
from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from functools import lru_cache
from struct import Struct
from time import struct_time, time_ns
from pathlib import Path
from zoneinfo import ZoneInfo
from .base import Moment, MomentRangeError


class MomentHelper:
    """Common to both kinds: zones, serialisation (which carries the kind), choice of helper.

    AWARE: True = aware, False = naive, None = either kind (a bare int is then refused).
    """

    AWARE = None
    _E_AW = datetime(1970, 1, 1, tzinfo=timezone.utc)
    _E_NA = datetime(1970, 1, 1)
    _G = 1_000_000_000
    _PK = Struct(">qIB")  # seconds int64, nanoseconds uint32, aware uint8 (13 B)
    #: The int64 ns of numpy, pandas and Arrow; -2**63 is their NaT, not a value (BR-MMN-07).
    INT64_MIN_NS = -(2**63) + 1
    INT64_MAX_NS = 2**63 - 1
    #: The global setting of the workflow zone (BR-MMN-12).
    ENV_ZONE = "WATTLEFLOW_TIME_ZONE"
    _workflow_zone: str | None = None

    # ---------- workflow zone ----------
    @classmethod
    def configure(cls, zone=None) -> str:
        """Sets the workflow zone once, at the start of a workflow (BR-MMN-12).

        `zone`, else ENV_ZONE, else the system zone, else UTC with one warning.
        """
        name = cls.key(zone) if zone is not None else None
        if name is None:
            name = cls.key(os.environ.get(cls.ENV_ZONE) or None) or cls._system_zone()
        if name is None:
            warnings.warn(
                f"the system zone has no IANA name; times are shown in UTC. Set {cls.ENV_ZONE}",
                RuntimeWarning,
                stacklevel=2,
            )
            name = "UTC"
        MomentHelper._workflow_zone = name
        return name

    @classmethod
    def workflow_zone(cls) -> str:
        """The workflow zone, resolved on first use when no workflow configured it."""
        return MomentHelper._workflow_zone or cls.configure()

    @staticmethod
    def _system_zone() -> str | None:
        # The standard library names the system zone only through TZ or /etc/localtime.
        name = (os.environ.get("TZ") or "").lstrip(":")
        if not name:
            link = Path("/etc/localtime")
            target = str(link.resolve()) if link.is_symlink() else ""
            name = target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else ""
        try:
            return Moment._key(name) if name else None
        except Exception:
            return None

    # ---------- zones ----------
    @staticmethod
    @lru_cache(maxsize=64)
    def zone(name: str) -> ZoneInfo:
        return ZoneInfo(name)

    key = staticmethod(Moment._key)  # alias: the one source of truth is Moment

    # ---------- choice of helper ----------
    @classmethod
    def of(cls, x):
        """MomentAwareHelper or MomentNaiveHelper by the kind of a Moment or datetime."""
        if isinstance(x, Moment):
            aw = x.aware
        elif isinstance(x, datetime):
            aw = x.tzinfo is not None
        else:
            raise TypeError(f"cannot tell the kind of: {type(x).__name__}")
        return MomentAwareHelper if aw else MomentNaiveHelper

    # ---------- internal ----------
    @classmethod
    def _wrong(cls):
        return TypeError(
            "expected an aware input (Moment or datetime with a zone)"
            if cls.AWARE
            else "expected a naive input (Moment or datetime without a zone)"
        )

    @classmethod
    def _parts(cls, x):
        """x -> (ns, aware, tz); the kind must match cls.AWARE."""
        a = cls.AWARE
        if type(x) is int or (not isinstance(x, (Moment, datetime)) and hasattr(x, "__index__")):
            if a is None:
                raise TypeError(
                    "a bare int has no kind; use MomentAwareHelper or MomentNaiveHelper"
                )
            return int(x), a, None
        if isinstance(x, Moment):
            ns, aw, tz = x.ns, x.aware, x.tz
        elif isinstance(x, datetime):
            z = x.tzinfo
            if z is None:
                d, aw, tz = x - cls._E_NA, False, None
            else:
                d, aw, tz = x - cls._E_AW, True, cls.key(z)
            ns = ((d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds) * 1000
        else:
            raise TypeError(f"unsupported type: {type(x).__name__}")
        if a is not None and aw != a:
            raise cls._wrong()
        return ns, aw, tz

    @classmethod
    def _fields(cls, x):
        a = cls.AWARE
        if type(x) is Moment and (a is None or a == x.aware):
            return x.ns, x.aware, x.tz
        return cls._parts(x)

    @classmethod
    def _expect(cls, m: Moment) -> Moment:
        if cls.AWARE is not None and m.aware != cls.AWARE:
            raise cls._wrong()
        return m

    @staticmethod
    def _off_ns(off: timedelta) -> int:
        return ((off.days * 86400 + off.seconds) * 1_000_000 + off.microseconds) * 1000

    # ---------- serialisation (carries the kind) ----------
    @classmethod
    def to_dict(cls, x) -> dict:
        ns, aw, tz = cls._fields(x)
        sec, nsec = divmod(ns, cls._G)
        return {"sec": sec, "nsec": nsec, "aware": aw, "tz": tz}

    @classmethod
    def from_dict(cls, d: dict) -> Moment:
        return cls._expect(Moment(d["sec"] * cls._G + d["nsec"], d["aware"], d.get("tz")))

    @classmethod
    def to_bytes(cls, x) -> bytes:
        ns, aw, tz = cls._fields(x)
        sec, nsec = divmod(ns, cls._G)
        return cls._PK.pack(sec, nsec, aw) + (tz.encode() if tz else b"")

    @classmethod
    def from_bytes(cls, b: bytes) -> Moment:
        sec, nsec, a = cls._PK.unpack_from(b)
        return cls._expect(Moment(sec * cls._G + nsec, bool(a), b[cls._PK.size :].decode() or None))

    # ---------- text whose kind the source decides ----------
    @classmethod
    def text(cls, x) -> str:
        """ISO 8601 of either kind in the default form (microseconds in full, UTC as 'Z'):
        a moment with the offset of its zone, a wall time without one."""
        helper = cls.of(x)
        if helper.AWARE:
            return helper.to_iso(x, timespec="microseconds", z=True)
        return helper.to_iso(x, timespec="microseconds")

    @classmethod
    def parse_iso(cls, text: str) -> Moment:
        """A moment when the text carries an offset or 'Z', else a wall time; other text, ValueError."""
        value = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
        return cls.of(value).moment(value)

    # ---------- bridge to int64 ns columns ----------
    @classmethod
    def to_int64_ns(cls, x) -> int:
        """ns for an int64 column; outside int64, or NaT, a MomentRangeError.

        The one way into ns columns: numpy wraps an out-of-range value silently on some paths.
        """
        ns = cls._fields(x)[0]
        if not cls.INT64_MIN_NS <= ns <= cls.INT64_MAX_NS:
            raise MomentRangeError(f"{ns} ns is outside the int64 ns of a column")
        return ns

    @staticmethod
    def _shown(make):
        # Past years 1-9999 (zone edge, inf) datetime fails; it is named a range error (BR-MMN-06).
        try:
            return make()
        except (OverflowError, ValueError) as e:
            raise MomentRangeError(f"outside years 1-9999 in this form ({e})") from e


class MomentAwareHelper(MomentHelper):
    """Aware time: a UTC moment (+ a zone for display). A bare int = UTC ns."""

    AWARE = True
    _JD_UNIX = 2440587.5  # JD of 1970-01-01T00:00:00 UTC

    # ================= input -> Moment =================
    @classmethod
    def moment(cls, x, tz=None) -> Moment:
        """Aware Moment from Moment | datetime (with a zone) | int (UTC ns).

        `tz` sets the display zone.
        """
        if tz is None and type(x) is datetime:  # the common path
            z = x.tzinfo
            if z is None:
                raise cls._wrong()
            d = x - cls._E_AW
            return Moment._raw(
                ((d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds) * 1000, True, cls.key(z)
            )
        ns, _, tzs = cls._parts(x)
        return Moment._raw(ns, True, tzs if tz is None else cls.key(tz))

    @classmethod
    def from_iso(cls, s: str) -> Moment:
        """The ISO text must carry an offset or 'Z'; without one TypeError (no zone is invented)."""
        return cls.moment(datetime.fromisoformat(s.replace("Z", "+00:00")))

    @classmethod
    def from_str(cls, s: str, fmt: str) -> Moment:
        """strptime; the format must yield a zone (e.g. %z), otherwise TypeError."""
        return cls.moment(datetime.strptime(s, fmt))

    @classmethod
    def from_unix(cls, sec: float, tz=None) -> Moment:
        return Moment._raw(cls._shown(lambda: round(sec * cls._G)), True, cls.key(tz))

    @classmethod
    def from_unix_ns(cls, ns: int, tz=None) -> Moment:
        return Moment._raw(int(ns), True, cls.key(tz))

    @classmethod
    def now(cls, tz=None) -> Moment:
        """This moment, shown in `tz`, else in the workflow zone (BR-MMN-12)."""
        return Moment._raw(time_ns(), True, cls.key(tz) if tz is not None else cls.workflow_zone())

    # ================= output =================
    @classmethod
    def to_datetime(cls, x, tz=None) -> datetime:
        """In zone `tz`, else the stored zone, else UTC."""
        t = type(x)
        if t is Moment:
            if not x.aware:
                raise cls._wrong()
            ns, z = x.ns, (tz if tz is not None else x.tz)
        elif t is int:
            ns, z = x, tz
        elif isinstance(x, datetime):
            if x.tzinfo is None:
                raise cls._wrong()
            if tz is None:
                return x
            return cls._shown(lambda: x.astimezone(cls.zone(tz) if isinstance(tz, str) else tz))
        else:
            ns, _, tzs = cls._parts(x)
            z = tz if tz is not None else tzs
        dt = cls._shown(lambda: cls._E_AW + timedelta(microseconds=ns // 1000))
        if z is None:
            return dt
        return cls._shown(lambda: dt.astimezone(cls.zone(z) if isinstance(z, str) else z))

    @classmethod
    def to_utc(cls, x) -> datetime:
        return cls.to_datetime(x, timezone.utc)

    @classmethod
    def to_local(cls, x) -> datetime:
        """datetime in the operating system's zone."""
        return cls._shown(lambda: cls.to_datetime(x, timezone.utc).astimezone())

    @classmethod
    def to_str(cls, x, fmt: str = None, tz=None) -> str:
        """Without `fmt`: the form of str(datetime). With `fmt`: strftime."""
        dt = cls.to_datetime(x, tz)
        return str(dt) if fmt is None else dt.strftime(fmt)

    @classmethod
    def to_iso(cls, x, tz=None, timespec: str = "auto", z: bool = False) -> str:
        """isoformat; z=True writes '+00:00' as 'Z'."""
        s = cls.to_datetime(x, tz).isoformat(timespec=timespec)
        return s[:-6] + "Z" if (z and s.endswith("+00:00")) else s

    @classmethod
    def to_unix_ns(cls, x) -> int:
        t = type(x)
        if t is int:
            return x
        if t is Moment:
            if not x.aware:
                raise cls._wrong()
            return x.ns
        return cls._parts(x)[0]

    @classmethod
    def to_unix(cls, x) -> float:
        return cls.to_unix_ns(x) / cls._G

    @classmethod
    def to_date(cls, x, tz=None) -> date:
        return cls.to_datetime(x, tz).date()

    @classmethod
    def to_time(cls, x, tz=None) -> time:
        return cls.to_datetime(x, tz).time()

    @classmethod
    def to_struct(cls, x, tz=None) -> struct_time:
        return cls.to_datetime(x, tz).timetuple()

    @classmethod
    def to_rfc2822(cls, x, tz=None) -> str:
        return format_datetime(cls.to_datetime(x, tz))

    @classmethod
    def to_http(cls, x) -> str:
        return format_datetime(cls.to_datetime(x, timezone.utc), usegmt=True)

    @classmethod
    def to_jd(cls, x) -> float:
        """Julian date as float64 (resolution ~40 µs; use ns for exactness)."""
        return cls.to_unix_ns(x) / (86400 * cls._G) + cls._JD_UNIX

    @classmethod
    def to_mjd(cls, x) -> float:
        """Modified JD as float64 (resolution ~0.6 µs)."""
        return cls.to_jd(x) - 2400000.5

    # ================= zone and one-way conversion =================
    @classmethod
    def with_tz(cls, x, tz):
        """The same moment, another display zone. Moment -> Moment, datetime -> datetime."""
        if isinstance(x, datetime):
            if x.tzinfo is None:
                raise cls._wrong()
            return cls.to_datetime(x, tz)
        if not isinstance(x, Moment):
            raise TypeError("an int has no zone; use a Moment or a datetime")
        if not x.aware:
            raise cls._wrong()
        return x._raw(x.ns, True, cls.key(tz))

    @classmethod
    def strip(cls, x, tz=None):
        """Aware -> NAIVE (one way, the zone is lost): the wall time in zone `tz`.

        `tz` defaults to the stored zone, else UTC. Moment -> Moment, datetime -> datetime,
        int (UTC ns) -> int (wall-time ns).
        """
        if isinstance(x, datetime):
            if x.tzinfo is None:
                raise cls._wrong()
            return (x if tz is None else cls.to_datetime(x, tz)).replace(tzinfo=None)
        ns, _, tzs = cls._parts(x)
        z = tz if tz is not None else tzs
        out = ns
        if z is not None:
            zone = cls.zone(z) if isinstance(z, str) else z
            inst = cls.to_datetime(ns, timezone.utc)
            out = ns + cls._off_ns(cls._shown(lambda: inst.astimezone(zone)).utcoffset())
        if isinstance(x, Moment):
            return x._raw(out, False, None)
        if not Moment.MIN_NS <= out <= Moment.MAX_NS:
            raise MomentRangeError(f"{out} ns is outside years 1-9999")
        return out


class MomentNaiveHelper(MomentHelper):
    """Naive time: a wall time without a zone. A bare int = wall-time ns.

    No unix/http/jd/zone operations, no RFC 5322 form (its '-0000' means UTC, BR-MMN-09) and NO
    conversion to aware (a zone is never invented).
    """

    AWARE = False

    # ================= input -> Moment =================
    @classmethod
    def moment(cls, x) -> Moment:
        """Naive Moment from Moment | datetime (without a zone) | int (wall-time ns)."""
        if type(x) is datetime:
            if x.tzinfo is not None:
                raise cls._wrong()
            d = x - cls._E_NA
            return Moment._raw(
                ((d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds) * 1000, False, None
            )
        return Moment._raw(cls._parts(x)[0], False, None)

    @classmethod
    def from_iso(cls, s: str) -> Moment:
        """ISO text without an offset; with an offset or 'Z', TypeError."""
        return cls.moment(datetime.fromisoformat(s))

    @classmethod
    def from_str(cls, s: str, fmt: str) -> Moment:
        """strptime; the format must not yield a zone."""
        return cls.moment(datetime.strptime(s, fmt))

    @classmethod
    def localize(cls, x, zone) -> Moment:
        """The wall time read in `zone`: the one crossing into a moment, and the zone is always
        named by the caller (BR-MMN-13, BR-MMN-14)."""
        m = cls.moment(x)
        z = MomentHelper.zone(zone) if isinstance(zone, str) else zone
        # The offset comes from datetime (µs); the nanoseconds stay those of the Moment.
        offset = cls._shown(lambda: cls.to_datetime(m).replace(tzinfo=z)).utcoffset()
        return Moment._raw(m.ns - cls._off_ns(offset), True, cls.key(zone))

    # ================= output =================
    @classmethod
    def to_datetime(cls, x) -> datetime:
        t = type(x)
        if t is Moment:
            if x.aware:
                raise cls._wrong()
            ns = x.ns
        elif t is int:
            ns = x
        elif isinstance(x, datetime):
            if x.tzinfo is not None:
                raise cls._wrong()
            return x
        else:
            ns = cls._parts(x)[0]
        return cls._shown(lambda: cls._E_NA + timedelta(microseconds=ns // 1000))

    @classmethod
    def to_str(cls, x, fmt: str = None) -> str:
        dt = cls.to_datetime(x)
        return str(dt) if fmt is None else dt.strftime(fmt)

    @classmethod
    def to_iso(cls, x, timespec: str = "auto") -> str:
        return cls.to_datetime(x).isoformat(timespec=timespec)

    @classmethod
    def to_date(cls, x) -> date:
        return cls.to_datetime(x).date()

    @classmethod
    def to_time(cls, x) -> time:
        return cls.to_datetime(x).time()

    @classmethod
    def to_struct(cls, x) -> struct_time:
        return cls.to_datetime(x).timetuple()
