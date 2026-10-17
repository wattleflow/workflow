# Module name: tests/test_fault_tolerance.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Retry, circuit breaker and fault events (StRS-FAULT-TOLERANCE BR-FTL-21…26).

The storage part (SyRS-FTL-fault-tolerance, FR-FTL-01…14) has no code yet and no test here.
Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_fault_tolerance -v
"""

import threading
import unittest

from wattleflow.concrete import fault_tolerance as ft
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.fault_tolerance import (
    CircuitBreakerInvoker,
    CircuitOpenError,
    CircuitStateMachine,
    EventEmitter,
    FaultEvent,
    FaultToleranceException,
    InvokerCommand,
    RetryExhaustedError,
    RetryInvoker,
    RetryPolicy,
)
from wattleflow.constants.fault_tolerance import (
    CIRCUIT_REJECTED,
    CIRCUIT_STATE_CHANGED,
    RETRY_GAVE_UP,
    RETRY_SCHEDULED,
)
from wattleflow.core import ICommand, IEventListener, IStrategy
from wattleflow.enums.fault_tolerance import BreakerAction, BreakerState
from wattleflow.helpers.moment import MomentAwareHelper


class Operation(ICommand):
    """Fails `failures` times, then answers."""

    __slots__ = ("calls", "failures", "error")

    def __init__(self, failures: int = 0, error: BaseException | None = None) -> None:
        self.calls = 0
        self.failures = failures
        self.error = error or RuntimeError("down")

    @property
    def name(self) -> str:
        return "Operation"

    def execute(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return kwargs.get("value", "ok")


class Recorder(IEventListener):
    __slots__ = ("events",)

    def __init__(self) -> None:
        self.events: list = []

    @property
    def name(self) -> str:
        return "Recorder"

    def on_event(self, event) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Fallback(IStrategy):
    __slots__ = ()

    @property
    def name(self) -> str:
        return "Fallback"

    def algorithm(self, caller, **kwargs):
        return "fallback"


class PolicyTest(unittest.TestCase):  # BR-FTL-22
    def test_the_delay_grows_with_each_attempt(self):
        policy = RetryPolicy(max_attempts=5, base_delay=0.1, multiplier=2.0)
        delays = [policy.algorithm(self, attempt=n, error=RuntimeError()) for n in (1, 2, 3, 4)]
        self.assertEqual(delays, [0.1, 0.2, 0.4, 0.8])

    def test_the_delay_never_passes_the_maximum(self):
        policy = RetryPolicy(max_attempts=20, base_delay=1.0, multiplier=10.0, max_delay=5.0)
        self.assertEqual(policy.algorithm(self, attempt=4, error=RuntimeError()), 5.0)

    def test_the_attempts_are_limited(self):
        policy = RetryPolicy(max_attempts=3)
        self.assertIsNone(policy.algorithm(self, attempt=3, error=RuntimeError()))

    def test_only_the_declared_errors_are_retried(self):
        policy = RetryPolicy(retry_on=(TimeoutError,))
        self.assertIsNotNone(policy.algorithm(self, attempt=1, error=TimeoutError()))
        self.assertIsNone(policy.algorithm(self, attempt=1, error=ValueError()))

    def test_invalid_settings_are_refused(self):
        for kwargs in (
            {"max_attempts": 0},
            {"base_delay": -1},
            {"max_delay": -1},
            {"multiplier": 0.5},
        ):
            with self.subTest(**kwargs), self.assertRaises(FaultToleranceException):
                RetryPolicy(**kwargs)

    def test_the_boundary_values_are_accepted(self):
        RetryPolicy(max_attempts=1, base_delay=0, max_delay=0, multiplier=1)

    def test_the_attempt_before_the_limit_still_waits(self):
        policy = RetryPolicy(max_attempts=3)
        self.assertIsNotNone(policy.algorithm(self, attempt=2, error=RuntimeError()))

    def test_a_subclass_of_a_declared_error_is_retried(self):
        policy = RetryPolicy(retry_on=(OSError,))
        self.assertIsNotNone(policy.algorithm(self, attempt=1, error=TimeoutError()))

    def test_it_has_a_name_and_is_a_strategy(self):
        policy = RetryPolicy()
        self.assertEqual((policy.name, str(policy)), ("RetryPolicy", "RetryPolicy"))
        self.assertIsInstance(policy, IStrategy)


class RetryInvokerTest(unittest.TestCase):
    def build(self, operation, **policy):
        self.slept: list[float] = []
        invoker = RetryInvoker(
            RetryPolicy(**policy), command=operation, sleep=self.slept.append, source="test"
        )
        self.listener = Recorder()
        invoker.register_listener(self.listener)
        return invoker

    def test_success_needs_no_retry_and_no_event(self):
        invoker = self.build(Operation())
        self.assertEqual(invoker.invoke(value=7), 7)
        self.assertEqual((self.slept, self.listener.events), ([], []))

    def test_a_transient_fault_is_retried_and_reported(self):  # BR-FTL-25
        operation = Operation(failures=2)
        invoker = self.build(operation, max_attempts=5, base_delay=0.5)
        self.assertEqual(invoker.invoke(), "ok")
        self.assertEqual(operation.calls, 3)
        self.assertEqual(self.slept, [0.5, 1.0])
        self.assertEqual(self.listener.types(), [RETRY_SCHEDULED, RETRY_SCHEDULED])
        self.assertEqual(self.listener.events[0].payload["attempt"], 1)

    def test_exhaustion_is_chained_to_the_last_error(self):
        error = RuntimeError("down")
        invoker = self.build(Operation(failures=9, error=error), max_attempts=3, base_delay=0)
        with self.assertRaises(RetryExhaustedError) as caught:
            invoker.invoke()
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(self.listener.types()[-1], RETRY_GAVE_UP)
        self.assertEqual((caught.exception.attempts, caught.exception.last_error), (3, error))
        self.assertIs(caught.exception.caller, invoker)

    def test_the_exceptions_belong_to_the_framework_taxonomy(self):
        for kind in (RetryExhaustedError, CircuitOpenError):
            self.assertTrue(issubclass(kind, FaultToleranceException))
        self.assertTrue(issubclass(FaultToleranceException, AuditException))

    def test_a_first_attempt_without_retry_raises_the_original(self):
        error = RuntimeError("down")
        invoker = self.build(Operation(failures=9, error=error), max_attempts=1)
        with self.assertRaises(RuntimeError) as caught:
            invoker.invoke()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.listener.types(), [RETRY_GAVE_UP])

    def test_what_is_not_an_exception_is_never_caught(self):
        invoker = self.build(Operation(failures=1, error=KeyboardInterrupt()))
        with self.assertRaises(KeyboardInterrupt):
            invoker.invoke()
        self.assertEqual(self.slept, [])

    def test_the_final_report_carries_the_attempts_and_the_error(self):
        invoker = self.build(Operation(failures=9), max_attempts=2, base_delay=0)
        with self.assertRaises(RetryExhaustedError):
            invoker.invoke()
        gave_up = self.listener.events[-1]
        self.assertEqual(gave_up.type, RETRY_GAVE_UP)
        self.assertEqual(gave_up.payload["attempts"], 2)
        self.assertIn("error", gave_up.payload)

    def test_the_scheduled_report_carries_the_delay_and_the_error(self):
        invoker = self.build(Operation(failures=1), max_attempts=3, base_delay=0.25)
        invoker.invoke()
        payload = self.listener.events[0].payload
        self.assertEqual((payload["attempt"], payload["delay"]), (1, 0.25))
        self.assertIn("error", payload)

    def test_without_a_command_it_says_so(self):
        invoker = RetryInvoker(RetryPolicy())
        with self.assertRaisesRegex(FaultToleranceException, "No command set"):
            invoker.invoke()
        invoker.set_command(Operation())
        self.assertEqual(invoker.invoke(), "ok")


class MachineTest(unittest.TestCase):  # BR-FTL-23
    def build(self, threshold=3, timeout=10.0):
        self.clock = Clock()
        return CircuitStateMachine(threshold, timeout, clock=self.clock)

    def test_it_starts_closed_and_it_has_a_name(self):
        machine = self.build()
        self.assertEqual((machine.state, machine.failures), (BreakerState.CLOSED, 0))
        self.assertEqual(machine.name, "CircuitStateMachine")

    def test_it_opens_when_the_failures_reach_the_threshold(self):
        machine = self.build(threshold=3)
        for _ in range(2):
            machine.apply(BreakerAction.FAILURE)
        self.assertIs(machine.state, BreakerState.CLOSED)
        machine.apply(BreakerAction.FAILURE)
        self.assertIs(machine.state, BreakerState.OPEN)

    def test_a_success_clears_the_failures(self):
        machine = self.build(threshold=3)
        machine.apply(BreakerAction.FAILURE)
        machine.apply(BreakerAction.SUCCESS)
        self.assertEqual(machine.failures, 0)

    def test_an_open_circuit_rejects_calls_until_the_timeout(self):
        machine = self.build(threshold=1, timeout=10.0)
        machine.apply(BreakerAction.FAILURE)
        self.assertFalse(machine.can(BreakerAction.CALL))
        self.clock.now = 9.9
        self.assertFalse(machine.can(BreakerAction.CALL))
        self.clock.now = 10.0
        self.assertTrue(machine.can(BreakerAction.CALL))

    def test_after_the_timeout_one_trial_call_is_let_through(self):
        machine = self.build(threshold=1, timeout=10.0)
        machine.apply(BreakerAction.FAILURE)
        self.clock.now = 10.0
        machine.apply(BreakerAction.CALL)
        self.assertIs(machine.state, BreakerState.HALF_OPEN)

    def test_a_trial_success_closes_and_a_trial_failure_reopens(self):
        machine = self.build(threshold=1, timeout=10.0)
        machine.apply(BreakerAction.FAILURE)
        self.clock.now = 10.0
        machine.apply(BreakerAction.CALL)
        machine.apply(BreakerAction.FAILURE)
        self.assertIs(machine.state, BreakerState.OPEN)
        self.clock.now = 20.0
        machine.apply(BreakerAction.CALL)
        machine.apply(BreakerAction.SUCCESS)
        self.assertIs(machine.state, BreakerState.CLOSED)

    def test_an_inadmissible_action_is_refused(self):
        machine = self.build(threshold=1)
        machine.apply(BreakerAction.FAILURE)
        with self.assertRaises(FaultToleranceException):
            machine.apply(BreakerAction.CALL)
        self.assertIs(machine.state, BreakerState.OPEN)

    def test_invalid_settings_are_refused(self):
        with self.assertRaises(FaultToleranceException):
            CircuitStateMachine(failure_threshold=0)
        with self.assertRaises(FaultToleranceException):
            CircuitStateMachine(reset_timeout=-1)

    def test_the_boundary_settings_are_accepted(self):
        CircuitStateMachine(failure_threshold=1, reset_timeout=0)

    def test_an_open_circuit_admits_no_result(self):
        machine = self.build(threshold=1)
        machine.apply(BreakerAction.FAILURE)
        self.assertFalse(machine.can(BreakerAction.SUCCESS))
        self.assertFalse(machine.can(BreakerAction.FAILURE))

    def test_closed_and_half_open_admit_a_result(self):
        machine = self.build(threshold=1, timeout=10.0)
        for action in (BreakerAction.SUCCESS, BreakerAction.FAILURE):
            self.assertTrue(machine.can(action))
        machine.apply(BreakerAction.FAILURE)
        self.clock.now = 10.0
        machine.apply(BreakerAction.CALL)
        for action in (BreakerAction.SUCCESS, BreakerAction.FAILURE):
            self.assertTrue(machine.can(action))

    def test_a_zero_timeout_lets_the_trial_through_at_once(self):
        machine = self.build(threshold=1, timeout=0.0)
        machine.apply(BreakerAction.FAILURE)
        self.assertTrue(machine.can(BreakerAction.CALL))

    def test_only_one_trial_call_is_in_flight(self):
        machine = self.build(threshold=1, timeout=10.0)
        machine.apply(BreakerAction.FAILURE)
        self.clock.now = 10.0
        machine.apply(BreakerAction.CALL)
        self.assertFalse(machine.can(BreakerAction.CALL))
        with self.assertRaises(FaultToleranceException):
            machine.apply(BreakerAction.CALL)
        machine.apply(BreakerAction.SUCCESS)
        self.assertTrue(machine.can(BreakerAction.CALL))

    def test_concurrent_calls_admit_exactly_one_trial(self):
        machine = self.build(threshold=1, timeout=0.0)
        machine.apply(BreakerAction.FAILURE)
        admitted, barrier = [], threading.Barrier(8)

        def attempt():
            barrier.wait()
            try:
                machine.apply(BreakerAction.CALL)
                admitted.append(1)
            except FaultToleranceException:
                pass

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(admitted), 1)

    def test_the_vocabulary_lives_in_enums(self):
        self.assertFalse(
            hasattr(ft, "BreakerAction") and ft.BreakerAction.__module__ == ft.__name__
        )
        self.assertEqual(BreakerAction.__module__, "wattleflow.enums.fault_tolerance")
        self.assertEqual(BreakerState.__module__, "wattleflow.enums.fault_tolerance")


class BreakerInvokerTest(unittest.TestCase):
    def build(self, operation, threshold=2, fallback=None):
        self.clock = Clock()
        machine = CircuitStateMachine(threshold, 10.0, clock=self.clock)
        invoker = CircuitBreakerInvoker(machine, command=operation, fallback=fallback, source="t")
        self.listener = Recorder()
        invoker.register_listener(self.listener)
        return invoker, machine

    def test_a_healthy_call_passes_through(self):
        invoker, machine = self.build(Operation())
        self.assertEqual(invoker.invoke(value=3), 3)
        self.assertIs(machine.state, BreakerState.CLOSED)

    def test_failures_open_the_circuit_and_each_change_is_reported(self):  # BR-FTL-25
        invoker, machine = self.build(Operation(failures=9), threshold=2)
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                invoker.invoke()
        self.assertIs(machine.state, BreakerState.OPEN)
        changed = [e for e in self.listener.events if e.type == CIRCUIT_STATE_CHANGED]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].payload, {"from": "closed", "to": "open"})

    def test_an_open_circuit_without_a_fallback_is_an_error(self):  # BR-FTL-24
        invoker, _ = self.build(Operation(failures=9), threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        with self.assertRaises(CircuitOpenError):
            invoker.invoke()
        self.assertEqual(self.listener.types()[-1], CIRCUIT_REJECTED)

    def test_an_open_circuit_answers_through_the_fallback_strategy(self):
        invoker, _ = self.build(Operation(failures=9), threshold=1, fallback=Fallback())
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        self.assertEqual(invoker.invoke(), "fallback")

    def test_the_circuit_closes_again_after_a_good_trial(self):
        operation = Operation(failures=1)
        invoker, machine = self.build(operation, threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        self.clock.now = 10.0
        self.assertEqual(invoker.invoke(), "ok")
        self.assertIs(machine.state, BreakerState.CLOSED)

    def test_a_rejection_reports_the_state_and_does_not_run_the_command(self):
        operation = Operation(failures=9)
        invoker, _ = self.build(operation, threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        with self.assertRaises(CircuitOpenError) as caught:
            invoker.invoke()
        self.assertEqual(operation.calls, 1)
        self.assertIs(caught.exception.caller, invoker)
        rejected = self.listener.events[-1]
        self.assertEqual((rejected.type, rejected.payload), (CIRCUIT_REJECTED, {"state": "open"}))

    def test_the_fallback_receives_the_arguments_of_the_call(self):
        class Echo(Fallback):
            __slots__ = ()

            def algorithm(self, caller, **kwargs):
                return kwargs

        invoker, _ = self.build(Operation(failures=9), threshold=1, fallback=Echo())
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        self.assertEqual(invoker.invoke(a=1), {"a": 1})

    def test_a_trial_reports_each_change_of_state(self):
        invoker, _ = self.build(Operation(failures=1), threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        self.clock.now = 10.0
        invoker.invoke()
        changes = [e.payload for e in self.listener.events if e.type == CIRCUIT_STATE_CHANGED]
        self.assertEqual(
            changes,
            [
                {"from": "closed", "to": "open"},
                {"from": "open", "to": "half_open"},
                {"from": "half_open", "to": "closed"},
            ],
        )

    def test_a_success_in_a_closed_circuit_reports_nothing(self):
        invoker, _ = self.build(Operation())
        invoker.invoke()
        self.assertEqual(self.listener.events, [])

    def test_the_exception_of_a_failed_call_passes_unchanged(self):
        error = RuntimeError("down")
        invoker, _ = self.build(Operation(failures=9, error=error))
        with self.assertRaises(RuntimeError) as caught:
            invoker.invoke()
        self.assertIs(caught.exception, error)

    def test_what_is_not_an_exception_is_never_caught_by_the_breaker(self):
        invoker, machine = self.build(Operation(failures=1, error=KeyboardInterrupt()))
        with self.assertRaises(KeyboardInterrupt):
            invoker.invoke()
        self.assertEqual((machine.state, machine.failures), (BreakerState.CLOSED, 0))

    def test_an_interrupted_trial_reopens_the_circuit(self):
        operation = Operation(failures=2)
        invoker, machine = self.build(operation, threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        operation.error = KeyboardInterrupt()
        self.clock.now = 10.0
        with self.assertRaises(KeyboardInterrupt):
            invoker.invoke()
        self.assertIs(machine.state, BreakerState.OPEN)

    def test_a_second_call_during_a_trial_is_rejected(self):
        gate, release = threading.Event(), threading.Event()

        class Slow(Operation):
            __slots__ = ()

            def execute(self, **kwargs):
                gate.set()
                release.wait(2)
                return "ok"

        invoker, machine = self.build(Operation(failures=1), threshold=1)
        with self.assertRaises(RuntimeError):
            invoker.invoke()
        invoker.set_command(Slow())
        self.clock.now = 10.0
        result = []
        thread = threading.Thread(target=lambda: result.append(invoker.invoke()))
        thread.start()
        gate.wait(2)
        with self.assertRaises(CircuitOpenError):
            invoker.invoke()
        release.set()
        thread.join()
        self.assertEqual(result, ["ok"])
        self.assertIs(machine.state, BreakerState.CLOSED)

    def test_without_a_command_it_says_so(self):
        invoker, machine = self.build(None)
        with self.assertRaisesRegex(FaultToleranceException, "No command set"):
            invoker.invoke()
        self.assertIs(machine.state, BreakerState.CLOSED)

    def test_invokers_stack_through_the_command_adapter(self):
        operation = Operation(failures=1)
        retry = RetryInvoker(RetryPolicy(base_delay=0), command=operation, sleep=lambda s: None)
        breaker, machine = self.build(InvokerCommand(retry), threshold=1)
        self.assertEqual(breaker.invoke(), "ok")
        self.assertEqual(operation.calls, 2)
        self.assertIs(machine.state, BreakerState.CLOSED)


class EventTest(unittest.TestCase):
    def test_an_event_keeps_its_payload_apart_from_the_caller(self):
        payload = {"n": 1}
        event = FaultEvent("retry.scheduled", payload, source="s", correlation_id="c")
        payload["n"] = 2
        event.payload["n"] = 3
        self.assertEqual(event.payload, {"n": 1})
        self.assertEqual(
            (event.source, event.correlation_id, event.type), ("s", "c", "retry.scheduled")
        )

    def test_an_event_is_stamped_in_the_workflow_zone_and_has_its_own_id(self):
        first, second = FaultEvent("a"), FaultEvent("a")
        self.assertIsNotNone(first.timestamp.utcoffset())
        expected = MomentAwareHelper.to_datetime(MomentAwareHelper.now()).utcoffset()
        self.assertEqual(first.timestamp.utcoffset(), expected)
        self.assertNotEqual(first.id, second.id)

    def test_an_event_has_a_name(self):
        self.assertEqual(FaultEvent("a").name, "FaultEvent")

    def test_a_listener_is_registered_once_and_can_leave(self):
        emitter, listener = EventEmitter("s"), Recorder()
        emitter.register_listener(listener)
        emitter.register_listener(listener)
        emitter.emit_event(FaultEvent("a"))
        self.assertEqual(len(listener.events), 1)
        emitter.unregister_listener(listener)
        emitter.emit_event(FaultEvent("b"))
        self.assertEqual(len(listener.events), 1)

    def test_a_listener_that_never_registered_can_leave(self):
        EventEmitter().unregister_listener(Recorder())

    def test_extra_keywords_do_not_change_the_delivery(self):
        emitter, listener = EventEmitter(), Recorder()
        emitter.register_listener(listener)
        emitter.emit_event(FaultEvent("a"), ignored=True)
        self.assertEqual(listener.types(), ["a"])

    def test_listeners_hear_events_in_registration_order(self):
        emitter, seen = EventEmitter(), []

        class Tag(Recorder):
            __slots__ = ("tag",)

            def __init__(self, tag):
                super().__init__()
                self.tag = tag

            def on_event(self, event):
                seen.append(self.tag)

        emitter.register_listener(Tag(1))
        emitter.register_listener(Tag(2))
        emitter.emit_event(FaultEvent("a"))
        self.assertEqual(seen, [1, 2])

    # BR-FTL-26
    def test_a_failing_listener_never_stops_the_others_or_the_operation(self):
        emitter, good = EventEmitter(), Recorder()

        class Broken(Recorder):
            __slots__ = ()

            def on_event(self, event):
                raise RuntimeError("listener down")

        emitter.register_listener(Broken())
        emitter.register_listener(good)
        with self.assertLogs("EventEmitter", level="WARNING") as logs:
            emitter.emit_event(FaultEvent("a"))
        self.assertEqual(len(good.events), 1)
        self.assertEqual(len(logs.records), 1)


if __name__ == "__main__":
    unittest.main()
