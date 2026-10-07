# Module name: tests/test_moment.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence
#
#   PYTHONPATH=src:../core/src python -m unittest tests.test_moment -v
"""Moment and its helpers: two kinds (aware, naive) that never mix, nanoseconds since the epoch,
and conversions that never invent a zone."""

import copy
import pickle
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wattleflow.helpers.moment import (
    Moment,
    MomentRangeError,
    MomentAwareHelper as A,
    MomentHelper,
    MomentNaiveHelper as N,
)

WALL = datetime(2026, 10, 6, 12, 0)
UTC_NOON = WALL.replace(tzinfo=timezone.utc)
SYDNEY_NOON = WALL.replace(tzinfo=ZoneInfo("Australia/Sydney"))


class TestMoment(unittest.TestCase):
    def test_is_immutable_and_copies_to_itself(self):
        m = Moment(5, True, "UTC")
        with self.assertRaises(AttributeError):
            m.ns = 6
        with self.assertRaises(AttributeError):
            del m.ns
        self.assertIs(copy.copy(m), m)
        self.assertIs(copy.deepcopy(m), m)
        self.assertEqual(pickle.loads(pickle.dumps(m)), m)
        self.assertEqual(pickle.loads(pickle.dumps(m)).tz, "UTC")

    def test_a_naive_moment_carries_no_zone(self):
        with self.assertRaises(ValueError):
            Moment(0, False, "UTC")
        with self.assertRaises(ZoneInfoNotFoundError):
            Moment(0, True, "Not/AZone")

    def test_the_zone_is_for_display_only(self):
        self.assertEqual(Moment(7, True, "UTC"), Moment(7, True, "Australia/Sydney"))
        self.assertEqual(hash(Moment(7, True, "UTC")), hash(Moment(7, True)))

    def test_naive_and_aware_never_mix(self):
        aware, naive = Moment(1, True), Moment(1, False)
        self.assertNotEqual(aware, naive)
        for op in (lambda: aware < naive, lambda: aware <= naive, lambda: aware > naive,
                   lambda: aware >= naive, lambda: aware - naive):  # fmt: skip
            with self.assertRaises(TypeError):
                op()

    def test_order_and_arithmetic(self):
        a, b = Moment(1_000, True), Moment(3_000, True)
        self.assertTrue(a < b <= b and b > a >= a)
        self.assertEqual(a + timedelta(microseconds=2), b)
        self.assertEqual(b - timedelta(microseconds=2), a)
        self.assertEqual(b - a, timedelta(microseconds=2))
        self.assertEqual(timedelta(seconds=1) + a, Moment(1_000_001_000, True))


class TestAware(unittest.TestCase):
    def test_from_and_to_datetime(self):
        m = A.moment(SYDNEY_NOON)
        self.assertEqual(m.tz, "Australia/Sydney")
        self.assertEqual(A.to_datetime(m), SYDNEY_NOON)
        self.assertEqual(A.to_datetime(m, "UTC"), datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc))
        with self.assertRaises(TypeError):
            A.moment(WALL)  # no zone is invented

    def test_iso_needs_an_offset(self):
        self.assertEqual(A.from_iso("2026-10-06T12:00:00Z"), A.moment(UTC_NOON))
        self.assertEqual(A.to_iso(A.moment(UTC_NOON), z=True), "2026-10-06T12:00:00Z")
        self.assertEqual(A.to_iso(A.moment(SYDNEY_NOON)), "2026-10-06T12:00:00+11:00")
        with self.assertRaises(TypeError):
            A.from_iso("2026-10-06T12:00:00")

    def test_epoch_numbers(self):
        m = A.moment(UTC_NOON)
        self.assertEqual(A.to_unix_ns(m), A.to_unix_ns(A.from_unix_ns(m.ns)))
        self.assertEqual(A.to_unix(Moment(1_500_000_000, True)), 1.5)
        self.assertEqual(A.to_jd(Moment(0, True)), 2440587.5)
        self.assertEqual(A.to_mjd(Moment(0, True)), 40587.0)

    def test_display_zone_and_strip(self):
        m = A.moment(UTC_NOON)
        self.assertEqual(A.with_tz(m, "Australia/Sydney"), m)
        self.assertEqual(A.with_tz(m, "Australia/Sydney").tz, "Australia/Sydney")
        wall = A.strip(m, "Australia/Sydney")  # 12:00 UTC is 23:00 in Sydney (AEDT, +11)
        self.assertFalse(wall.aware)
        self.assertEqual(N.to_datetime(wall), datetime(2026, 10, 6, 23, 0))
        winter = A.strip(
            A.moment(datetime(2026, 7, 1, 12, tzinfo=timezone.utc)), "Australia/Sydney"
        )
        self.assertEqual(N.to_datetime(winter), datetime(2026, 7, 1, 22, 0))  # AEST, +10

    def test_rfc_5322_and_http(self):
        # RFC 5322 section 3.3: "+0000" SHOULD be used for Universal Time.
        self.assertEqual(A.to_rfc2822(A.moment(UTC_NOON)), "Tue, 06 Oct 2026 12:00:00 +0000")
        self.assertEqual(A.to_rfc2822(A.moment(SYDNEY_NOON)), "Tue, 06 Oct 2026 12:00:00 +1100")
        self.assertEqual(A.to_http(A.moment(UTC_NOON)), "Tue, 06 Oct 2026 12:00:00 GMT")

    def test_a_naive_input_is_refused(self):
        for call in (A.to_datetime, A.to_unix_ns, A.strip):
            with self.subTest(call=call.__name__), self.assertRaises(TypeError):
                call(Moment(0, False))


class TestNaive(unittest.TestCase):
    def test_from_and_to_datetime(self):
        m = N.moment(WALL)
        self.assertEqual(N.to_datetime(m), WALL)
        self.assertEqual(N.to_iso(m), "2026-10-06T12:00:00")
        with self.assertRaises(TypeError):
            N.moment(UTC_NOON)
        with self.assertRaises(TypeError):
            N.from_iso("2026-10-06T12:00:00+00:00")

    def test_no_way_into_the_aware_kind(self):
        for name in ("to_unix_ns", "to_http", "to_jd", "with_tz", "strip"):
            self.assertFalse(hasattr(N, name), name)

    def test_a_wall_time_has_no_rfc_5322_form(self):  # FRQ-MOM c.11
        # RFC 5322 section 3.3: "-0000" means UT, and a wall time is not UT.
        self.assertFalse(hasattr(N, "to_rfc2822"))


class TestCommon(unittest.TestCase):
    def test_the_helper_follows_the_kind(self):
        self.assertIs(MomentHelper.of(Moment(0, True)), A)
        self.assertIs(MomentHelper.of(WALL), N)
        with self.assertRaises(TypeError):
            MomentHelper.of(0)
        with self.assertRaises(TypeError):
            MomentHelper.to_dict(0)  # a bare int has no kind

    def test_serialisation_carries_the_kind_and_zone(self):
        aware = A.moment(SYDNEY_NOON) + timedelta(microseconds=1)
        naive = N.moment(WALL)
        for helper, m in ((A, aware), (N, naive)):
            with self.subTest(aware=m.aware):
                back = helper.from_bytes(helper.to_bytes(m))
                self.assertEqual((back, back.tz), (m, m.tz))
                self.assertEqual(helper.from_dict(helper.to_dict(m)), m)
        self.assertEqual(len(MomentHelper.to_bytes(naive)), 13)
        with self.assertRaises(TypeError):
            N.from_bytes(A.to_bytes(aware))  # the kind travels and is checked

    def test_nanoseconds_beyond_microseconds(self):
        m = Moment(1_000_000_123, True)
        self.assertEqual(MomentHelper.from_bytes(MomentHelper.to_bytes(m)).ns, 1_000_000_123)
        # datetime holds microseconds: the last three digits do not survive it (floor).
        self.assertEqual(A.moment(A.to_datetime(m)).ns, 1_000_000_000)

    def test_text_forms(self):
        self.assertEqual(repr(A.moment(UTC_NOON)), "Moment('2026-10-06T12:00:00+00:00')")
        self.assertEqual(str(N.moment(WALL)), "2026-10-06 12:00:00")
        self.assertEqual(f"{A.moment(UTC_NOON):%Y-%m-%d}", "2026-10-06")



class TestDomain(unittest.TestCase):
    """FRQ-MOM c.7-9: years 1-9999 on creation, named errors at zone edges, one bridge to int64."""

    def test_the_bounds_are_the_years_of_datetime(self):
        self.assertEqual(Moment.MIN_NS, -62_135_596_800 * 10**9)
        self.assertEqual(Moment.MAX_NS, 253_402_300_800 * 10**9 - 1)
        self.assertEqual(A.to_iso(Moment(Moment.MIN_NS, True)), "0001-01-01T00:00:00+00:00")
        self.assertEqual(A.to_iso(Moment(Moment.MAX_NS, True)), "9999-12-31T23:59:59.999999+00:00")
        self.assertEqual(N.to_iso(Moment(Moment.MAX_NS, False)), "9999-12-31T23:59:59.999999")
        self.assertTrue(issubclass(MomentRangeError, OverflowError))
        self.assertTrue(issubclass(MomentRangeError, ValueError))

    def test_nothing_outside_the_domain_comes_into_being(self):
        below, above = Moment.MIN_NS - 1, Moment.MAX_NS + 1
        day = timedelta(days=1)
        attempts = {
            "constructor": lambda: Moment(above, True),
            "constructor below": lambda: Moment(below, False),
            "_raw": lambda: Moment._raw(above, True, None),
            "addition": lambda: Moment(Moment.MAX_NS, True) + day,
            "subtraction": lambda: Moment(Moment.MIN_NS, True) - day,
            "from_dict": lambda: A.from_dict({"sec": above // 10**9, "nsec": 0, "aware": True}),
            "from_bytes": lambda: A.from_bytes(MomentHelper._PK.pack(above // 10**9 + 1, 0, True)),
            "from_unix_ns": lambda: A.from_unix_ns(above),
            "from_unix": lambda: A.from_unix(above / 10**9 + 1),
            "from_unix(inf)": lambda: A.from_unix(float("inf")),
            "from_unix(nan)": lambda: A.from_unix(float("nan")),
            "naive moment(int)": lambda: N.moment(above),
        }
        for name, attempt in attempts.items():
            with self.subTest(name), self.assertRaises(MomentRangeError):
                attempt()

    def test_a_zone_that_moves_past_the_edge_is_a_range_error(self):
        first, last = Moment(Moment.MIN_NS, True), Moment(Moment.MAX_NS, True)
        attempts = {
            "to_iso New York": lambda: A.to_iso(first, "America/New_York"),
            "to_datetime Sydney": lambda: A.to_datetime(last, "Australia/Sydney"),
            "strip Sydney": lambda: A.strip(last, "Australia/Sydney"),
            "to_iso int Sydney": lambda: A.to_iso(Moment.MAX_NS, "Australia/Sydney"),
        }
        for name, attempt in attempts.items():
            with self.subTest(name), self.assertRaises(MomentRangeError):
                attempt()

    def test_one_bridge_to_int64_columns(self):
        m = A.moment(UTC_NOON)
        self.assertEqual(MomentHelper.to_int64_ns(m), m.ns)
        self.assertEqual(N.to_int64_ns(N.moment(WALL)), N.moment(WALL).ns)
        self.assertEqual(A.to_int64_ns(2**63 - 1), 2**63 - 1)
        for value in (-(2**63), 2**63, Moment(Moment.MAX_NS, True)):
            with self.subTest(value=value), self.assertRaises(MomentRangeError):
                A.to_int64_ns(value)
        with self.assertRaises(TypeError):
            MomentHelper.to_int64_ns(0)  # a bare int has no kind


if __name__ == "__main__":
    unittest.main()
