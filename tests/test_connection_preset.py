# Module name: tests/test_connection_preset.py
# Tests for the preset surface of GenericConnection (FRQ-CON, DEF-CON-04): `lazy_loading` is the
# generic class's own argument, so it is declared once there and never reported as unknown.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_connection_preset -v
import unittest
from contextlib import contextmanager

from wattleflow.concrete.connection import ConnectionState, GenericConnection
from wattleflow.decorators.preset import PresetGate


class RecordingConnection(GenericConnection):
    """Declares nothing of its own and records every warning raised during construction."""

    warnings: list = []

    def warning(self, **kwargs):
        type(self).warnings.append(kwargs)

    def create_connection(self) -> None:
        pass

    @contextmanager
    def connect(self):
        yield None

    def disconnect(self) -> None:
        pass


class DeclaredConnection(RecordingConnection):
    ALLOWED = ["host"]


class LazyLoadingDeclarationTest(unittest.TestCase):
    def setUp(self):
        RecordingConnection.warnings = []

    def test_generic_class_declares_lazy_loading(self):
        self.assertIn("lazy_loading", PresetGate.resolve(RecordingConnection))

    def test_specialisation_inherits_the_declaration_and_adds_its_own(self):
        permitted = PresetGate.resolve(DeclaredConnection)
        self.assertLessEqual({"lazy_loading", "host"}, permitted)

    def test_lazy_loading_is_not_reported_as_unknown(self):
        RecordingConnection(connection_name="stub", lazy_loading=True)
        self.assertEqual(RecordingConnection.warnings, [])

    def test_other_undeclared_keys_are_still_reported(self):
        RecordingConnection(connection_name="stub", lazy_loading=True, typo="x")
        self.assertEqual(len(RecordingConnection.warnings), 1)
        self.assertEqual(RecordingConnection.warnings[0]["discarded"], ["typo"])

    def test_preset_keeps_the_value(self):
        connection = RecordingConnection(connection_name="stub", lazy_loading=True)
        self.assertIs(connection._preset.lazy_loading, True)


class LazyLoadingBehaviourTest(unittest.TestCase):
    def test_lazy_connection_builds_no_engine_on_construction(self):
        connection = RecordingConnection(connection_name="stub", lazy_loading=True)
        self.assertIs(connection.state, ConnectionState.NEW)

    def test_eager_connection_builds_the_engine_on_construction(self):
        connection = RecordingConnection(connection_name="stub")
        self.assertIs(connection.state, ConnectionState.CREATED)


if __name__ == "__main__":
    unittest.main()
