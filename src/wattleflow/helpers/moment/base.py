# Module name: helpers/moment/moment.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from datetime import timedelta
from zoneinfo import ZoneInfo


class _MomentSlots:
    """Samo pohrana: tri slota (najbrži pristup atributima).
    Najbrži pristup atributima - Moment ih tako postavlja izravno mimo __setattr__ (ostaje nepromjenjiv).
    Bez ove baze stvaranje je ~25% sporije (579 -> 721 ns).
    """

    __slots__ = ("ns", "aware", "tz")


class Moment(_MomentSlots):
    """ns od 1970-01-01.
    aware=True : UTC trenutak; `tz` je IANA ime zone za prikaz (ne utječe na usporedbu).
    aware=False: zidno vrijeme bez zone (tz mora biti None)."""

    __slots__ = ()

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
                raise ValueError("naivan Moment ne može imati zonu")
        o = _new(cls)
        _sn(o, int(ns))
        _sa(o, bool(aware))
        _st(o, tz)
        return o

    @staticmethod
    def _key(tz):
        """tzinfo | str | None -> IANA ime ili None (fiksni pomaci nemaju ime).
        Nepoznato ime zone baca ZoneInfoNotFoundError. Jedini izvor istine; MomentHelper.key je alias."""
        if tz is None:
            return None
        if isinstance(tz, str):
            ZoneInfo(tz)  # provjera (ZoneInfo ima vlastitu predmemoriju)
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
        """Brzi put za već provjerene vrijednosti (bez int()/bool()/key())."""
        o = _new(cls)
        _sn(o, ns)
        _sa(o, aware)
        _st(o, tz)
        return o

    # ---- nepromjenjivost i kopiranje ----
    def __setattr__(self, k, v):
        raise AttributeError("Moment je nepromjenjiv")

    def __delattr__(self, k):
        raise AttributeError("Moment je nepromjenjiv")

    def __reduce__(self):
        return (type(self), (self.ns, self.aware, self.tz))

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    # ---- usporedba (tz se ne uspoređuje; naivno i svjesno se ne miješaju) ----
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
            raise TypeError("ne mogu usporediti naivno i svjesno")
        return self.ns < o.ns

    def __le__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("ne mogu usporediti naivno i svjesno")
        return self.ns <= o.ns

    def __gt__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("ne mogu usporediti naivno i svjesno")
        return self.ns > o.ns

    def __ge__(self, o):
        if not isinstance(o, Moment):
            return NotImplemented
        if self.aware != o.aware:
            raise TypeError("ne mogu usporediti naivno i svjesno")
        return self.ns >= o.ns

    # ---- aritmetika ----
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
                raise TypeError("ne mogu usporediti naivno i svjesno")
            return timedelta(microseconds=(self.ns - o.ns) // 1000)
        return NotImplemented

    # ---- prikaz ----
    # Prikaz uvozi helper u trenutku poziva: Moment tako ne ovisi o helperu na razini modula
    # (nema kružnog uvoza), a str/repr nisu vrući put.
    def __str__(self):
        from .moment_helper import MomentHelper

        return MomentHelper.of(self).to_str(self)

    def __format__(self, spec):
        from .moment_helper import MomentHelper

        return MomentHelper.of(self).to_str(self, spec or None)

    def __repr__(self):
        from .moment_helper import MomentHelper

        return f"Moment({MomentHelper.of(self).to_iso(self)!r})"


__all__ = ["Moment"]
