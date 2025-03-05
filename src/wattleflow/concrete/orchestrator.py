# Module Name: core/concrete/orchestrator.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul has Orchestrator class.
"""
Orchestrator Implementation for WattleFlow Workflow
The Orchestrator class will:
    - Manage and coordinate multiple processors within a workflow.
    - Ensure connection management is shared across processors.
    - Execute processors sequentially or in parallel.
    - Monitor and log execution using event-driven behavior.
    - Utilize pipelines for structured data flow.


Usage example:

class SampleProcessor:
    def process_tasks(self):
        print(f"[{datetime.now()}] Processing tasks in {self.__class__.__name__}...")
        time.sleep(2)

# Example Event Listener
class EventLogger:
    def on_event(self, event, **kwargs):
        print(f"Event: {event} - {kwargs}")

# Example Strategy
class SampleStrategy(StrategyExecuteTask):
    def execute(self, **kwargs):
        print(f"[{datetime.now()}] Executing strategy task: \
             {kwargs.get('task_name', 'Unnamed Task')}")

# Initialize Orchestrator with a connection manager
connection_manager = ConnectionClass()
orchestrator = Orchestrator(connection_manager, strategy_execute=SampleStrategy())

# Register event listener
event_logger = EventLogger()
orchestrator.register_listener(event_logger)

# Add processors
orchestrator.add_processor(SampleProcessor())
orchestrator.add_processor(SampleProcessor())

# Start orchestration in parallel mode
orchestrator.start(parallel=True)

# Stop orchestration after execution
orchestrator.stop()
"""

import threading
from datetime import datetime
from wattleflow.core import IFacade, IEventSource, IEventListener, IStrategy
from wattleflow.constants.enums import Event
from wattleflow.helpers.functions import name_class
from wattleflow.concrete import (
    ConnectionManager,
    ManagedException,
    GenericProcessor,
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

    def register_listener(self, listener: IEventListener) -> None:
        """Registers an event listener for monitoring execution."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def emit_event(self, event: Event, **kwargs):
        """Notifies all listeners of an event."""
        for listener in self._listeners:
            listener.on_event(event, **kwargs)

    def add_processor(self, processor: GenericProcessor):
        """
        Adds a processor to the orchestrator.
        Ensures the processor has the `process_tasks()` method.
        """
        if not hasattr(processor, "process_tasks"):
            raise TypeError(
                f"Processor {name_class(processor)} is missing `process_tasks()` method."
            )

        self._processors.append(processor)

    def _execute_processor(self, processor):
        """Executes a processor and logs execution time."""
        try:
            start_time = datetime.now()
            processor.process_tasks()
            end_time = datetime.now()

            execution_time = (end_time - start_time).total_seconds()
            self.emit_event(
                Event.ProcessorExecuted,
                processor=name_class(processor),
                duration=execution_time,
            )

        except Exception as e:
            raise ManagedException(
                self, f"Error processing {name_class(processor)}: {e}"
            )

    def start(self, parallel: bool = False):
        """Starts processor execution (sequentially or in parallel)."""
        self._running = True
        self.emit_event(Event.OrchestrationStarted)

        if parallel:
            threads = []
            for processor in self._processors:
                thread = threading.Thread(
                    target=self._execute_processor, args=(processor,), daemon=True
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()
        else:
            for processor in self._processors:
                self._execute_processor(processor)

        self.emit_event(Event.OrchestrationCompleted)

    def stop(self):
        """Stops the orchestrator."""
        self._running = False
        self.emit_event(Event.OrchestrationStopped)

    def execute_strategy(self, **kwargs):
        """Executes a strategy-based processing task if defined."""
        if not self._strategy_execute:
            raise ManagedException(self, "No execution strategy defined.")
        self._strategy_execute.execute(**kwargs)
