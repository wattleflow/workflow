# Module name: tests/test_driver_proxy.py
# Tests for LazyDriverProxy state queries (FRQ-DRV, DEF-DRV-04): asking a lazy proxy for its state,
# whether an action is allowed, or to pause never connects or builds the driver.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_driver_proxy -v
import unittest
from contextlib import contextmanager

from wattleflow.concrete.connection import GenericConnection
from wattleflow.concrete.exception import ManagerException
from wattleflow.concrete.manager import ConnectionManager
from wattleflow.concrete.driver import DriverAction, DriverState, LazyDriverProxy


class FakeConnection:
    """Idle like a real one: the engine exists (`created`) but no session is open (`connected`)."""

    def __init__(self):
        self.connected = False
        self.created = False
        self.requests = 0

    def request(self, **kwargs):
        self.requests += 1
        self.created = True


class FakeManager:
    def __init__(self):
        self.connection = FakeConnection()

    def get_connection(self, name):
        return self.connection


class FakeDriver:
    built = 0

    def __init__(self):
        type(self).built += 1
        self.state = DriverState.PENDING
        self.paused = 0

    def ensure_live(self):
        self.state = DriverState.LIVE

    def ensure_unloaded(self):
        self.state = DriverState.UNLOADED

    def can(self, action):
        return action is DriverAction.PAUSE and self.state is DriverState.LIVE

    def read(self, uri, **kwargs):
        return uri

    def pause(self):
        self.paused += 1
        self.state = DriverState.PAUSED


def proxy():
    FakeDriver.built = 0
    manager = FakeManager()
    return LazyDriverProxy(FakeDriver, manager, "db"), manager


class LazyQueriesTest(unittest.TestCase):
    def test_state_of_a_lazy_proxy_is_pending(self):
        lazy, _ = proxy()
        self.assertIs(lazy.state, DriverState.PENDING)

    def test_state_does_not_build_or_connect(self):
        lazy, manager = proxy()
        _ = lazy.state
        self.assertEqual((FakeDriver.built, manager.connection.requests), (0, 0))
        self.assertIsNone(lazy.driver)

    def test_can_of_a_lazy_proxy_answers_as_for_a_pending_driver(self):
        lazy, manager = proxy()
        self.assertTrue(lazy.can(DriverAction.LOAD))
        self.assertFalse(lazy.can(DriverAction.PAUSE))
        self.assertFalse(lazy.can(DriverAction.UNLOAD))
        self.assertEqual((FakeDriver.built, manager.connection.requests), (0, 0))

    def test_pause_of_a_lazy_proxy_does_nothing(self):
        lazy, manager = proxy()
        lazy.pause()
        self.assertEqual((FakeDriver.built, manager.connection.requests), (0, 0))

    def test_state_returns_to_pending_after_release(self):
        lazy, _ = proxy()
        lazy.load()
        lazy.release()
        self.assertIs(lazy.state, DriverState.PENDING)


class LoadedDelegationTest(unittest.TestCase):
    def test_state_follows_the_driver_once_it_is_built(self):
        lazy, _ = proxy()
        lazy.load()
        self.assertIs(lazy.state, DriverState.LIVE)

    def test_can_is_delegated_once_the_driver_is_built(self):
        lazy, _ = proxy()
        lazy.load()
        self.assertTrue(lazy.can(DriverAction.PAUSE))

    def test_pause_is_delegated_once_the_driver_is_built(self):
        lazy, _ = proxy()
        lazy.load()
        lazy.pause()
        self.assertIs(lazy.state, DriverState.PAUSED)
        self.assertEqual(lazy.driver.paused, 1)


class RequestPerCallTest(unittest.TestCase):
    """DEF-DRV-06: a connect request is made when it has something to do, not on every call."""

    def test_first_call_connects(self):
        lazy, manager = proxy()
        lazy.load()
        self.assertEqual(manager.connection.requests, 1)

    def test_later_calls_do_not_repeat_the_request(self):
        lazy, manager = proxy()
        lazy.load()
        for _ in range(5):
            lazy.read("uri")
        self.assertEqual(manager.connection.requests, 1)

    def test_the_connection_is_still_fetched_from_the_manager_on_every_call(self):
        lazy, manager = proxy()
        fetched = []
        original = manager.get_connection
        manager.get_connection = lambda name: fetched.append(name) or original(name)
        lazy.load()
        lazy.read("uri")
        lazy.read("uri")
        self.assertEqual(len(fetched), 3)


class FailingConnection(GenericConnection):
    def create_connection(self) -> None:
        raise RuntimeError("engine cannot be built")

    @contextmanager
    def connect(self):
        yield None

    def disconnect(self) -> None:
        pass


class FailureStaysVisibleTest(unittest.TestCase):
    def test_a_failed_connection_keeps_raising_on_later_calls(self):
        manager = ConnectionManager()
        manager._connections["db"] = FailingConnection(connection_name="db", lazy_loading=True)
        FakeDriver.built = 0
        lazy = LazyDriverProxy(FakeDriver, manager, "db")
        with self.assertRaises(RuntimeError):
            lazy.load()
        with self.assertRaises(ManagerException):
            lazy.load()


if __name__ == "__main__":
    unittest.main()
