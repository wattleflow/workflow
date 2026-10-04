# Module name: tests/test_document_clock.py
# Tests for the clock behind a document's audit keys (FRQ-DOC, DEF-DOC-03, DEF-DOC-09): there is one
# route to the time, `Now.utc()`, and `Document` has no second one of its own.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_clock -v
import unittest
from datetime import datetime, timezone
from unittest import mock

from wattleflow.concrete.document import Document, DummyReadDocument
from wattleflow.helpers.dtime import Now

FIXED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class SingleRouteTest(unittest.TestCase):
    def test_document_has_no_clock_of_its_own(self):
        self.assertFalse(hasattr(Document, "utc_time_stamp"))

    def test_an_instance_has_no_clock_of_its_own_either(self):
        self.assertFalse(hasattr(DummyReadDocument(identifier="a"), "utc_time_stamp"))

    def test_now_utc_is_a_timezone_aware_datetime(self):
        self.assertIsInstance(Now.utc(), datetime)
        self.assertIsNotNone(Now.utc().tzinfo)


class AuditKeysFollowTheClockTest(unittest.TestCase):
    def setUp(self):
        self.document = DummyReadDocument(identifier="a")

    def test_metadata_change_time_comes_from_now_utc(self):
        with mock.patch.object(Now, "utc", return_value=FIXED):
            self.document.update_metadata("note", "x")
        self.assertEqual(self.document.metadata["last_change_time"], FIXED)

    def test_content_change_time_comes_from_now_utc(self):
        with mock.patch.object(Now, "utc", return_value=FIXED):
            self.document.update_content({"notice": "y"})
        self.assertEqual(self.document.metadata["last_change_time"], FIXED)

    def test_creation_time_comes_from_now_utc(self):
        with mock.patch.object(Now, "utc", return_value=FIXED):
            created = DummyReadDocument(identifier="b")
        self.assertEqual(created.metadata["created_at"], FIXED)


if __name__ == "__main__":
    unittest.main()
