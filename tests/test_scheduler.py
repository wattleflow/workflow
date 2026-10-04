# Module name: tests/test_scheduler.py
# Tests for Scheduler (FRQ-SCH): lifecycle events around the orchestrator, a stop that is not blocked by a
# running start, closure of the Started event on failure, listener isolation and delivery outside the lock,
# the orchestration counter and running flag, and slots (BR-PTN-07).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_scheduler -v
import logging
import threading
import unittest

from wattleflow.concrete.scheduler import Scheduler
from wattleflow.core import IEventListener
from wattleflow.enums.event import Event


class Listener(IEventListener):
    def __init__(self, label="l", log=None):
        self.label = label
        self.log = log if log is not None else []

    @property
    def name(self):
        return self.label

    def on_event(self, event, **kwargs):
        self.log.append((self.label, event, kwargs))


class BrokenListener(Listener):
    def on_event(self, event, **kwargs):
        raise RuntimeError("listener down")


class StubOrchestrator:
    def __init__(self, fail=False, gate=None, entered=None):
        self.calls, self.fail, self.gate, self.entered = [], fail, gate, entered

    def start(self, parallel=False):
        self.calls.append(("start", parallel))
        if self.entered:
            self.entered.set()
        if self.gate:
            self.gate.wait(5)
        if self.fail:
            raise RuntimeError("orchestrator down")

    def stop(self):
        self.calls.append(("stop",))


class Plain(Scheduler):
    """A specialisation that sets nothing: no orchestrator."""


def with_orchestrator(orchestrator, **kwargs):
    scheduler = Plain(level=logging.CRITICAL, **kwargs)
    scheduler._orchestrator = orchestrator
    return scheduler


def events(listener):
    return [entry[1] for entry in listener.log]


class ConstructionTest(unittest.TestCase):
    def test_the_scheduler_can_be_constructed_and_has_no_orchestrator(self):
        scheduler = Plain(level=logging.CRITICAL)
        self.assertIsNone(scheduler._orchestrator)

    def test_starting_and_stopping_without_an_orchestrator_does_nothing(self):
        scheduler = Plain(level=logging.CRITICAL)
        listener = Listener()
        scheduler.register_listener(listener)
        scheduler.start_orchestration()
        scheduler.stop_orchestration()
        self.assertEqual(listener.log, [])

    def test_a_second_init_does_not_reset_the_state(self):
        scheduler = Plain(level=logging.CRITICAL)
        listener = Listener()
        scheduler.register_listener(listener)
        scheduler.__init__(level=logging.CRITICAL)
        self.assertEqual(scheduler._listeners, [listener])

    def test_the_audit_lock_is_not_shared_with_other_instances(self):
        self.assertIsNot(Plain(level=logging.CRITICAL)._lock, Plain(level=logging.CRITICAL)._lock)


class SlotsTest(unittest.TestCase):
    def test_every_attribute_the_class_sets_is_a_declared_slot(self):
        self.assertIn("_preset", Scheduler.__slots__)

    def test_unused_slots_are_gone(self):
        for retired in ("_tasks", "_config"):
            self.assertNotIn(retired, Scheduler.__slots__)


class ListenerTest(unittest.TestCase):
    def setUp(self):
        self.scheduler = Plain(level=logging.CRITICAL)

    def test_a_listener_is_registered_once(self):
        listener = Listener()
        self.scheduler.register_listener(listener)
        self.scheduler.register_listener(listener)
        self.assertEqual(self.scheduler._listeners, [listener])

    def test_two_equal_but_distinct_listeners_are_both_registered(self):
        class Equal(Listener):
            def __eq__(self, other):
                return isinstance(other, Equal)

            __hash__ = None

        log = []
        self.scheduler.register_listener(Equal("a", log))
        self.scheduler.register_listener(Equal("b", log))
        self.scheduler.emit_event(Event.Started)
        self.assertEqual([entry[0] for entry in log], ["a", "b"])

    def test_listeners_hear_events_in_registration_order_with_the_metadata(self):
        log = []
        for label in "ab":
            self.scheduler.register_listener(Listener(label, log))
        self.scheduler.emit_event(Event.Started, key="v")
        self.assertEqual(log, [("a", Event.Started, {"key": "v"}), ("b", Event.Started, {"key": "v"})])

    def test_a_failing_listener_does_not_stop_the_others_or_the_emitter(self):
        log = []
        self.scheduler.register_listener(Listener("a", log))
        self.scheduler.register_listener(BrokenListener())
        self.scheduler.register_listener(Listener("c", log))
        self.scheduler.emit_event(Event.Started)
        self.assertEqual([entry[0] for entry in log], ["a", "c"])

    def test_the_listener_failure_is_logged(self):
        scheduler = Plain(level=logging.DEBUG)
        scheduler.register_listener(BrokenListener())
        with self.assertLogs(level=logging.ERROR) as logged:
            scheduler.emit_event(Event.Started)
        text = "\n".join(logged.output)
        for part in ("Notify", "listener down"):
            self.assertIn(part, text)

    def test_delivery_happens_outside_the_lock(self):
        scheduler, done = self.scheduler, threading.Event()

        class Other(Listener):
            def on_event(self, event, **kwargs):
                worker = threading.Thread(target=lambda: (scheduler.register_listener(Listener("x")), done.set()))
                worker.start()
                worker.join(timeout=2)

        scheduler.register_listener(Other())
        scheduler.emit_event(Event.Started)
        self.assertTrue(done.is_set(), "another thread could not register during delivery")

    def test_a_listener_registered_during_delivery_hears_only_the_next_event(self):
        scheduler, log = self.scheduler, []
        late = Listener("late", log)

        class Adder(Listener):
            def on_event(self, event, **kwargs):
                super().on_event(event, **kwargs)
                scheduler.register_listener(late)

        scheduler.register_listener(Adder("adder", log))
        scheduler.emit_event(Event.Started)
        scheduler.emit_event(Event.Started)
        self.assertEqual([entry[0] for entry in log], ["adder", "adder", "late"])


class LifecycleTest(unittest.TestCase):
    def test_start_emits_started_then_completed_around_the_orchestrator(self):
        orchestrator = StubOrchestrator()
        scheduler = with_orchestrator(orchestrator)
        listener = Listener()
        scheduler.register_listener(listener)
        scheduler.start_orchestration(parallel=True)
        self.assertEqual(events(listener), [Event.Started, Event.Completed])
        self.assertEqual(orchestrator.calls, [("start", True)])

    def test_stop_emits_stopped_then_stops_the_orchestrator(self):
        orchestrator = StubOrchestrator()
        scheduler = with_orchestrator(orchestrator)
        listener = Listener()
        scheduler.register_listener(listener)
        scheduler.stop_orchestration()
        self.assertEqual(events(listener), [Event.Stopped])
        self.assertEqual(orchestrator.calls, [("stop",)])

    def test_a_failing_orchestrator_closes_started_with_failed_and_the_error_propagates(self):
        scheduler = with_orchestrator(StubOrchestrator(fail=True))
        listener = Listener()
        scheduler.register_listener(listener)
        with self.assertRaises(RuntimeError):
            scheduler.start_orchestration()
        self.assertEqual(events(listener), [Event.Started, Event.Failed])
        self.assertIn("orchestrator down", listener.log[-1][2]["error"])

    def test_after_a_failure_the_scheduler_can_start_again(self):
        orchestrator = StubOrchestrator(fail=True)
        scheduler = with_orchestrator(orchestrator)
        with self.assertRaises(RuntimeError):
            scheduler.start_orchestration()
        orchestrator.fail = False
        scheduler.start_orchestration()
        self.assertEqual(len(orchestrator.calls), 2)

    def test_an_orchestrator_that_is_falsy_is_still_used(self):
        class Falsy(StubOrchestrator):
            def __bool__(self):
                return False

        orchestrator = Falsy()
        with_orchestrator(orchestrator).start_orchestration()
        self.assertEqual(orchestrator.calls, [("start", False)])


class CounterTest(unittest.TestCase):
    def test_count_is_the_number_of_completed_orchestrations(self):
        scheduler = with_orchestrator(StubOrchestrator())
        self.assertEqual(scheduler.count, 0)
        scheduler.start_orchestration()
        scheduler.start_orchestration()
        self.assertEqual(scheduler.count, 2)

    def test_a_failed_orchestration_is_not_counted(self):
        scheduler = with_orchestrator(StubOrchestrator(fail=True))
        with self.assertRaises(RuntimeError):
            scheduler.start_orchestration()
        self.assertEqual(scheduler.count, 0)

    def test_running_is_true_only_while_the_orchestrator_runs(self):
        gate, entered = threading.Event(), threading.Event()
        scheduler = with_orchestrator(StubOrchestrator(gate=gate, entered=entered))
        self.assertFalse(scheduler.running)
        worker = threading.Thread(target=scheduler.start_orchestration)
        worker.start()
        self.assertTrue(entered.wait(2))
        self.assertTrue(scheduler.running)
        gate.set()
        worker.join(5)
        self.assertFalse(scheduler.running)

    def test_running_is_false_again_after_a_failure(self):
        scheduler = with_orchestrator(StubOrchestrator(fail=True))
        with self.assertRaises(RuntimeError):
            scheduler.start_orchestration()
        self.assertFalse(scheduler.running)

    def test_a_start_while_running_is_ignored(self):
        gate, entered = threading.Event(), threading.Event()
        orchestrator = StubOrchestrator(gate=gate, entered=entered)
        scheduler = with_orchestrator(orchestrator)
        worker = threading.Thread(target=scheduler.start_orchestration)
        worker.start()
        self.assertTrue(entered.wait(2))
        scheduler.start_orchestration()
        gate.set()
        worker.join(5)
        self.assertEqual(len(orchestrator.calls), 1)


class StopWhileRunningTest(unittest.TestCase):
    def test_stop_is_not_blocked_by_a_running_start(self):
        gate, entered, stopped = threading.Event(), threading.Event(), threading.Event()
        orchestrator = StubOrchestrator(gate=gate, entered=entered)
        scheduler = with_orchestrator(orchestrator)
        starter = threading.Thread(target=scheduler.start_orchestration)
        starter.start()
        self.assertTrue(entered.wait(2))
        stopper = threading.Thread(target=lambda: (scheduler.stop_orchestration(), stopped.set()))
        stopper.start()
        self.assertTrue(stopped.wait(2), "stop_orchestration waited for the running start")
        gate.set()
        starter.join(5)
        stopper.join(5)
        self.assertIn(("stop",), orchestrator.calls)


if __name__ == "__main__":
    unittest.main()
