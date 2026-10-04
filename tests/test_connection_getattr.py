# Module name: tests/test_connection_getattr.py
# Tests for GenericConnection.__getattr__ (FRQ-CON, DEF-CON-03): the slot set is computed once
# per type, and attribute resolution (slots, preset, unknown names) behaves as before.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_connection_getattr -v
import unittest
from contextlib import contextmanager

from wattleflow.concrete.connection import GenericConnection


class HostConnection(GenericConnection):
    ALLOWED = ["host", "port"]

    def create_connection(self) -> None:
        pass

    @contextmanager
    def connect(self):
        yield None

    def disconnect(self) -> None:
        pass


class SlottedConnection(HostConnection):
    __slots__ = ("_extra",)


def build(cls, **kwargs):
    return cls(connection_name="stub", lazy_loading=True, **kwargs)


class PresetResolutionTest(unittest.TestCase):
    def test_declared_key_with_value_is_resolved_from_the_preset(self):
        self.assertEqual(build(HostConnection, host="h").host, "h")

    def test_declared_key_without_value_is_none(self):
        self.assertIsNone(build(HostConnection, host="h").port)

    def test_undeclared_name_is_refused(self):
        with self.assertRaises(AttributeError):
            _ = build(HostConnection).not_declared


class SlotResolutionTest(unittest.TestCase):
    def test_unset_slot_raises_attribute_error_and_does_not_reach_the_preset(self):
        half_built = object.__new__(HostConnection)
        with self.assertRaises(AttributeError):
            _ = half_built._connection

    def test_unset_slot_of_a_subclass_raises_attribute_error(self):
        connection = build(SlottedConnection)
        with self.assertRaises(AttributeError):
            _ = connection._extra


class SlotSetCacheTest(unittest.TestCase):
    def test_slot_set_is_stored_once_on_the_type_after_the_first_miss(self):
        connection = build(HostConnection, host="h")
        _ = connection.host
        cached = HostConnection.__dict__.get("_slot_names")
        self.assertIsInstance(cached, frozenset)
        _ = connection.port
        self.assertIs(HostConnection.__dict__.get("_slot_names"), cached)

    def test_each_type_keeps_its_own_slot_set(self):
        _ = build(HostConnection).port
        _ = build(SlottedConnection).port
        parent = HostConnection.__dict__["_slot_names"]
        child = SlottedConnection.__dict__["_slot_names"]
        self.assertNotIn("_extra", parent)
        self.assertIn("_extra", child)
        self.assertTrue(parent < child)

    def test_cached_set_contains_the_generic_slots(self):
        _ = build(HostConnection).port
        self.assertTrue({"_fsm", "_version", "_preset"} <= HostConnection.__dict__["_slot_names"])


if __name__ == "__main__":
    unittest.main()
