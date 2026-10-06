# Module name: tests/test_datetime_helpers.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence
#
#   PYTHONPATH=src:../core/src python -m unittest tests.test_datetime_helpers -v
"""NFRQ-DEF-04 (ZonedDateTimeHelper, the norm) and NFRQ-DEF-05 (DateTimeHelper, no zone): two models,
never mixed, and DateTimeKind, which hands a value to the helper of its model."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from wattleflow.helpers.dtime import CreatedWithin, DateTimeHelper, DateTimeKind, Now, ZonedDateTimeHelper


SYDNEY = datetime(2026, 10, 6, 12, 35, 2, 123456, tzinfo=timezone(timedelta(hours=11)))
NAIVE = SYDNEY.replace(tzinfo=None)
UTC_TEXT = "2026-10-06T01:35:02.123456Z"


def utc_defaults():
    return mock.patch.multiple(
        ZonedDateTimeHelper, DEFAULT_ZONE="UTC", DEFAULT_TIMESPEC="microseconds", DEFAULT_UTC_MARKER="Z"
    )


class TestZonedWrite(unittest.TestCase):
    def test_default_form_is_utc_microseconds_z(self):  # DEF-04 c.3
        with utc_defaults():
            self.assertEqual(ZonedDateTimeHelper.write(SYDNEY), UTC_TEXT)
            self.assertEqual(ZonedDateTimeHelper.write(SYDNEY.replace(microsecond=0)), "2026-10-06T01:35:02.000000Z")

    def test_width_is_fixed(self):  # DEF-04 c.7
        with utc_defaults():
            for moment in (datetime(1000, 1, 1, tzinfo=timezone.utc), SYDNEY,
                           datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)):
                self.assertEqual(len(ZonedDateTimeHelper.write(moment)), 27, moment)

    def test_a_datetime_without_a_zone_is_refused(self):  # DEF-04 c.5
        for call in (ZonedDateTimeHelper.write, ZonedDateTimeHelper.convert):
            with self.assertRaises(ValueError) as caught:
                call(NAIVE)
            self.assertIn("DateTimeHelper", str(caught.exception))

    def test_defaults_are_the_installation_settings(self):
        with mock.patch.multiple(ZonedDateTimeHelper, DEFAULT_ZONE="Australia/Sydney", DEFAULT_TIMESPEC="seconds",
                                 DEFAULT_UTC_MARKER=None):
            self.assertEqual(ZonedDateTimeHelper.write(SYDNEY.astimezone(timezone.utc)), "2026-10-06T12:35:02+11:00")
        self.assertEqual(ZonedDateTimeHelper.ENV_ZONE, "WATTLEFLOW_TIME_ZONE")

    def test_each_argument_overrides_one_default(self):  # DEF-04 c.4
        with utc_defaults():
            self.assertEqual(ZonedDateTimeHelper.convert(SYDNEY, timespec="milliseconds"), "2026-10-06T01:35:02.123Z")
            self.assertEqual(ZonedDateTimeHelper.convert(SYDNEY, utc_marker=None), "2026-10-06T01:35:02.123456+00:00")
            self.assertEqual(ZonedDateTimeHelper.convert(SYDNEY, zone="Europe/Zagreb", timespec="seconds"),
                             "2026-10-06T03:35:02+02:00")
            self.assertEqual(ZonedDateTimeHelper.convert(SYDNEY, zone=SYDNEY.tzinfo), "2026-10-06T12:35:02.123456+11:00")


class TestZonedRead(unittest.TestCase):
    def test_round_trip_is_a_fixed_point(self):  # DEF-04 c.6
        with utc_defaults():
            for moment in (datetime(1970, 1, 1, tzinfo=timezone.utc), SYDNEY,
                           datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc),
                           datetime(2026, 12, 31, 23, 59, 59, 999999, tzinfo=timezone(timedelta(hours=-5)))):
                self.assertEqual(ZonedDateTimeHelper.read(ZonedDateTimeHelper.write(moment)), moment)
            for text in (UTC_TEXT, "2026-10-06T01:35:02.123456+00:00", "2026-10-06T12:35:02.123456+11:00"):
                self.assertEqual(ZonedDateTimeHelper.write(ZonedDateTimeHelper.read(text)), UTC_TEXT)

    def test_text_without_an_offset_is_refused(self):  # DEF-04 c.5
        with self.assertRaises(ValueError) as caught:
            ZonedDateTimeHelper.read("2026-10-06T01:35:02")
        self.assertIn("DateTimeHelper", str(caught.exception))
        with self.assertRaises(ValueError):
            ZonedDateTimeHelper.read("yesterday")


class TestDateTimeHelper(unittest.TestCase):
    def test_writes_and_reads_a_datetime_without_a_zone(self):  # DEF-05 c.4
        self.assertEqual(DateTimeHelper.write(NAIVE), "2026-10-06T12:35:02.123456")
        self.assertEqual(DateTimeHelper.write(NAIVE, timespec="seconds"), "2026-10-06T12:35:02")
        self.assertEqual(DateTimeHelper.read(DateTimeHelper.write(NAIVE)), NAIVE)
        self.assertEqual(DateTimeHelper.read("2026-10-06"), datetime(2026, 10, 6))

    def test_a_zoned_datetime_is_refused(self):  # DEF-05 c.2
        with self.assertRaises(ValueError) as caught:
            DateTimeHelper.write(SYDNEY)
        self.assertIn("ZonedDateTimeHelper", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            DateTimeHelper.read(UTC_TEXT)
        self.assertIn("ZonedDateTimeHelper", str(caught.exception))

    def test_zoned_is_the_one_crossing_and_needs_a_zone(self):  # DEF-05 c.3
        self.assertEqual(DateTimeHelper.zoned(NAIVE, zone="UTC"), NAIVE.replace(tzinfo=timezone.utc))
        self.assertEqual(DateTimeHelper.zoned(NAIVE, zone="Australia/Sydney").utcoffset(), timedelta(hours=11))
        with self.assertRaises(TypeError):
            DateTimeHelper.zoned(NAIVE)  # the zone is not optional
        with self.assertRaises(ValueError):
            DateTimeHelper.zoned(SYDNEY, zone="UTC")


class TestDateTimeKind(unittest.TestCase):
    def test_routing_keeps_the_model(self):  # DEF-05 c.5
        self.assertEqual(DateTimeKind.text(SYDNEY), "2026-10-06T12:35:02.123456+11:00")
        self.assertEqual(DateTimeKind.text(NAIVE), "2026-10-06T12:35:02.123456")
        self.assertEqual(DateTimeKind.parse(UTC_TEXT), SYDNEY)
        self.assertIsNone(DateTimeKind.parse(" 2026-10-06T12:35:02 ").tzinfo)
        with self.assertRaises(ValueError):
            DateTimeKind.parse("06/10/2026")


class TestUsers(unittest.TestCase):
    def test_now_iso_is_zoned_utc(self):
        with utc_defaults():
            text = Now.iso()
        self.assertTrue(text.endswith("Z"), text)
        self.assertLess(abs((ZonedDateTimeHelper.read(text) - Now.utc()).total_seconds()), 5)

    def test_created_window_is_zoned_before_it_is_compared(self):
        window = CreatedWithin("2026-10-01", "2026-10-06T12:00:00+11:00")
        self.assertIsNotNone(window.start.tzinfo)
        self.assertIsNotNone(window.end.tzinfo)
        self.assertLess(window.start, window.end)  # no TypeError between the two models


if __name__ == "__main__":
    unittest.main()
