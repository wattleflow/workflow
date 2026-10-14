# Module name: tests/test_connection_observers.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Observers of a connection: `attach`, `detach`, `notify` (FR-CNC-12, FR-CNC-16, IObservable).

Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_connection_observers -v
"""

import logging
import unittest

from wattleflow.concrete.connection import ConnectionObserverInterface
from wattleflow.core import IObservable, IObserver


class Observed(ConnectionObserverInterface):
    __slots__ = ()


class Watcher(IObserver):
    __slots__ = ("label", "heard")

    def __init__(self, label: str) -> None:
        self.label = label
        self.heard: list = []

    @property
    def name(self) -> str:
        return self.label

    def update(self, event, **kwargs) -> None:
        self.heard.append((event, kwargs))


class Failing(Watcher):
    __slots__ = ()

    def update(self, event, **kwargs) -> None:
        raise RuntimeError("down")


class AttachTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = Observed(level=logging.CRITICAL)

    def test_it_is_an_observable(self):
        self.assertIsInstance(self.connection, IObservable)

    def test_only_an_observer_is_attached(self):  # FR-CNC-12 k.1
        with self.assertRaisesRegex(TypeError, "Expected IObserver, got object"):
            self.connection.attach(object())

    def test_a_second_observer_of_the_same_name_is_not_added(self):  # k.2
        first, second = Watcher("x"), Watcher("x")
        self.connection.attach(first)
        self.connection.attach(second)
        self.assertEqual(list(self.connection._observers.values()), [first])

    def test_detach_removes_the_attached_object(self):  # k.3
        a, b = Watcher("a"), Watcher("b")
        self.connection.attach(a)
        self.connection.attach(b)
        self.connection.detach(a)
        self.assertEqual([o.name for o in self.connection._observers.values()], ["b"])

    def test_detach_does_not_remove_another_object_of_the_same_name(self):  # k.3
        attached, impostor = Watcher("x"), Watcher("x")
        self.connection.attach(attached)
        self.connection.detach(impostor)
        self.assertIn(attached, self.connection._observers.values())

    def test_detaching_an_unknown_observer_is_quiet(self):
        self.connection.detach(Watcher("never"))

    def test_the_old_names_are_gone(self):
        self.assertFalse(hasattr(self.connection, "subscribe"))
        self.assertFalse(hasattr(self.connection, "unsubscribe"))
        self.assertFalse(hasattr(self.connection, "subscribe_observer"))

    def test_transfer_moves_every_observer(self):
        target = Observed(level=logging.CRITICAL)
        a, b = Watcher("a"), Watcher("b")
        self.connection.attach(a)
        self.connection.attach(b)
        self.connection.transfer_observers(target)
        self.assertEqual(set(target._observers), {"a", "b"})


class NotifyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = Observed(level=logging.CRITICAL)

    def test_every_observer_hears_the_event_and_its_data(self):  # FR-CNC-16 k.1
        a, b = Watcher("a"), Watcher("b")
        self.connection.attach(a)
        self.connection.attach(b)
        self.connection.notify("swap", name="db")
        self.assertEqual(a.heard, [("swap", {"name": "db"})])
        self.assertEqual(b.heard, [("swap", {"name": "db"})])

    def test_the_event_can_be_passed_by_keyword(self):
        a = Watcher("a")
        self.connection.attach(a)
        self.connection.notify(event="e")
        self.assertEqual(a.heard, [("e", {})])

    def test_a_failing_observer_does_not_stop_the_rest(self):  # k.2, k.3
        failing, healthy = Failing("bad"), Watcher("good")
        self.connection.attach(failing)
        self.connection.attach(healthy)
        with self.assertLogs("wattleflow.concrete.connection", level="WARNING") as logs:
            self.connection.notify("e")
        self.assertEqual(healthy.heard, [("e", {})])
        self.assertIn("Observer 'bad' raised an exception during notify", logs.output[0])


if __name__ == "__main__":
    unittest.main()
