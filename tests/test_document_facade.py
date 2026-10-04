# Module name: tests/test_document_facade.py
# Tests for DocumentAdapter and DocumentFacade construction (FRQ-DOC, DEF-DOC-05): both refuse a
# non-IAdaptee before any base initialisation, so a refused object leaves nothing half-built.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_facade -v
import unittest
from unittest import mock

from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.document import DocumentAdapter, DocumentFacade, DummyReadDocument


class PlainFacade(DocumentFacade):
    pass


class RefusalOrderTest(unittest.TestCase):
    def refused_with_base_init_count(self, build) -> tuple[bool, int]:
        with mock.patch.object(Wattleflow, "__init__", return_value=None) as base_init:
            try:
                build()
            except TypeError:
                return True, base_init.call_count
        return False, base_init.call_count

    def test_adapter_refuses_before_base_initialisation(self):
        refused, calls = self.refused_with_base_init_count(lambda: DocumentAdapter(object()))
        self.assertTrue(refused)
        self.assertEqual(calls, 0)

    def test_facade_refuses_before_base_initialisation(self):
        refused, calls = self.refused_with_base_init_count(lambda: PlainFacade(object()))
        self.assertTrue(refused)
        self.assertEqual(calls, 0)

    def test_facade_refuses_none(self):
        with self.assertRaises(TypeError):
            PlainFacade(None)


class AcceptedAdapteeTest(unittest.TestCase):
    def setUp(self):
        self.document = DummyReadDocument(identifier="a")

    def test_adapter_wraps_and_returns_the_adaptee(self):
        self.assertIs(DocumentAdapter(self.document).request(), self.document)

    def test_facade_returns_the_adaptee(self):
        self.assertIs(PlainFacade(self.document).request(), self.document)

    def test_facade_delegates_attributes_to_the_adaptee(self):
        self.assertEqual(PlainFacade(self.document).identifier, self.document.identifier)

    def test_facade_refuses_private_names(self):
        with self.assertRaises(AttributeError):
            _ = PlainFacade(self.document)._missing


class CountedDocument(DummyReadDocument):
    reads = 0

    @property
    def probe(self) -> int:
        type(self).reads += 1
        return 7

    @property
    def broken(self) -> int:
        raise AttributeError("raised inside the property")


class SwitchingDocument(DummyReadDocument):
    """Hands out a different object on every request, as a lazily resolved adaptee may."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.partner = None
        self.toggle = False

    def specific_request(self):
        self.toggle = not self.toggle
        return self.partner if self.toggle and self.partner is not None else self


class DelegationTest(unittest.TestCase):
    def setUp(self):
        CountedDocument.reads = 0

    def test_a_delegated_property_is_evaluated_once_per_read(self):
        facade = PlainFacade(CountedDocument(identifier="a"))
        self.assertEqual(facade.probe, 7)
        self.assertEqual(CountedDocument.reads, 1)

    def test_missing_attribute_is_reported_against_the_facade(self):
        facade = PlainFacade(DummyReadDocument(identifier="a"))
        with self.assertRaisesRegex(AttributeError, "PlainFacade.*nothing_here"):
            _ = facade.nothing_here

    def test_attribute_error_inside_a_property_stays_an_attribute_error(self):
        facade = PlainFacade(CountedDocument(identifier="a"))
        with self.assertRaises(AttributeError):
            _ = facade.broken

    def test_the_adaptee_is_resolved_on_every_miss_not_cached(self):
        partner = DummyReadDocument(identifier="partner")
        document = SwitchingDocument(identifier="own")
        document.partner = partner
        facade = PlainFacade(document)
        first = facade.identifier
        second = facade.identifier
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
