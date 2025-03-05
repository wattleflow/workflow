# Module Name: core/concrete/scheduler.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul has Scheduler class.

"""
# Example strategy
class SampleStrategy(StrategyExecuteTask):
    def execute(self, **kwargs):
        print(
            f"[{datetime.now()}] Executing strategy task: \
              {kwargs.get('task_name', 'Unnamed Task')}")

# Example listener
class TaskListener(IWattleflow)
    def on_event(self, event, **kwargs):
        print(f"Event Triggered: {event} - {kwargs}")

# Define a sample task
def sample_task():
    print(f"[{datetime.now()}] Running scheduled task...")

# Initialize scheduler
scheduler = Scheduler(strategy_execute=SampleStrategy())

# Register event listener
listener = TaskListener()
scheduler.register_listener(listener)

# Schedule a repeating task every 5 seconds
scheduler.schedule_task(sample_task, interval=5, repeat=True)

# Start the scheduler
scheduler.start()

# Allow tasks to run for 20 seconds before stopping
time.sleep(20)
scheduler.stop()
"""

import time
import threading
from datetime import datetime
from wattleflow.core import IEventSource, IEventListener, IStrategy, IFacade
from wattleflow.concrete import Attribute, ManagedException
from wattleflow.constants.enums import Event
from wattleflow.helpers.functions import name_class


class Scheduler(IEventSource, IFacade, Attribute):
    """
    Scheduler class for managing periodic and event-driven task execution.
    Utilizes event-driven execution with event listeners and supports strategy-based scheduling.
    """

    def __init__(self, strategy_execute: IStrategy = None):
        super().__init__()
        self._listeners = []
        self._tasks = []
        self._running = False
        self._strategy_execute = strategy_execute

    def register_listener(self, listener: IEventListener) -> None:
        """Registers an event listener."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def emit_event(self, event, **kwargs):
        """Notifies all listeners of an event."""
        for listener in self._listeners:
            listener.on_event(event, **kwargs)

    def schedule_task(self, task, interval: int, repeat: bool = True):
        """
        Schedule a task for execution.

        Args:
            task (callable): The function or method to execute.
            interval (int): Time in seconds between executions.
            repeat (bool): Whether the task should repeat indefinitely.
        """
        if not callable(task):
            raise TypeError(f"Expected a callable task, got {type(task).__name__}")

        self._tasks.append((task, interval, repeat))

    def _execute_task(self, task, interval, repeat):
        """Executes a task based on the provided interval and repetition settings."""
        try:
            while repeat and self._running:
                start_time = datetime.now()
                task()
                end_time = datetime.now()

                execution_time = (end_time - start_time).total_seconds()
                sleep_time = max(0, interval - execution_time)

                self.emit_event(
                    Event.TaskExecuted, task=name_class(task), duration=execution_time
                )

                time.sleep(sleep_time)
        except Exception as e:
            raise ManagedException(
                self, f"Error executing task {name_class(task)}: {e}"
            )

    def start(self):
        """Starts the scheduler."""
        self._running = True
        for task, interval, repeat in self._tasks:
            thread = threading.Thread(
                target=self._execute_task, args=(task, interval, repeat), daemon=True
            )
            thread.start()

        self.emit_event(Event.SchedulerStarted)

    def stop(self):
        """Stops the scheduler."""
        self._running = False
        self.emit_event(Event.SchedulerStopped)

    def execute_strategy(self, **kwargs):
        """Executes a strategy-based task if a strategy is defined."""
        if not self._strategy_execute:
            raise ManagedException(self, "No execution strategy defined.")
        self._strategy_execute.execute(**kwargs)
