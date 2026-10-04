# Module name: tests/test_connection_request.py
# Tests for GenericConnection.request (FRQ-CON, DEF-CON-01): an unknown or missing
# action is a ConnectionException, Connect and Disconnect drive the engine level.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_connection_request -v
import unittest
from contextlib import contextmanager
from typing import get_type_hints

from wattleflow.concrete.connection import ConnectionState, GenericConnection
from wattleflow.concrete.exception import ConnectionException
from wattleflow.enums.operation import Operation


class StubConnection(GenericConnection):
    def create_connection(self) -> None:
        self.engine = object()

    @contextmanager
    def connect(self):
        yield self.engine

    def disconnect(self) -> None:
        self.engine = None


class RequestTest(unittest.TestCase):
    def setUp(self):
        self.connection = StubConnection(connection_name="stub", lazy_loading=True)

    def test_unknown_action_raises_connection_exception(self):
        with self.assertRaises(ConnectionException):
            self.connection.request(action=Operation.Start)

    def test_missing_action_raises_connection_exception(self):
        with self.assertRaises(ConnectionException):
            self.connection.request()

    def test_unknown_action_leaves_state_unchanged(self):
        before = self.connection.state
        with self.assertRaises(ConnectionException):
            self.connection.request(action=Operation.Stop)
        self.assertIs(self.connection.state, before)

    def test_connect_builds_the_engine(self):
        self.connection.request(action=Operation.Connect)
        self.assertIs(self.connection.state, ConnectionState.CREATED)

    def test_disconnect_closes_the_engine(self):
        self.connection.request(action=Operation.Connect)
        self.connection.request(action=Operation.Disconnect)
        self.assertIs(self.connection.state, ConnectionState.CLOSED)

    def test_operation_still_answers_false_for_unsupported_action(self):
        self.assertFalse(self.connection.operation(Operation.Start))


class VersionContractTest(unittest.TestCase):
    """DEF-CON-02: `version` is the remote system's version, or None when unknown."""

    def setUp(self):
        self.connection = StubConnection(connection_name="stub", lazy_loading=True)

    def test_version_is_none_by_default(self):
        self.assertIsNone(self.connection.version)

    def test_version_stays_none_when_the_specialisation_does_not_fill_it(self):
        self.connection.request(action=Operation.Connect)
        self.connection.request(action=Operation.Disconnect)
        self.assertIsNone(self.connection.version)

    def test_version_declares_none_as_a_legal_value(self):
        hint = get_type_hints(GenericConnection.version.fget)["return"]
        self.assertEqual(hint, str | None)

    def test_version_is_read_only(self):
        with self.assertRaises(AttributeError):
            self.connection.version = "1.0"


class CreatedPropertyTest(unittest.TestCase):
    """DEF-DRV-06: `created` is true exactly where `request(Connect)` has nothing to do."""

    def connection_in(self, state: ConnectionState) -> StubConnection:
        connection = StubConnection(connection_name="stub", lazy_loading=True)
        connection._fsm._state = state
        return connection

    def test_created_is_true_where_a_connect_request_is_a_no_op(self):
        for state in (
            ConnectionState.CREATING,
            ConnectionState.CREATED,
            ConnectionState.CONNECTED,
        ):
            with self.subTest(state=state):
                self.assertTrue(self.connection_in(state).created)

    def test_created_is_false_everywhere_else(self):
        for state in (
            ConnectionState.NEW,
            ConnectionState.CONNECTING,
            ConnectionState.CLOSING,
            ConnectionState.CLOSED,
            ConnectionState.FAILED,
        ):
            with self.subTest(state=state):
                self.assertFalse(self.connection_in(state).created)

    def test_created_matches_what_a_connect_request_actually_does(self):
        for state in ConnectionState:
            connection = self.connection_in(state)
            created = connection.created
            try:
                connection.request(action=Operation.Connect)
                acted = connection.state is not state
            except Exception:
                acted = True
            with self.subTest(state=state):
                self.assertEqual(created, not acted)


if __name__ == "__main__":
    unittest.main()
