# Module name: scheduler.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import threading
from abc import ABC
from logging import Handler
from typing import Any
from wattleflow.core import IEventListener, IScheduler
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Schedulers                                                           #
# --------------------------------------------------------------------------- #


class Scheduler(Wattleflow, IScheduler, ABC):
    """
    Scheduler class for managing periodic and event-driven task execution.
    Utilizes event-driven execution with event listeners and supports strategy-based scheduling.
    """

    __slots__ = (
        "_lock",
        "_initialised",
        "_running",
        "_counter",
        "_listeners",
        "_orchestrator",
        "_preset",
    )

    @property
    def count(self) -> int:
        """Orchestrations that ran to completion; a failed one is not counted."""
        return self._counter

    @property
    def running(self) -> bool:
        return self._running

    def __init__(self, level: int, handler: Handler | None = None, **kwargs):
        # The base constructor audits under `self._lock`, and `__slots__` above
        # shadows the class-level lock it would otherwise inherit from Audit, so
        # the instance lock has to exist before the base runs. Reentrant because
        # start_orchestration/stop_orchestration hold it and then call emit_event,
        # which takes it again.
        if not hasattr(self, "_lock"):
            self._lock = threading.RLock()

        super().__init__(level=level, handler=handler, **kwargs)

        self.debug(
            msg=Event.Constructor,
            name=self.name,
            level=level,
            handler=handler,
            kwargs=kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        if not hasattr(self, "_initialised"):
            self._initialised = True
            self._running = False
            self._counter = 0
            self._listeners = []
            self._orchestrator = None

            self.setup_orchestrator()

    def setup_orchestrator(self) -> None:
        self.debug(msg=Event.Configuring, name=self.name)

    # The lock guards state, never the orchestrator's run: a start that held it for the whole run
    # would make stop_orchestration wait for the very thing it is meant to stop.
    def start_orchestration(self, parallel: bool = False):
        with self._lock:
            orchestrator = self._orchestrator
            if orchestrator is None or self._running:
                return
            self._running = True
        self.emit_event(Event.Started)
        try:
            orchestrator.start(parallel)
        except Exception as error:
            # Started is always closed: Completed on success, Failed otherwise.
            self.emit_event(Event.Failed, error=str(error))
            raise
        finally:
            with self._lock:
                self._running = False
        with self._lock:
            self._counter += 1
        self.emit_event(Event.Completed)

    def stop_orchestration(self):
        with self._lock:
            orchestrator = self._orchestrator
        if orchestrator is None:
            return
        self.emit_event(Event.Stopped)
        orchestrator.stop()

    # Event Source Pattern Implementation
    def register_listener(self, listener: IEventListener) -> None:
        with self._lock:
            # Identity, not ==: a listener is registered as an object, so two equal ones are two.
            if not any(known is listener for known in self._listeners):
                self._listeners.append(listener)

    def emit_event(self, event: Event, **kwargs):
        with self._lock:
            listeners = list(self._listeners)
        # Delivery is outside the lock and isolated: a listener may register another or call
        # back into the scheduler, and one that fails must not hide the event from the rest
        # (SchedulerCronJob emits its error event from inside the handler of that very error).
        for listener in listeners:
            try:
                listener.on_event(event, **kwargs)
            except Exception as error:
                self.exception(
                    msg=Event.Notify,
                    reason="Listener raised during on_event",
                    listener=listener,
                    error=str(error),
                )

    # Must be implemented if using PresetDecorator.
    # The guards matter during construction: the base constructor touches
    # attributes before `_preset` exists, and an unguarded lookup re-enters this
    # hook looking for `_preset` itself, which recurses until the stack ends.
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            preset = object.__getattribute__(self, "_preset")
        except AttributeError:
            raise AttributeError(name) from None
        return getattr(preset, name)


# --------------------------------------------------------------------------- #
# endregion Schedulers                                                        #
# --------------------------------------------------------------------------- #


__all__ = ["Scheduler"]
