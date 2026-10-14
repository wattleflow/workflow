# Module name: concrete/fault_tolerance.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = [
    "RETRY_SCHEDULED",
    "RETRY_GAVE_UP",
    "CIRCUIT_STATE_CHANGED",
    "CIRCUIT_REJECTED",
    "FaultEvent",
    "EventEmitter",
    "RetryExhaustedError",
    "RetryPolicy",
    "RetryInvoker",
    "BreakerState",
    "BreakerAction",
    "CircuitOpenError",
    "CircuitStateMachine",
    "CircuitBreakerInvoker",
    "InvokerCommand",
]

import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from wattleflow.core.behavioural import ICommand, IInvoker, IStateMachine, IStrategy
from wattleflow.core.framework import IWattleflow
from wattleflow.core.transactional import IEvent, IEventListener, IEventSource

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Event types                                                          #
# --------------------------------------------------------------------------- #
RETRY_SCHEDULED = "retry.scheduled"
RETRY_GAVE_UP = "retry.gave_up"
CIRCUIT_STATE_CHANGED = "circuit.state_changed"
CIRCUIT_REJECTED = "circuit.rejected"
# --------------------------------------------------------------------------- #
# endregion Event types                                                       #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Events                                                               #
# --------------------------------------------------------------------------- #
class FaultEvent(IEvent):
    """
    FaultEvent - immutable IEvent emitted by fault tolerance invokers.

    id is a random hex UUID, timestamp is UTC at construction, payload is
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
        self._timestamp = datetime.now(timezone.utc)
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


class EventEmitter(IEventSource[IEvent]):
    """
    EventEmitter - IEventSource[IEvent] with an in-memory listener list.

    Registering the same listener twice has no effect; unregistering an
    unknown listener is ignored. emit_event() calls listeners synchronously
    in registration order and ignores **kwargs. A listener exception
    propagates to the caller of emit_event().
    """

    __slots__ = ("_listeners", "_source")

    def __init__(self, source: str | None = None) -> None:
        self._listeners: list[IEventListener[IEvent]] = []
        self._source = source

    def register_listener(self, listener: IEventListener[IEvent]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: IEventListener[IEvent]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit_event(self, event: IEvent, **kwargs: Any) -> None:
        for listener in tuple(self._listeners):
            listener.on_event(event)

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.emit_event(FaultEvent(event_type, payload, source=self._source))


def _require(command: ICommand | None) -> ICommand:
    if command is None:
        raise RuntimeError("No command set; call set_command() first.")
    return command


# --------------------------------------------------------------------------- #
# endregion Events                                                            #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Retry                                                                #
# --------------------------------------------------------------------------- #
class RetryExhaustedError(Exception):
    """Raised when a command failed and at least one retry was performed."""

    def __init__(self, attempts: int, last_error: BaseException) -> None:
        super().__init__(f"Operation failed after {attempts} attempts: {last_error!r}")
        self.attempts = attempts
        self.last_error = last_error


class RetryPolicy(IStrategy):
    """
    RetryPolicy - exponential backoff as an IStrategy.

    execute(caller, attempt=int, error=BaseException) returns the delay in
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
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if base_delay < 0 or max_delay < 0:
            raise ValueError("delays must be >= 0")
        if multiplier < 1:
            raise ValueError("multiplier must be >= 1")
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


class RetryInvoker(IInvoker, EventEmitter):
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

    __slots__ = ("_command", "_policy", "_sleep")

    def __init__(
        self,
        policy: IStrategy,
        *,
        command: ICommand | None = None,
        sleep: Callable[[float], None] = time.sleep,
        source: str | None = None,
    ) -> None:
        EventEmitter.__init__(self, source)
        self._policy = policy
        self._command = command
        self._sleep = sleep

    def set_command(self, command: ICommand) -> None:
        self._command = command

    def invoke(self, **kwargs: Any) -> Any:
        command = _require(self._command)
        attempt = 0
        while True:
            attempt += 1
            try:
                return command.execute(**kwargs)
            except Exception as error:
                delay = self._policy.algorithm(self, attempt=attempt, error=error)
                if delay is None:
                    self._publish(RETRY_GAVE_UP, {"attempts": attempt, "error": repr(error)})
                    if attempt == 1:
                        raise
                    raise RetryExhaustedError(attempt, error) from error
                self._publish(
                    RETRY_SCHEDULED,
                    {"attempt": attempt, "delay": delay, "error": repr(error)},
                )
                self._sleep(delay)


# --------------------------------------------------------------------------- #
# endregion Retry                                                             #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Circuit Breaker                                                      #
# --------------------------------------------------------------------------- #
class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerAction(str, Enum):
    CALL = "call"
    SUCCESS = "success"
    FAILURE = "failure"


class CircuitOpenError(Exception):
    """Raised when the circuit is open and no fallback is set."""


class CircuitStateMachine(IStateMachine[BreakerAction]):
    """
    CircuitStateMachine - IStateMachine[BreakerAction] for a circuit breaker.

    can(CALL) is True in CLOSED and HALF_OPEN, and in OPEN once reset_timeout
    seconds have passed since the circuit opened. can(SUCCESS/FAILURE) is
    True in any state except OPEN. apply() raises ValueError for an action
    can() rejects.

    apply(CALL) moves OPEN to HALF_OPEN. apply(SUCCESS) moves to CLOSED and
    resets the failure count. apply(FAILURE) opens the circuit from HALF_OPEN,
    and from CLOSED once failures reach failure_threshold.

    state and failures are read-only properties of this class; IStateMachine
    itself exposes no state. Not thread-safe.
    """

    __slots__ = ("_clock", "_failures", "_opened_at", "_reset_timeout", "_state", "_threshold")

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if reset_timeout < 0:
            raise ValueError("reset_timeout must be >= 0")
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._clock = clock
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    def can(self, action: BreakerAction) -> bool:
        if action is BreakerAction.CALL:
            if self._state is BreakerState.OPEN:
                return self._clock() - self._opened_at >= self._reset_timeout
            return True
        return self._state is not BreakerState.OPEN

    def apply(self, action: BreakerAction) -> None:
        if not self.can(action):
            raise ValueError(
                f"Action {action.value!r} is not admissible in state {self._state.value!r}"
            )
        if action is BreakerAction.CALL:
            if self._state is BreakerState.OPEN:
                self._state = BreakerState.HALF_OPEN
        elif action is BreakerAction.SUCCESS:
            self._state = BreakerState.CLOSED
            self._failures = 0
        elif self._state is BreakerState.HALF_OPEN:
            self._trip()
        else:
            self._failures += 1
            if self._failures >= self._threshold:
                self._trip()

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()


class CircuitBreakerInvoker(IInvoker, EventEmitter):
    """
    CircuitBreakerInvoker - IInvoker guarded by a CircuitStateMachine.

    invoke(**kwargs): if the machine rejects CALL, emits CIRCUIT_REJECTED and
    returns fallback.execute(self, **kwargs), or raises CircuitOpenError when
    no fallback is set. Otherwise applies CALL, runs command.execute(**kwargs),
    then applies SUCCESS or FAILURE; a failure's exception is re-raised. Every
    state change emits CIRCUIT_STATE_CHANGED with "from" and "to".
    """

    __slots__ = ("_command", "_fallback", "_machine")

    def __init__(
        self,
        machine: CircuitStateMachine,
        *,
        command: ICommand | None = None,
        fallback: IStrategy | None = None,
        source: str | None = None,
    ) -> None:
        EventEmitter.__init__(self, source)
        self._machine = machine
        self._command = command
        self._fallback = fallback

    def set_command(self, command: ICommand) -> None:
        self._command = command

    def invoke(self, **kwargs: Any) -> Any:
        command = _require(self._command)
        if not self._machine.can(BreakerAction.CALL):
            self._publish(CIRCUIT_REJECTED, {"state": self._machine.state.value})
            if self._fallback is not None:
                return self._fallback.execute(self, **kwargs)
            raise CircuitOpenError("Circuit is open; call rejected.")
        self._transition(BreakerAction.CALL)
        try:
            result = command.execute(**kwargs)
        except Exception:
            self._transition(BreakerAction.FAILURE)
            raise
        self._transition(BreakerAction.SUCCESS)
        return result

    def _transition(self, action: BreakerAction) -> None:
        before = self._machine.state
        self._machine.apply(action)
        after = self._machine.state
        if after is not before:
            self._publish(CIRCUIT_STATE_CHANGED, {"from": before.value, "to": after.value})


# --------------------------------------------------------------------------- #
# endregion Circuit Breaker                                                   #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Composition                                                          #
# --------------------------------------------------------------------------- #
class InvokerCommand(ICommand):
    """
    InvokerCommand - adapts an IInvoker to ICommand.

    execute(**kwargs) returns invoker.invoke(**kwargs), so invokers can be
    stacked, e.g. CircuitBreakerInvoker -> RetryInvoker -> operation.
    """

    __slots__ = ("_invoker",)

    def __init__(self, invoker: IInvoker) -> None:
        self._invoker = invoker

    def execute(self, **kwargs: Any) -> Any:
        return self._invoker.invoke(**kwargs)


# --------------------------------------------------------------------------- #
# endregion Composition                                                       #
# --------------------------------------------------------------------------- #
