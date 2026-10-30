# Module name: tests/connections/test_memory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""SyRS-CNC-memory: the in-process key-value connection."""

from __future__ import annotations

import unittest

from wattleflow.concrete.connection import ConnectionState
from wattleflow.concrete.exception import ConnectionException
from wattleflow.connections.memory import MemoryConnection


def connection(**kwargs) -> MemoryConnection:
    return MemoryConnection(connection_name="memory", level=50, **kwargs)


class CreateTest(unittest.TestCase):
    def test_a_new_connection_is_created_and_empty(self):  # UC01 k.1
        c = connection()
        self.assertIs(c.state, ConnectionState.CREATED)
        with c.connect() as store:
            self.assertEqual(len(store), 0)

    def test_lazy_loading_creates_the_store_on_first_connect(self):  # UC01 k.2
        c = connection(lazy_loading=True)
        self.assertIsNone(c.connection)
        with c.connect() as store:
            self.assertEqual(len(store), 0)

    def test_without_a_name_there_is_no_connection(self):
        with self.assertRaises(ConnectionException):
            MemoryConnection(level=50)


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.c = connection()

    def test_a_value_set_in_one_session_is_read_in_another(self):  # UC02 k.3
        with self.c.connect() as store:
            store.set("a", {"x": 1})
        with self.c.connect() as store:
            self.assertEqual(store.get("a"), {"x": 1})

    def test_changing_a_returned_value_leaves_the_store_alone(self):  # UC02 k.4
        with self.c.connect() as store:
            store.set("a", {"x": [1]})
            store.get("a")["x"].append(2)
            self.assertEqual(store.get("a"), {"x": [1]})

    def test_delete_says_whether_the_key_existed(self):  # UC02 k.5
        with self.c.connect() as store:
            store.set("a", 1)
            self.assertTrue(store.delete("a"))
            self.assertFalse(store.delete("a"))

    def test_keys_by_prefix_are_sorted(self):  # UC02 k.6
        with self.c.connect() as store:
            for key in ("a:2", "b:1", "a:1"):
                store.set(key, 0)
            self.assertEqual(store.keys("a:"), ["a:1", "a:2"])

    def test_increment_of_a_missing_key_returns_the_amount(self):  # UC02 k.7
        with self.c.connect() as store:
            self.assertEqual(store.increment("n", 3), 3)
            self.assertEqual(store.increment("n"), 4)

    def test_increment_of_text_fails_without_the_value(self):  # UC02 k.8
        with self.c.connect() as store:
            store.set("n", "SECRETVALUE")
            with self.assertRaises(ConnectionException) as raised:
                store.increment("n")
        self.assertNotIn("SECRETVALUE", str(raised.exception))

    def test_a_missing_key_gives_the_default(self):
        with self.c.connect() as store:
            self.assertEqual(store.get("none", 7), 7)


class CloseTest(unittest.TestCase):
    def test_closing_and_creating_again_gives_an_empty_store(self):  # UC03 k.9
        c = connection()
        with c.connect() as store:
            store.set("a", 1)
        c.ensure_closed()
        c.reset()
        c.ensure_created()
        with c.connect() as store:
            self.assertEqual(len(store), 0)


if __name__ == "__main__":
    unittest.main()
