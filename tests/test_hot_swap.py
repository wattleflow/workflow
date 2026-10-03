# Module name: tests/test_hot_swap.py
# Tests for ConnectionManager.hot_swap (FRQ-MGR, FRQ-CON): observers survive the swap,
# a failed swap leaves the old connection active, drivers react to Event.Swap.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest discover -s tests -t . -v
import unittest

from wattleflow.concrete.connection import ConnectionObserverInterface
from wattleflow.concrete.driver import LazyDriverProxy
from wattleflow.concrete.exception import ManagerException
from wattleflow.concrete.manager import ConnectionManager
from wattleflow.core.behavioural import IObserver
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation


class FakeConnection(ConnectionObserverInterface):
    def __init__(self, fail=False, **kwargs):
        super().__init__(**kwargs)
        self.fail = fail
        self.ops: list = []

    def operation(self, action, **kwargs):
        self.ops.append(action)
        if self.fail:
            raise RuntimeError("cannot connect")
        return True


class Watcher(Wattleflow, IObserver):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events: list = []

    def update(self, event, **kwargs):
        self.events.append((event, kwargs))


class HotSwapTest(unittest.TestCase):
    def setUp(self):
        self.manager = ConnectionManager()
        self.old = FakeConnection()
        self.manager._connections["db"] = self.old
        self.watcher = Watcher()
        self.old.subscribe(self.watcher)

    def test_swap_replaces_registered_connection(self):
        new = FakeConnection()
        self.manager.hot_swap("db", new)
        self.assertIs(self.manager.get_connection("db"), new)

    def test_observers_move_and_are_notified_with_swap(self):
        new = FakeConnection()
        self.manager.hot_swap("db", new)
        self.assertEqual(len(self.watcher.events), 1)
        event, kwargs = self.watcher.events[0]
        self.assertEqual(event, Event.Swap)
        self.assertEqual(kwargs["name"], "db")
        self.assertIs(kwargs["connection"], new)
        new.notify(Event.Update)
        self.assertEqual(len(self.watcher.events), 2)

    def test_new_connects_first_old_disconnects_last(self):
        new = FakeConnection()
        self.manager.hot_swap("db", new)
        self.assertEqual(new.ops, [Operation.Connect])
        self.assertEqual(self.old.ops, [Operation.Disconnect])

    def test_failed_connect_keeps_old_connection_active(self):
        new = FakeConnection(fail=True)
        with self.assertRaises(ManagerException):
            self.manager.hot_swap("db", new)
        self.assertIs(self.manager.get_connection("db"), self.old)
        self.assertEqual(self.old.ops, [])
        self.assertEqual(self.watcher.events, [])

    def test_unknown_name_raises(self):
        with self.assertRaises(ManagerException):
            self.manager.hot_swap("missing", FakeConnection())

    def test_old_disconnect_failure_is_not_fatal(self):
        self.old.fail = True
        new = FakeConnection()
        self.manager.hot_swap("db", new)
        self.assertIs(self.manager.get_connection("db"), new)


class ProxyReactionTest(unittest.TestCase):
    def test_proxy_releases_driver_on_matching_swap(self):
        released = []

        class Dummy:
            def ensure_unloaded(self):
                released.append(True)

            def update(self, event, **kwargs):
                pass

        proxy = LazyDriverProxy(factory=Dummy, conn_mgr=None, conn_name="db")
        proxy._driver = Dummy()
        proxy.update(Event.Swap, name="other")
        self.assertIsNotNone(proxy.driver)
        proxy.update(Event.Swap, name="db")
        self.assertIsNone(proxy.driver)
        self.assertEqual(released, [True])


if __name__ == "__main__":
    unittest.main()
