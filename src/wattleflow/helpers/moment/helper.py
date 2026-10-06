# Module name: helpers/moment/moment.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from functools import lru_cache
from struct import Struct
from time import struct_time, time_ns
from zoneinfo import ZoneInfo
from .moment import Moment


"""MomentHelper (baza) + MomentAwareHelper + MomentNaiveHelper.

int: UTC ns (Aware) ili ns zidnog vremena (Naive). Pogrešna vrsta baca TypeError.
Pretvorba je jednosmjerna: MomentAwareHelper.strip (svjesno → naivno);
obrnuto ne postoji jer se zona ne smije izmisliti (DST fold/gap).
Svjesni Moment gradi se iz datetimea s tzinfo.
Sve su classmethod; podklasa ih može nadjačati.
"""


class MomentHelper:
    """Zajedničko za obje vrste: zone, serijalizacija (nosi oznaku vrste), odabir helpera.
    AWARE: True = svjesno, False = naivno, None = bilo koja vrsta (goli int tada nije dopušten)."""

    AWARE = None
    _E_AW = datetime(1970, 1, 1, tzinfo=timezone.utc)
    _E_NA = datetime(1970, 1, 1)
    _G = 1_000_000_000
    _PK = Struct(">qIB")  # sekunde int64, nanosekunde uint32, aware uint8 (13 B)

    # ---------- zone ----------
    @staticmethod
    @lru_cache(maxsize=64)
    def zone(name: str) -> ZoneInfo:
        return ZoneInfo(name)

    key = staticmethod(Moment._key)  # alias: jedan izvor istine je u Moment-u

    # ---------- odabir helpera ----------
    @classmethod
    def of(cls, x):
        """MomentAwareHelper ili MomentNaiveHelper prema vrsti Moment-a / datetime-a."""
        if isinstance(x, Moment):
            aw = x.aware
        elif isinstance(x, datetime):
            aw = x.tzinfo is not None
        else:
            raise TypeError(f"vrsta se ne može odrediti iz: {type(x).__name__}")
        return MomentAwareHelper if aw else MomentNaiveHelper

    # ---------- unutarnje ----------
    @classmethod
    def _wrong(cls):
        return TypeError(
            "očekivan svjestan ulaz (Moment/datetime sa zonom)"
            if cls.AWARE
            else "očekivan naivan ulaz (Moment/datetime bez zone)"
        )

    @classmethod
    def _parts(cls, x):
        """x -> (ns, aware, tz); vrsta mora odgovarati cls.AWARE."""
        a = cls.AWARE
        if type(x) is int or (not isinstance(x, (Moment, datetime)) and hasattr(x, "__index__")):
            if a is None:
                raise TypeError(
                    "goli int nema vrstu; koristi MomentAwareHelper ili MomentNaiveHelper"
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
            raise TypeError(f"nepodržan tip: {type(x).__name__}")
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

    # ---------- serijalizacija (nosi oznaku vrste) ----------
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


class MomentAwareHelper(MomentHelper):
    """Svjesno vrijeme: UTC trenutak (+ zona za prikaz). Goli int = ns UTC."""

    AWARE = True
    _JD_UNIX = 2440587.5  # JD trenutka 1970-01-01T00:00:00 UTC

    # ================= ulaz -> Moment =================
    @classmethod
    def moment(cls, x, tz=None) -> Moment:
        """Svjesni Moment iz Moment | datetime (sa zonom) | int (ns UTC). tz mijenja zonu prikaza."""
        if tz is None and type(x) is datetime:  # najčešći put
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
        """ISO niz mora imati pomak ili 'Z'; bez toga TypeError (zona se ne izmišlja)."""
        return cls.moment(datetime.fromisoformat(s.replace("Z", "+00:00")))

    @classmethod
    def from_str(cls, s: str, fmt: str) -> Moment:
        """strptime; format mora davati zonu (npr. %z), inače TypeError."""
        return cls.moment(datetime.strptime(s, fmt))

    @classmethod
    def from_unix(cls, sec: float, tz=None) -> Moment:
        return Moment._raw(round(sec * cls._G), True, cls.key(tz))

    @classmethod
    def from_unix_ns(cls, ns: int, tz=None) -> Moment:
        return Moment._raw(int(ns), True, cls.key(tz))

    @classmethod
    def now(cls, tz=None) -> Moment:
        return Moment._raw(time_ns(), True, cls.key(tz))

    # ================= izlaz =================
    @classmethod
    def to_datetime(cls, x, tz=None) -> datetime:
        """U zoni tz, inače spremljenoj, inače UTC."""
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
            return x if tz is None else x.astimezone(cls.zone(tz) if isinstance(tz, str) else tz)
        else:
            ns, _, tzs = cls._parts(x)
            z = tz if tz is not None else tzs
        dt = cls._E_AW + timedelta(microseconds=ns // 1000)
        if z is None:
            return dt
        return dt.astimezone(cls.zone(z) if isinstance(z, str) else z)

    @classmethod
    def to_utc(cls, x) -> datetime:
        return cls.to_datetime(x, timezone.utc)

    @classmethod
    def to_local(cls, x) -> datetime:
        """datetime u zoni operacijskog sustava."""
        return cls.to_datetime(x, timezone.utc).astimezone()

    @classmethod
    def to_str(cls, x, fmt: str = None, tz=None) -> str:
        """Bez fmt: oblik kao str(datetime). S fmt: strftime."""
        dt = cls.to_datetime(x, tz)
        return str(dt) if fmt is None else dt.strftime(fmt)

    @classmethod
    def to_iso(cls, x, tz=None, timespec: str = "auto", z: bool = False) -> str:
        """isoformat; z=True zamjenjuje '+00:00' sa 'Z'."""
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
        """Julijanski datum kao float64 (rezolucija ~40 µs; za točnost koristi ns)."""
        return cls.to_unix_ns(x) / (86400 * cls._G) + cls._JD_UNIX

    @classmethod
    def to_mjd(cls, x) -> float:
        """Modificirani JD kao float64 (rezolucija ~0.6 µs)."""
        return cls.to_jd(x) - 2400000.5

    # ================= zona i jednosmjerna pretvorba =================
    @classmethod
    def with_tz(cls, x, tz):
        """Isti trenutak, druga zona za prikaz. Moment -> Moment, datetime -> datetime."""
        if isinstance(x, datetime):
            if x.tzinfo is None:
                raise cls._wrong()
            return cls.to_datetime(x, tz)
        if not isinstance(x, Moment):
            raise TypeError("int nema zonu; koristi Moment ili datetime")
        if not x.aware:
            raise cls._wrong()
        return x._raw(x.ns, True, cls.key(tz))

    @classmethod
    def strip(cls, x, tz=None):
        """Svjesno -> NAIVNO (jednosmjerno, gubi zonu): zidno vrijeme u zoni tz (zadano spremljena zona,
        inače UTC). Moment -> Moment, datetime -> datetime, int (ns UTC) -> int (ns zidnog vremena)."""
        if isinstance(x, datetime):
            if x.tzinfo is None:
                raise cls._wrong()
            return (x if tz is None else cls.to_datetime(x, tz)).replace(tzinfo=None)
        ns, _, tzs = cls._parts(x)
        z = tz if tz is not None else tzs
        out = ns
        if z is not None:
            inst = cls._E_AW + timedelta(microseconds=ns // 1000)
            out = ns + cls._off_ns(
                inst.astimezone(cls.zone(z) if isinstance(z, str) else z).utcoffset()
            )
        return x._raw(out, False, None) if isinstance(x, Moment) else out


class MomentNaiveHelper(MomentHelper):
    """Naivno vrijeme: zidno vrijeme bez zone. Goli int = ns zidnog vremena.
    Nema unix/http/jd/zona operacija i NEMA pretvorbe u svjesno (zona se ne izmišlja)."""

    AWARE = False

    # ================= ulaz -> Moment =================
    @classmethod
    def moment(cls, x) -> Moment:
        """Naivni Moment iz Moment | datetime (bez zone) | int (ns zidnog vremena)."""
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
        """ISO niz bez pomaka; s pomakom ili 'Z' TypeError."""
        return cls.moment(datetime.fromisoformat(s))

    @classmethod
    def from_str(cls, s: str, fmt: str) -> Moment:
        """strptime; format ne smije davati zonu."""
        return cls.moment(datetime.strptime(s, fmt))

    # ================= izlaz =================
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
        return cls._E_NA + timedelta(microseconds=ns // 1000)

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

    @classmethod
    def to_rfc2822(cls, x) -> str:
        """Bez zone: pomak je '-0000' (RFC 2822: zona nepoznata)."""
        return format_datetime(cls.to_datetime(x))


__all__ = ["MomentHelper", "MomentAwareHelper", "MomentNaiveHelper"]
