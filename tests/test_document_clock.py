# Module name: tests/test_document_clock.py
# Tests for the clock behind a document's audit keys (FRQ-DOC c.12): there is one route to the time,
# `MomentAwareHelper.now()`, and `Document` has no second one of its own.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_clock -v
import unittest
from unittest import mock

from wattleflow.concrete.document import Document, DummyReadDocument
from wattleflow.helpers.moment import Moment, MomentAwareHelper, MomentHelper

FIXED = Moment(1_767_323_045 * 10**9, True, "UTC")


class SingleRouteTest(unittest.TestCase):
    def test_document_has_no_clock_of_its_own(self):
        self.assertFalse(hasattr(Document, "utc_time_stamp"))

    def test_an_instance_has_no_clock_of_its_own_either(self):
        self.assertFalse(hasattr(DummyReadDocument(identifier="a"), "utc_time_stamp"))

    def test_now_is_an_aware_moment_in_the_workflow_zone(self):
        now = MomentAwareHelper.now()
        self.assertIsInstance(now, Moment)
        self.assertTrue(now.aware)
        self.assertEqual(now.tz, MomentHelper.workflow_zone())


class AuditKeysFollowTheClockTest(unittest.TestCase):
    def setUp(self):
        self.document = DummyReadDocument(identifier="a")

    def test_metadata_change_time_comes_from_now(self):
        with mock.patch.object(MomentAwareHelper, "now", return_value=FIXED):
            self.document.update_metadata("note", "x")
        self.assertEqual(self.document.metadata["last_change_time"], FIXED)

    def test_content_change_time_comes_from_now(self):
        with mock.patch.object(MomentAwareHelper, "now", return_value=FIXED):
            self.document.update_content({"notice": "y"})
        self.assertEqual(self.document.metadata["last_change_time"], FIXED)

    def test_creation_time_comes_from_now(self):
        with mock.patch.object(MomentAwareHelper, "now", return_value=FIXED):
            created = DummyReadDocument(identifier="b")
        self.assertEqual(created.metadata["created_at"], FIXED)


if __name__ == "__main__":
    unittest.main()
