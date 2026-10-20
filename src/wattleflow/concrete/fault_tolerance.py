# Module name: concrete/fault_tolerance.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = [
    "FaultToleranceException",
    "FaultEvent",
    "EventEmitter",
    "GenericInvoker",
    "RetryExhaustedError",
    "RetryPolicy",
    "RetryInvoker",
    "CircuitOpenError",
    "CircuitStateMachine",
    "CircuitBreakerInvoker",
    "InvokerCommand",
]

import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import AuditException
from wattleflow.constants.fault_tolerance import (
    CIRCUIT_REJECTED,
    CIRCUIT_STATE_CHANGED,
    RETRY_GAVE_UP,
    RETRY_SCHEDULED,
)
from wattleflow.core.behavioural import ICommand, IInvoker, IStateMachine, IStrategy
from wattleflow.core.framework import IWattleflow
from wattleflow.core.transactional import IEvent, IEventListener, IEventSource
from wattleflow.enums.event import Event
from wattleflow.enums.fault_tolerance import BreakerAction, BreakerState
from wattleflow.helpers.moment import MomentAwareHelper

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"

# --------------------------------------------------------------------------- #
# region Events                                                               #
# --------------------------------------------------------------------------- #
class FaultEvent(IEvent):
    """
    FaultEvent - immutable IEvent emitted by fault tolerance invokers.

    id is a random hex UUID, timestamp is the workflow-zone moment at construction, payload is
    copied on construction and on every read.
    """

    __slots__ = (
        "_correlation_id",
        "_id",
        "_payload",
        "_source",
        "_timestamp",
        "_type",
    )

    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    def __init__(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self._id = uuid.uuid4().hex
        self._correlation_id = correlation_id
        self._source = source
        self._timestamp = MomentAwareHelper.to_datetime(MomentAwareHelper.now())
        self._type = event_type
        self._payload = dict(payload or {})

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def source(self) -> str | None:
        return self._source

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def type(self) -> str:
        return self._type

    @property
    def payload(self) -> dict[str, Any]:
        return dict(self._payload)


class EventEmitter(Wattleflow, IEventSource[IEvent]):
    """
    EventEmitter - IEventSource[IEvent] with an in-memory listener list.

    Registering the same listener twice has no effect; unregistering an
    unknown listener is ignored. emit_event() calls listeners synchronously
    in registration order and ignores **kwargs. A listener exception is logged
    as a warning and never reaches the other listeners or the caller (BR-FTL-26).
    """

    __slots__ = ("_listeners", "_source")

    def __init__(self, source: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._listeners: list[IEventListener[IEvent]] = []
        self._source = source

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.emit_event(FaultEvent(event_type, payload, source=self._source))

    def register_listener(self, listener: IEventListener[IEvent]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: IEventListener[IEvent]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit_event(self, event: IEvent, **kwargs: Any) -> None:
        for listener in tuple(self._listeners):
            try:
                listener.on_event(event)
            except Exception as error:
                self.warning(
                    msg=Event.Emit,
                    step=Event.Failed,
                    listener=type(listener).__name__,
                    event=event.type,
                    error=type(error).__name__,
                )


# --------------------------------------------------------------------------- #
# endregion Events                                                            #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Retry                                                                #
# --------------------------------------------------------------------------- #


class FaultToleranceException(AuditException):
    """Root of the fault tolerance exceptions."""


class RetryExhaustedError(FaultToleranceException):
    """Raised when a command failed and at least one retry was performed."""

    def __init__(self, caller: object, attempts: int, last_error: BaseException) -> None:
        super().__init__(
            caller, f"Operation failed after {attempts} attempts: {last_error!r}", exc=last_error
        )
        self.attempts = attempts
        self.last_error = last_error


class RetryPolicy(Wattleflow, IStrategy):
    """
    RetryPolicy - exponential backoff as an IStrategy.

    algorithm(caller, attempt=int, error=BaseException) returns the delay in
    seconds before the next attempt, or None when no further attempt is
    allowed (attempt limit reached, or error is not an instance of retry_on).
    Delay = min(base_delay * multiplier ** (attempt - 1), max_delay).
    """

    __slots__ = ("_base_delay", "_max_attempts", "_max_delay", "_multiplier", "_retry_on")

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.1,
        multiplier: float = 2.0,
        max_delay: float = 30.0,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        if max_attempts < 1:
            raise FaultToleranceException(self, "max_attempts must be >= 1")
        if base_delay < 0 or max_delay < 0:
            raise FaultToleranceException(self, "delays must be >= 0")
        if multiplier < 1:
            raise FaultToleranceException(self, "multiplier must be >= 1")
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._multiplier = multiplier
        self._max_delay = max_delay
        self._retry_on = retry_on

    def algorithm(self, caller: IWattleflow, **kwargs: Any) -> float | None:
        attempt = int(kwargs["attempt"])
        error = kwargs["error"]
        if attempt >= self._max_attempts or not isinstance(error, self._retry_on):
            return None
        return min(self._base_delay * self._multiplier ** (attempt - 1), self._max_delay)


class GenericInvoker(EventEmitter, IInvoker):
    """
    GenericInvoker - EventEmitter that holds the ICommand an IInvoker runs.

    invoke() is left to the subclass. _require_command() raises
    FaultToleranceException when no command has been set.
    """

    __slots__ = ("_command",)

    def __init__(
        self,
        *,
        command: ICommand | None = None,
        source: str | None = None,
        **kwargs: Any,
    ) -> None:
        EventEmitter.__init__(self, source, **kwargs)
        self._command = command

    def set_command(self, command: ICommand) -> None:
        self._command = command

    def _require_command(self) -> ICommand:
        if self._command is None:
            raise FaultToleranceException(self, "No command set; call set_command() first.")
        return self._command


class RetryInvoker(GenericInvoker):
    """
    RetryInvoker - IInvoker that re-executes its ICommand on failure.

    invoke(**kwargs) forwards kwargs to command.execute(). On an Exception it
    asks the policy for a delay; a float emits RETRY_SCHEDULED, sleeps and
    retries, None emits RETRY_GAVE_UP and stops. When stopping on the first
    attempt the original exception is re-raised; after one or more retries
    RetryExhaustedError is raised, chained to the last exception.
    BaseException subclasses that are not Exception (e.g. KeyboardInterrupt)
    are never caught. The command is assumed to be safe to repeat.
    """

    __slots__ = ("_policy", "_sleep")

    def __init__(
        self,
        policy: IStrategy,
        *,
        command: ICommand | None = None,
        sleep: Callable[[float], None] = time.sleep,
        source: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(command=command, source=source, **kwargs)
        self._policy = policy
        self._sleep = sleep

    def invoke(self, **kwargs: Any) -> Any:
        command = self._require_command()
        attempt = 0
        while True:
            attempt += 1
            try:
                return command.execute(**kwargs)
            except Exception as error:
                delay = self._policy.algorithm(self, attempt=attempt, error=error)
                if delay is None:
                    self._publish(RETRY_GAVE_UP, {"attempts": attempt, "error": type(error).__name__})
                    self.debug(
                        msg=Event.Execute,
                        step=Event.Failed,
                        attempts=attempt,
                        error=type(error).__name__,
                    )
                    if attempt == 1:
                        raise
                    raise RetryExhaustedError(self, attempt, error) from error
                self._publish(
                    RETRY_SCHEDULED,
                    {"attempt": attempt, "delay": delay, "error": type(error).__name__},
                )
                self._sleep(delay)


# --------------------------------------------------------------------------- #
# endregion Retry                                                             #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Circuit Breaker                                                      #
# --------------------------------------------------------------------------- #


class CircuitOpenError(FaultToleranceException):
    """Raised when the circuit is open and no fallback is set; cardinal for the processor (BR-FTL-24)."""


class CircuitStateMachine(Wattleflow, IStateMachine[BreakerAction]):
    """
    CircuitStateMachine - IStateMachine[BreakerAction] for a circuit breaker.

    can(CALL) is True in CLOSED, in OPEN once reset_timeout seconds have
    passed since the circuit opened, and in HALF_OPEN while no trial call is
    in flight. can(SUCCESS/FAILURE) is True in any state except OPEN. apply()
    raises FaultToleranceException for an action can() rejects.

    apply(CALL) moves OPEN to HALF_OPEN and marks the trial call in flight.
    apply(SUCCESS) moves to CLOSED and resets the failure count. apply(FAILURE)
    opens the circuit from HALF_OPEN, and from CLOSED once failures reach
    failure_threshold. SUCCESS and FAILURE end the trial call.

    state and failures are read-only properties of this class; IStateMachine
    itself exposes no state. can() and apply() are atomic under one lock.
    """

    __slots__ = ("_clock", "_failures", "_guard", "_opened_at", "_reset_timeout", "_state", "_threshold", "_trial")

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        if failure_threshold < 1:
            raise FaultToleranceException(self, "failure_threshold must be >= 1")
        if reset_timeout < 0:
            raise FaultToleranceException(self, "reset_timeout must be >= 0")
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._clock = clock
        self._guard = threading.Lock()
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._trial = False

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    def can(self, action: BreakerAction) -> bool:
        with self._guard:
            return self._admits(action)

    def apply(self, action: BreakerAction) -> None:
        with self._guard:
            if not self._admits(action):
                raise FaultToleranceException(
                    self,
                    f"Action {action.value!r} is not admissible in state {self._state.value!r}",
                )
            if action is BreakerAction.CALL:
                if self._state is BreakerState.OPEN:
                    self._state = BreakerState.HALF_OPEN
                if self._state is BreakerState.HALF_OPEN:
                    self._trial = True
            elif action is BreakerAction.SUCCESS:
                self._state = BreakerState.CLOSED
                self._failures = 0
                self._trial = False
            else:
                self._trial = False
                if self._state is BreakerState.HALF_OPEN:
                    self._trip()
                else:
                    self._failures += 1
                    if self._failures >= self._threshold:
                        self._trip()

    def _admits(self, action: BreakerAction) -> bool:
        if action is BreakerAction.CALL:
            if self._state is BreakerState.OPEN:
                return self._clock() - self._opened_at >= self._reset_timeout
            if self._state is BreakerState.HALF_OPEN:
                return not self._trial
            return True
        return self._state is not BreakerState.OPEN

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()


class CircuitBreakerInvoker(GenericInvoker):
    """
    CircuitBreakerInvoker - IInvoker guarded by a CircuitStateMachine.

    invoke(**kwargs): if the machine rejects CALL, emits CIRCUIT_REJECTED and
    returns fallback.algorithm(self, **kwargs), or raises CircuitOpenError when
    no fallback is set. Otherwise applies CALL, runs command.execute(**kwargs),
    then applies SUCCESS or FAILURE; a failure's exception is re-raised. Every
    state change emits CIRCUIT_STATE_CHANGED with "from" and "to". A trial
    call cut short by a BaseException that is not an Exception reopens the circuit.
    """

    __slots__ = ("_fallback", "_guard", "_machine")

    def __init__(
        self,
        machine: CircuitStateMachine,
        *,
        command: ICommand | None = None,
        fallback: IStrategy | None = None,
        source: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(command=command, source=source, **kwargs)
        self._machine = machine
        self._fallback = fallback
        self._guard = threading.Lock()

    def _transition(self, action: BreakerAction) -> None:
        with self._guard:
            before = self._machine.state
            self._machine.apply(action)
            after = self._machine.state
        if after is not before:
            self._publish(CIRCUIT_STATE_CHANGED, {"from": before.value, "to": after.value})

    def _admit(self) -> bool:
        if not self._machine.can(BreakerAction.CALL):
            return False
        try:
            self._transition(BreakerAction.CALL)
        except FaultToleranceException:
            return False
        return True

    def invoke(self, **kwargs: Any) -> Any:
        command = self._require_command()
        if not self._admit():
            self._publish(CIRCUIT_REJECTED, {"state": self._machine.state.value})
            if self._fallback is not None:
                return self._fallback.algorithm(self, **kwargs)
            raise CircuitOpenError(self, "Circuit is open; call rejected.")
        try:
            result = command.execute(**kwargs)
        except Exception as error:
            self._transition(BreakerAction.FAILURE)
            self.debug(msg=Event.Execute, step=Event.Failed, error=type(error).__name__)
            raise
        except BaseException as error:
            if self._machine.state is BreakerState.HALF_OPEN:
                self._transition(BreakerAction.FAILURE)
            self.debug(msg=Event.Execute, step=Event.Failed, error=type(error).__name__)
            raise
        self._transition(BreakerAction.SUCCESS)
        return result


# --------------------------------------------------------------------------- #
# endregion Circuit Breaker                                                   #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Composition                                                          #
# --------------------------------------------------------------------------- #


class InvokerCommand(Wattleflow, ICommand):
    """
    InvokerCommand - adapts an IInvoker to ICommand.
    execute(**kwargs) returns invoker.invoke(**kwargs), so invokers can be
    stacked, e.g. CircuitBreakerInvoker -> RetryInvoker -> operation.
    """

    __slots__ = ("_invoker",)

    def __init__(self, invoker: IInvoker, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._invoker = invoker

    def execute(self, **kwargs: Any) -> Any:
        return self._invoker.invoke(**kwargs)


# --------------------------------------------------------------------------- #
# endregion Composition                                                       #
# --------------------------------------------------------------------------- #
