# Module name: helpers/moment/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations

__all__ = ["Moment", "MomentRangeError"]

from datetime import timedelta
from zoneinfo import ZoneInfo


class MomentRangeError(OverflowError, ValueError):
    """A value outside the domain of Moment (years 1-9999) or of its target form (BR-MMN-05..07)."""


class _MomentSlots:
    """Storage only: three slots, the fastest attribute access.

    Moment sets them directly, past its own __setattr__, so it stays immutable.
    Without this base construction is ~25% slower (579 -> 721 ns).
    """

    __slots__ = ("ns", "aware", "tz")


class Moment(_MomentSlots):
    """Nanoseconds since 1970-01-01.

    aware=True : a UTC moment; `tz` is the IANA zone name for display (not compared).
    aware=False: a wall time without a zone (`tz` must be None).
    The domain is the years of datetime, 1-9999, checked where every Moment comes into being.
    """

    __slots__ = ()

    #: 0001-01-01T00:00:00 and 9999-12-31T23:59:59.999999999, both kinds (BR-MMN-05).
    MIN_NS = -62_135_596_800 * 1_000_000_000
    MAX_NS = 253_402_300_800 * 1_000_000_000 - 1

    def __new__(
        cls,
        ns,
        aware,
        tz=None,
        *,
        _new=object.__new__,
        _sn=_MomentSlots.ns.__set__,
        _sa=_MomentSlots.aware.__set__,
        _st=_MomentSlots.tz.__set__,
    ):
        if tz is not None:
            tz = Moment._key(tz)
            if tz and not aware:
                raise ValueError("a naive Moment cannot carry a zone")
        ns = int(ns)
        if not cls.MIN_NS <= ns <= cls.MAX_NS:
            raise MomentRangeError(f"{ns} ns is outside years 1-9999")
        o = _new(cls)
        _sn(o, ns)
        _sa(o, bool(aware))
        _st(o, tz)
        return o

    @staticmethod
    def _key(tz):
        """tzinfo | str | None -> IANA name or None (fixed offsets have no name).

        An unknown zone name raises ZoneInfoNotFoundError. The one source of truth;
        MomentHelper.key is an alias.
        """
        if tz is None:
            return None
        if isinstance(tz, str):
            ZoneInfo(tz)  # validates (ZoneInfo keeps its own cache)
            return tz
        return getattr(tz, "key", None)

    @classmethod
    def _raw(
        cls,
        ns,
        aware,
        tz,
        _new=object.__new__,
        _sn=_MomentSlots.ns.__set__,
        _sa=_MomentSlots.aware.__set__,
        _st=_MomentSlots.tz.__set__,
    ):
        """Fast path for typed values (no int()/bool()/key()); the domain is still checked."""
        if not cls.MIN_NS <= ns <= cls.MAX_NS:
            raise MomentRangeError(f"{ns} ns is outside years 1-9999")
        o = _new(cls)
        _sn(o, ns)
        _sa(o, aware)
        _st(o, tz)
        return o

    # ---- immutability and copying ----
    def __setattr__(self, k, v):
        raise AttributeError("Moment is immutable")

    def __delattr__(self, k):
        raise AttributeError("Moment is immutable")

    def __reduce__(self):
        return (type(self), (self.ns, self.aware, self.tz))

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    # ---- comparison (tz is not compared; naive and aware never mix) ----
    def __eq__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        return self.aware == o.aware and self.ns == o.ns

    def __hash__(self):
        return hash((self.ns, self.aware))

    def __lt__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("cannot compare a naive and an aware Moment")
        return self.ns < o.ns

    def __le__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("cannot compare a naive and an aware Moment")
        return self.ns <= o.ns

    def __gt__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("cannot compare a naive and an aware Moment")
        return self.ns > o.ns

    def __ge__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("cannot compare a naive and an aware Moment")
        return self.ns >= o.ns

    # ---- arithmetic ----
    def __add__(self, d):
        if not isinstance(d, timedelta):
            return NotImplemented
        return self._raw(
            self.ns + ((d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds) * 1000,
            self.aware,
            self.tz,
        )

    __radd__ = __add__

    def __sub__(self, o):
        if isinstance(o, timedelta):
            return self._raw(
                self.ns - ((o.days * 86400 + o.seconds) * 1_000_000 + o.microseconds) * 1000,
                self.aware,
                self.tz,
            )
        if isinstance(o, Moment):
            if self.aware != o.aware:
                raise TypeError("cannot subtract a naive and an aware Moment")
            return timedelta(microseconds=(self.ns - o.ns) // 1000)
        return NotImplemented

    # ---- display ----
    # The helper is imported at call time: Moment does not depend on it at module level
    # (no import cycle), and str/repr are not a hot path.
    def __str__(self):
        from .helper import MomentHelper

        return MomentHelper.of(self).to_str(self)

    def __format__(self, spec):
        from .helper import MomentHelper

        return MomentHelper.of(self).to_str(self, spec or None)

    def __repr__(self):
        from .helper import MomentHelper

        return f"Moment({MomentHelper.of(self).to_iso(self)!r})"
