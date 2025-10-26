# Module name: orchestrator.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Orchestrator Implementation for WattleFlow Workflow
The Orchestrator class will:
    - Manage and coordinate multiple processors within a workflow.
    - Ensure connection management is shared across processors.
    - Execute processors sequentially or in parallel.
    - Monitor and log execution using event-driven behavior.
    - Utilize pipelines for structured data flow.

"""


from __future__ import annotations
import threading
from datetime import datetime
from wattleflow.core import (
    IFacade,
    IEventSource,
    IEventListener,
    IProcessor,
    IStrategy,
)
from wattleflow.constants.enums import (
    Event,
    Operation,
)
from wattleflow.concrete import (
    OrchestratorException,
    ConnectionManager,
)


class Orchestrator(IEventSource, IFacade):
    """
    Orchestrator for managing and coordinating processors.
    Ensures processors share a connection manager and executes processing
    sequentially or in parallel.
    """

    def __init__(
        self, connection_manager: ConnectionManager, strategy_execute: IStrategy = None
    ):
        super().__init__()
        self._listeners = []
        self._processors = []
        self._running = False
        self._connection_manager = connection_manager
        self._strategy_execute = strategy_execute

    def _start_processor(self, processor: IProcessor):
        try:
            start_time = datetime.now()
            processor.process_tasks()
            end_time = datetime.now()

            execution_time = (end_time - start_time).total_seconds()
            self.emit_event(
                Event.Processed,
                processor=processor.name,
                duration=execution_time,
            )

        except Exception as e:
            raise OrchestratorException(
                self,
                "Error processing {}: {}".format(
                    getattr(processor, "name", "unknown"), e
                ),
            )

    def add_processor(self, processor: IProcessor):
        """
        Ensures the processor has the `process_tasks()` method.
        """
        if not hasattr(processor, "process_tasks"):
            raise TypeError(
                "Processor {} is missing `process_tasks()` method.".format(
                    getattr(processor, "name", "unknown"),
                )
            )

        self._processors.append(processor)

    def emit_event(self, event: Event, **kwargs):
        for listener in self._listeners:
            listener.on_event(event, **kwargs)

    def register_listener(self, listener: IEventListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def operation(self, action: Operation):
        if action == Operation.Start:
            self.start()
        elif action == Operation.Stop:
            self.stop()
        else:
            msg = f"{type(self).__name__}: Unrecognised operation! [{action}]"
            raise ChildProcessError(msg)

    def start(self, parallel: bool = False):
        """Starts processor execution (sequentially or in parallel)."""
        self._running = True
        self.emit_event(Event.OrchestrationStarted)

        if parallel:
            threads = []
            for processor in self._processors:
                thread = threading.Thread(
                    target=self._start_processor, args=(processor,), daemon=True
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()
        else:
            for processor in self._processors:
                self._start_processor(processor)

        self.emit_event(Event.OrchestrationCompleted)

    def stop(self):
        self._running = False
        self.emit_event(Event.OrchestrationStopped)


if __name__ == "__main__":
    import gc
    import unittest

    unittest.main()
    gc.collect()
