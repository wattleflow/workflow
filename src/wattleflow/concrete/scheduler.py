# Module Name: concrete/scheduler.py
# Description: This modul contains scheduler classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

"""
The Scheduler class:
- Manage task execution using existing strategies and pipelines.
- Use event-driven behavior from the observer pattern.
- Support asynchronous execution and cron-like scheduling.

"""

import threading
from abc import ABC
from logging import NOTSET, Handler
from typing import Optional
from wattleflow.core import IEventListener, IScheduler
from wattleflow.concrete import AuditLogger
from wattleflow.constants.enums import Event

PERMITED_SLOTS = (
    "_lock",
    "_initialized",
    "_running",
    "_counter",
    "_listeners",
    "_tasks",
    "_orchestrator",
    "_config",
)


class Scheduler(IScheduler, AuditLogger, ABC):
    """
    Scheduler class for managing periodic and event-driven task execution.
    Utilizes event-driven execution with event listeners and supports strategy-based scheduling.
    """

    __slots__ = PERMITED_SLOTS

    @property
    def count(self) -> int:
        return self._counter

    def __init__(
        self, level: int = NOTSET, handler: Optional[Handler] = None, *args, **kwargs
    ):
        IScheduler.__init__(self, *args, **kwargs)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            name=self.name,
            level=level,
            handler=handler,
            *args,
            **kwargs,
        )

        if not hasattr(self, "_initialized"):
            self._lock = threading.Lock()
            self._initialized = True
            self._running = False
            self._counter = 0
            self._listeners = []
            self._tasks = []
            self._orchestrator = None

            from wattleflow.helpers.preset import Preset

            self._preset: Preset = Preset()
            self._preset.configure(caller=self, raise_errors=True, **kwargs)
            self.setup_orchestrator()

    def setup_orchestrator(self) -> None:
        self.debug(msg=Event.Configuring.value, name=self.name)

        # with self._lock:
        #     if self._orchestrator is None:

        # config: Config = self.load_config(config_path)
        # connection_manager: ConnectionManager = ConnectionManager(
        #     **config["connection_manager"]
        # )
        # strategy = config.get("strategy")

        # self._orchestrator = Orchestrator(connection_manager, strategy)

        # # Emit event when orchestrator is set up
        # self.emit_event("OrchestratorSetup", config=config)

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
