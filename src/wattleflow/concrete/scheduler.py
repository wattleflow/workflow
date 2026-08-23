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
        "_tasks",
        "_orchestrator",
        "_config",
    )

    @property
    def count(self) -> int:
        return self._counter

    def __init__(self, level: int, handler: Handler | None = None, **kwargs):
        super().__init__(level=level, handler=handler, **kwargs)

        self.debug(
            msg=Event.Constructor.name,
            name=self.name,
            level=level,
            handler=handler,
            kwargs=kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        if not hasattr(self, "_initialised"):
            self._lock = threading.Lock()
            self._initialised = True
            self._running = False
            self._counter = 0
            self._listeners = []
            self._tasks = []
            self._orchestrator = None

            self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

            self.setup_orchestrator()

    def setup_orchestrator(self) -> None:
        self.debug(msg=Event.Configuring.name, name=self.name)

    def start_orchestration(self, parallel: bool = False):
        with self._lock:
            if self._orchestrator:
                self.emit_event(Event.Started)
                self._orchestrator.start(parallel)
                self.emit_event(Event.Completed)

    def stop_orchestration(self):
        with self._lock:
            if self._orchestrator:
                self.emit_event(Event.Stopped)
                self._orchestrator.stop()

    # Event Source Pattern Implementation
    def register_listener(self, listener: IEventListener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def emit_event(self, event: Event, **kwargs):
        with self._lock:
            for listener in self._listeners:
                listener.on_event(event, **kwargs)

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        return getattr(self._preset, name)


# --------------------------------------------------------------------------- #
# endregion Schedulers                                                        #
# --------------------------------------------------------------------------- #


__all__ = ["Scheduler"]
