# Module name: tests/test_orchestrator.py
# Tests for Orchestrator (FRQ-ORC): processors in order or in parallel, events to listeners, failures,
# stop, and the guards a facade over threads needs (atomic start, isolated listeners, exact signature
# fallback, duplicates).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_orchestrator -v
import logging
import threading
import time
import unittest

from wattleflow.concrete.exception import AttributeException, OrchestratorException
from wattleflow.concrete.manager import ConnectionManager
from wattleflow.concrete.orchestrator import Orchestrator
from wattleflow.core import IEventListener
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation


class Proc:
    """A processor stand-in: records its run, can fail or wait."""

    def __init__(self, label, log, fail=False, gate=None, entered=None):
        self.label, self.log, self.fail, self.gate, self.entered = label, log, fail, gate, entered

    @property
    def name(self):
        return self.label

    def start(self):
        if self.entered:
            self.entered.set()
        if self.gate:
            self.gate.wait(5)
        self.log.append(self.label)
        if self.fail:
            raise RuntimeError(f"{self.label} down")


class FacadeOnly:
    name = "facade"

    def __init__(self, log):
        self.log = log

    def operation(self, action):
        self.log.append(("operation", action))


class Listener(IEventListener):
    def __init__(self, label="l"):
        self.label, self.log = label, []

    @property
    def name(self):
        return self.label

    def on_event(self, event, **kwargs):
        self.log.append((event, kwargs))

    def events(self):
        return [e for e, _ in self.log]


class Strict(Listener):
    """Contract signature: on_event(event) only."""

    def on_event(self, event):
        self.log.append((event, {}))


class Broken(Listener):
    def on_event(self, event, **kwargs):
        raise RuntimeError("listener down")


class TypeErrorInside(Listener):
    calls = 0

    def on_event(self, event, **kwargs):
        type(self).calls += 1
        raise TypeError("bug inside the listener")


def make(*procs, listeners=()):
    orchestrator = Orchestrator(connection_manager=ConnectionManager(), level=logging.CRITICAL)
    for proc in procs:
        orchestrator.add_processor(proc)
    for listener in listeners:
        orchestrator.register_listener(listener)
    return orchestrator


class ConstructionTest(unittest.TestCase):
    def test_a_connection_manager_is_required_and_type_checked(self):
        for bad in (None, object(), "manager"):
            with self.subTest(bad=bad), self.assertRaises(AttributeException):
                Orchestrator(connection_manager=bad, level=logging.CRITICAL)

    def test_a_strategy_must_be_a_strategy_when_given(self):
        with self.assertRaises(AttributeException):
            Orchestrator(connection_manager=ConnectionManager(), strategy_execute=object(), level=logging.CRITICAL)

    def test_the_collaborators_are_exposed_read_only(self):
        manager = ConnectionManager()
        orchestrator = Orchestrator(connection_manager=manager, level=logging.CRITICAL)
        self.assertIs(orchestrator.connection_manager, manager)
        self.assertIsNone(orchestrator.strategy_execute)
        self.assertFalse(orchestrator.running)
        with self.assertRaises(AttributeError):
            orchestrator.connection_manager = None


class RegistrationTest(unittest.TestCase):
    def test_a_processor_without_start_is_rejected(self):
        with self.assertRaises(OrchestratorException):
            make().add_processor(object())

    def test_a_facade_only_processor_is_accepted(self):
        make().add_processor(Proc("p", []))

    def test_the_same_processor_is_added_once(self):
        log, proc = [], None
        proc = Proc("p", log)
        orchestrator = make(proc, proc)
        orchestrator.start()
        self.assertEqual(log, ["p"])

    def test_a_listener_is_registered_once_and_equal_ones_are_two(self):
        class Equal(Listener):
            def __eq__(self, other):
                return isinstance(other, Equal)

            __hash__ = None

        first, second = Equal("a"), Equal("b")
        orchestrator = make(listeners=(first, first, second))
        orchestrator.emit_event(Event.Processed)
        self.assertEqual((len(first.log), len(second.log)), (1, 1))


class SequentialTest(unittest.TestCase):
    def test_processors_run_in_registration_order_and_events_surround_them(self):
        log, listener = [], Listener()
        orchestrator = make(Proc("a", log), Proc("b", log), listeners=(listener,))
        orchestrator.start()
        self.assertEqual(log, ["a", "b"])
        self.assertEqual(
            listener.events(),
            [Event.OrchestrationStarted, Event.Processed, Event.Processed, Event.OrchestrationCompleted],
        )
        self.assertEqual([k["processor"] for e, k in listener.log if e is Event.Processed], ["a", "b"])
        self.assertTrue(all(k["duration"] >= 0 for e, k in listener.log if e is Event.Processed))

    def test_a_failure_stops_the_rest_and_raises_with_the_cause(self):
        log, listener = [], Listener()
        orchestrator = make(Proc("a", log, fail=True), Proc("b", log), listeners=(listener,))
        with self.assertRaises(OrchestratorException) as caught:
            orchestrator.start()
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(log, ["a"])

    def test_completed_is_emitted_after_a_failure_and_running_is_reset(self):
        log, listener = [], Listener()
        proc = Proc("a", log, fail=True)
        orchestrator = make(proc, listeners=(listener,))
        with self.assertRaises(OrchestratorException):
            orchestrator.start()
        self.assertEqual(listener.events()[-1], Event.OrchestrationCompleted)
        self.assertIn(Event.Failed, listener.events())
        proc.fail = False
        orchestrator.start()  # not stuck as running
        self.assertEqual(log, ["a", "a"])

    def test_a_processor_with_only_operation_is_started_through_it(self):
        log = []
        orchestrator = make()
        facade = FacadeOnly(log)
        orchestrator._processors.append(facade)
        orchestrator.start()
        self.assertEqual(log, [("operation", Operation.Start)])

    def test_a_processor_with_neither_is_a_failure(self):
        orchestrator = make()
        orchestrator._processors.append(object())
        with self.assertRaises(OrchestratorException):
            orchestrator.start()

    def test_stop_between_processors_skips_the_rest(self):
        log = []
        orchestrator = make()

        class Stopper(Proc):
            def start(self):
                super().start()
                orchestrator.stop()

        orchestrator.add_processor(Stopper("a", log))
        orchestrator.add_processor(Proc("b", log))
        orchestrator.start()
        self.assertEqual(log, ["a"])


class ParallelTest(unittest.TestCase):
    def test_all_processors_run_and_succeed(self):
        log = []
        make(Proc("a", log), Proc("b", log), Proc("c", log)).start(parallel=True)
        self.assertEqual(sorted(log), ["a", "b", "c"])

    def test_a_failure_does_not_stop_the_other_threads(self):
        log = []
        orchestrator = make(Proc("a", log, fail=True), Proc("b", log), Proc("c", log))
        with self.assertRaises(OrchestratorException):
            orchestrator.start(parallel=True)
        self.assertEqual(sorted(log), ["a", "b", "c"])

    def test_every_failure_is_named_in_the_error(self):
        orchestrator = make(Proc("a", [], fail=True), Proc("b", [], fail=True), Proc("c", []))
        with self.assertRaises(OrchestratorException) as caught:
            orchestrator.start(parallel=True)
        text = str(caught.exception)
        self.assertIn("Error processing a", text)
        self.assertIn("Error processing b", text)
        self.assertNotIn("Error processing c", text)

    def test_stop_during_a_parallel_run_does_not_interrupt_running_processors(self):
        gate, entered, log = threading.Event(), threading.Event(), []
        orchestrator = make(Proc("a", log, gate=gate, entered=entered))
        worker = threading.Thread(target=lambda: orchestrator.start(parallel=True))
        worker.start()
        self.assertTrue(entered.wait(2))
        orchestrator.stop()
        self.assertFalse(orchestrator.running)
        gate.set()
        worker.join(5)
        self.assertEqual(log, ["a"])  # the processor ran to its end: threads are not interruptible

    def test_operation_start_can_ask_for_parallel(self):
        log, gate = [], threading.Barrier(2, timeout=3)

        class Meet(Proc):
            def start(self):
                gate.wait()  # both must be running at once, or the barrier breaks
                super().start()

        orchestrator = make(Meet("a", log), Meet("b", log))
        orchestrator.operation(Operation.Start, parallel=True)
        self.assertEqual(sorted(log), ["a", "b"])

    def test_operation_rejects_an_unknown_action(self):
        with self.assertRaises(OrchestratorException):
            make().operation("restart")


class StartGuardTest(unittest.TestCase):
    def test_a_start_while_running_is_ignored(self):
        log, gate, entered = [], threading.Event(), threading.Event()
        orchestrator = make(Proc("a", log, gate=gate, entered=entered))
        worker = threading.Thread(target=orchestrator.start)
        worker.start()
        self.assertTrue(entered.wait(2))
        orchestrator.start()
        gate.set()
        worker.join(5)
        self.assertEqual(log, ["a"])

    def test_two_simultaneous_starts_run_the_processors_once(self):
        class Slow(Proc):
            def start(self):
                time.sleep(0.02)
                super().start()

        def round_trip():
            log, barrier = [], threading.Barrier(2)
            orchestrator = make(Slow("a", log))

            def go():
                barrier.wait()
                orchestrator.start()

            threads = [threading.Thread(target=go) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(5)
            return log

        for _ in range(20):
            self.assertEqual(round_trip(), ["a"])


class StateLockTest(unittest.TestCase):
    def test_claiming_and_releasing_running_happen_under_the_state_lock(self):
        """The race between two starts cannot be forced, so the guard is asserted directly."""

        class Spy:
            def __init__(self):
                self.entered = 0
                self.inner = threading.Lock()

            def __enter__(self):
                self.entered += 1
                return self.inner.__enter__()

            def __exit__(self, *exc):
                return self.inner.__exit__(*exc)

        orchestrator = make()
        orchestrator._state_lock = spy = Spy()
        orchestrator.start()
        self.assertEqual(spy.entered, 2)  # claim, then release
        orchestrator.stop()
        self.assertEqual(spy.entered, 3)


class ListenerDeliveryTest(unittest.TestCase):
    def test_a_strict_listener_gets_the_event_once_without_metadata(self):
        strict = Strict()
        make(listeners=(strict,)).emit_event(Event.Processed, processor="p")
        self.assertEqual(strict.events(), [Event.Processed])

    def test_a_type_error_inside_a_listener_is_not_retried(self):
        TypeErrorInside.calls = 0
        listener = TypeErrorInside()
        orchestrator = make(listeners=(listener,))
        orchestrator.emit_event(Event.Processed, processor="p")
        self.assertEqual(TypeErrorInside.calls, 1)

    def test_a_failing_listener_does_not_stop_the_others_or_the_emitter(self):
        good = Listener()
        orchestrator = make(listeners=(Broken(), good))
        orchestrator.emit_event(Event.Processed)
        self.assertEqual(good.events(), [Event.Processed])

    def test_a_failing_listener_does_not_turn_a_good_processor_into_a_failure(self):
        log = []
        orchestrator = make(Proc("a", log), Proc("b", log), listeners=(Broken(),))
        orchestrator.start()
        self.assertEqual(log, ["a", "b"])

    def test_a_failing_listener_does_not_hide_the_original_error(self):
        orchestrator = make(Proc("a", [], fail=True), listeners=(Broken(),))
        with self.assertRaises(OrchestratorException) as caught:
            orchestrator.start()
        self.assertIn("a down", str(caught.exception))

    def test_the_listener_failure_is_logged(self):
        orchestrator = Orchestrator(connection_manager=ConnectionManager(), level=logging.DEBUG)
        orchestrator.register_listener(Broken())
        with self.assertLogs(level=logging.ERROR) as logged:
            orchestrator.emit_event(Event.Processed)
        self.assertIn("listener down", "\n".join(logged.output))

    def test_delivery_is_outside_the_lock(self):
        done = threading.Event()
        orchestrator = make()

        class Registers(Listener):
            def on_event(self, event, **kwargs):
                worker = threading.Thread(target=lambda: (orchestrator.register_listener(Listener("x")), done.set()))
                worker.start()
                worker.join(2)

        orchestrator.register_listener(Registers())
        orchestrator.emit_event(Event.Processed)
        self.assertTrue(done.is_set())


if __name__ == "__main__":
    unittest.main()
