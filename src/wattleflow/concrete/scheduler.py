# Module Name: concrete/scheduler.py
# Description: This modul contains scheduler classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

"""
The Scheduler class:
- Manage task execution using existing strategies and pipelines.
- Use event-driven behavior from the observer pattern.
- Support asynchronous execution and cron-like scheduling.

"""

import threading
from abc import abstractmethod
from wattleflow.core import IEventListener, IScheduler
from wattleflow.concrete import Attribute, ConnectionManager, Orchestrator
from wattleflow.constants.enums import Event


class Scheduler(IScheduler, Attribute):
    """
    Scheduler class for managing periodic and event-driven task execution.
    Utilizes event-driven execution with event listeners and supports strategy-based scheduling.
    """

    @property
    def count(self) -> int:
        return self._counter

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._lock = threading.Lock()
            self._initialized = True
            self._running = False
            self._counter = 0
            self._listeners = []
            self._tasks = []
            self._orchestrator = None
            self._config = None
            self.load_config()

    @abstractmethod
    def load_config(self, *args, **kwargs):
        pass

    def setup_orchestrator(self, config_path: str):
        with self._lock:
            if self._orchestrator is None:
                config = self.load_config(config_path)
                connection_manager = ConnectionManager(**config["connection_manager"])
                strategy = config.get("strategy")

                self._orchestrator = Orchestrator(connection_manager, strategy)

                # Emit event when orchestrator is set up
                self.emit_event("OrchestratorSetup", config=config)

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
