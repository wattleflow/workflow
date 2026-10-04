# Module name: tests/test_manager.py
# Tests for ConnectionManager, DriverManager and ProcessorManager (FRQ-MGR): registration, lookup,
# operations, release on unregister and on discard, hashing, slots and the observer hook.
# hot_swap is covered by test_hot_swap.py.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_manager -v
import gc
import logging
import sys
import unittest

from wattleflow.concrete.exception import ManagerException
from wattleflow.concrete.manager import ConnectionManager, DriverManager, ProcessorManager
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation

QUIET = {"level": logging.CRITICAL}


class Conn:
    def __init__(self, name="c", connected=True, fail=False):
        self.connection_name, self.connected, self.fail, self.log = name, connected, fail, []

    def request(self, action):
        self.log.append(action)
        if self.fail:
            raise RuntimeError("disconnect down")
        self.connected = False

    def operation(self, action, **kwargs):
        self.log.append(action)
        return True


class NamelessConn(Conn):
    def __init__(self):
        super().__init__()
        del self.connection_name


class Driver:
    def __init__(self, name="d", fail=False):
        self.name, self.fail, self.unloaded, self.ops = name, fail, 0, []

    def ensure_unloaded(self):
        self.unloaded += 1
        if self.fail:
            raise RuntimeError("unload down")

    def operation(self, action, **kwargs):
        self.ops.append(action)
        return True


class Proc:
    def __init__(self, name="p"):
        self.name, self.ops = name, []

    def operation(self, action, **kwargs):
        self.ops.append(action)
        return True


def unraisable(build):
    caught = []
    previous, sys.unraisablehook = sys.unraisablehook, caught.append
    try:
        try:
            build()
        except Exception:
            pass
        gc.collect()
    finally:
        sys.unraisablehook = previous
    return caught


class CommonTest(unittest.TestCase):
    def managers(self):
        return (ConnectionManager(**QUIET), DriverManager(**QUIET), ProcessorManager(**QUIET))

    def test_hash_works_and_is_an_int(self):
        for manager in self.managers():
            with self.subTest(manager=type(manager).__name__):
                self.assertIsInstance(hash(manager), int)
                self.assertEqual(hash(manager), hash(manager))

    def test_each_manager_is_usable_as_a_dict_key(self):
        for manager in self.managers():
            self.assertEqual({manager: 1}[manager], 1)

    def test_every_manager_declares_its_slot(self):
        self.assertIn("_connections", ConnectionManager.__slots__)
        self.assertIn("_drivers", DriverManager.__slots__)
        self.assertIn("_processors", ProcessorManager.__slots__)

    def test_len_counts_the_registered_objects(self):
        connections, drivers, processors = self.managers()
        connections.register_connection(Conn("a"))
        drivers.register_driver(Driver("a"))
        processors.register_processor(Proc("a"))
        self.assertEqual((len(connections), len(drivers), len(processors)), (1, 1, 1))

    def test_the_observer_hook_accepts_an_event_and_does_nothing(self):
        for manager in self.managers():
            with self.subTest(manager=type(manager).__name__):
                manager.update(Event.Swap, name="x")

    def test_a_manager_whose_construction_failed_leaves_no_destructor_error(self):
        for cls in (ConnectionManager, DriverManager, ProcessorManager):
            with self.subTest(cls=cls.__name__):
                self.assertEqual(unraisable(lambda c=cls: c.__new__(c)), [])


class ConnectionManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = ConnectionManager(**QUIET)

    def test_a_second_registration_of_the_same_name_does_not_overwrite(self):
        first, second = Conn("db"), Conn("db")
        self.manager.register_connection(first)
        self.manager.register_connection(second)
        self.assertIs(self.manager.get_connection("db"), first)

    def test_the_name_can_come_from_kwargs_for_an_object_without_one(self):
        self.manager.register_connection(NamelessConn(), connection_name="db")
        self.assertIn("db", self.manager._connections)

    def test_no_name_at_all_is_an_error(self):
        with self.assertRaises(ManagerException):
            self.manager.register_connection(NamelessConn())

    def test_unknown_names_are_manager_exceptions(self):
        with self.assertRaises(ManagerException):
            self.manager.get_connection("nope")
        with self.assertRaises(ManagerException):
            self.manager.operation("nope", Operation.Connect)
        with self.assertRaises(ManagerException):
            self.manager.connect("nope")

    def test_operation_is_forwarded_and_connect_returns_the_connection(self):
        conn = Conn("db")
        self.manager.register_connection(conn)
        self.assertIs(self.manager.connect("db"), conn)
        self.assertEqual(conn.log, [Operation.Connect])

    def test_disconnect_swallows_a_failure_and_answers_false(self):
        class Failing(Conn):
            def operation(self, action, **kwargs):
                raise RuntimeError("down")

        self.manager.register_connection(Failing("db"))
        self.assertFalse(self.manager.disconnect("db"))

    def test_unregister_removes_and_disconnects_a_connected_connection(self):
        conn = Conn("db")
        self.manager.register_connection(conn)
        self.manager.unregister_connection("db")
        self.assertNotIn("db", self.manager._connections)
        self.assertEqual(conn.log, [Operation.Disconnect])

    def test_unregister_leaves_a_connection_that_is_not_connected_alone(self):
        conn = Conn("db", connected=False)
        self.manager.register_connection(conn)
        self.manager.unregister_connection("db")
        self.assertEqual(conn.log, [])

    def test_a_failing_disconnect_on_unregister_still_removes_the_entry(self):
        self.manager.register_connection(Conn("db", fail=True))
        self.manager.unregister_connection("db")
        self.assertNotIn("db", self.manager._connections)

    def test_unregistering_an_unknown_name_is_a_warning(self):
        with self.assertLogs(level=logging.WARNING):
            ConnectionManager(level=logging.DEBUG).unregister_connection("nope")

    def test_discarding_disconnects_every_connected_connection_despite_a_failure(self):
        a, b, c = Conn("a", fail=True), Conn("b"), Conn("c", connected=False)
        for conn in (a, b, c):
            self.manager.register_connection(conn)
        self.manager.__del__()
        self.assertEqual((a.log, b.log, c.log), ([Operation.Disconnect], [Operation.Disconnect], []))


class DriverManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = DriverManager(**QUIET)

    def test_a_second_registration_of_the_same_name_does_not_overwrite(self):
        first, second = Driver("d"), Driver("d")
        self.manager.register_driver(first)
        self.manager.register_driver(second)
        self.assertIs(self.manager.get_driver("d"), first)

    def test_the_name_can_be_given_in_kwargs(self):
        self.manager.register_driver(Driver("x"), name="y")
        self.assertIn("y", self.manager.all)

    def test_unknown_names_are_manager_exceptions(self):
        with self.assertRaises(ManagerException):
            self.manager.get_driver("nope")
        with self.assertRaises(ManagerException):
            self.manager.operation("nope", Operation.Connect)

    def test_unregister_unloads_and_removes_the_driver(self):
        driver = Driver("d")
        self.manager.register_driver(driver)
        self.manager.unregister_driver("d")
        self.assertNotIn("d", self.manager.all)
        self.assertEqual(driver.unloaded, 1)

    def test_a_failing_unload_on_unregister_still_removes_the_entry(self):
        self.manager.register_driver(Driver("d", fail=True))
        self.manager.unregister_driver("d")
        self.assertNotIn("d", self.manager.all)

    def test_unregistering_an_unknown_name_names_a_driver_not_a_connection(self):
        manager = DriverManager(level=logging.DEBUG)
        with self.assertLogs(level=logging.WARNING) as logged:
            manager.unregister_driver("nope")
        text = "\n".join(logged.output)
        self.assertIn("driver", text.lower())
        self.assertNotIn("connection", text.lower())

    def test_discarding_unloads_every_driver_despite_a_failure(self):
        a, b = Driver("a", fail=True), Driver("b")
        self.manager.register_driver(a)
        self.manager.register_driver(b)
        self.manager.__del__()
        self.assertEqual((a.unloaded, b.unloaded), (1, 1))

    def test_discarding_reports_completion_once(self):
        manager = DriverManager(level=logging.DEBUG)
        with self.assertLogs(level=logging.DEBUG) as logged:
            manager.__del__()
        done = [r for r in logged.records if "Delete" in r.getMessage() and "Completed" in r.getMessage()]
        self.assertEqual(len(done), 1)


class ProcessorManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = ProcessorManager(**QUIET)

    def test_a_second_registration_of_the_same_name_does_not_overwrite(self):
        first, second = Proc("p"), Proc("p")
        self.manager.register_processor(first)
        self.manager.register_processor(second)
        self.assertIs(self.manager.get_processor("p"), first)

    def test_unknown_names_are_manager_exceptions(self):
        with self.assertRaises(ManagerException):
            self.manager.get_processor("nope")
        with self.assertRaises(ManagerException):
            self.manager.operation("nope", Operation.Start)

    def test_start_is_forwarded(self):
        proc = Proc("p")
        self.manager.register_processor(proc)
        self.assertTrue(self.manager.operation("p", Operation.Start))
        self.assertEqual(proc.ops, [Operation.Start])

    def test_any_other_action_is_a_warning_and_false_and_the_processor_is_not_called(self):
        proc = Proc("p")
        manager = ProcessorManager(level=logging.DEBUG)
        manager.register_processor(proc)
        with self.assertLogs(level=logging.WARNING):
            self.assertFalse(manager.operation("p", Operation.Stop))
        self.assertEqual(proc.ops, [])

    def test_load_returns_the_processor(self):
        proc = Proc("p")
        self.manager.register_processor(proc)
        self.assertIs(self.manager.load("p"), proc)

    def test_unregister_removes_the_processor(self):
        self.manager.register_processor(Proc("p"))
        self.manager.unregister_processor("p")
        self.assertEqual(len(self.manager), 0)

    def test_discarding_empties_the_registry(self):
        self.manager.register_processor(Proc("a"))
        self.manager.register_processor(Proc("b"))
        self.manager.__del__()
        self.assertEqual(len(self.manager), 0)


if __name__ == "__main__":
    unittest.main()
