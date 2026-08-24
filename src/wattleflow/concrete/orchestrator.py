# Module name: concrete/orchestrator.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
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

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import threading
from wattleflow.helpers.dtime import Now
from wattleflow.core import (
    IFacade,
    IEventSource,
    IEventListener,
    IProcessor,
    IStrategy,
)
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation
from wattleflow.concrete.manager import ConnectionManager
from wattleflow.concrete.exception import OrchestratorException
from wattleflow.concrete.base import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Orchestrators                                                        #
# --------------------------------------------------------------------------- #


class Orchestrator(Wattleflow, IEventSource, IFacade):
    def __init__(
        self,
        connection_manager: ConnectionManager,
        strategy_execute: IStrategy | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._listeners: list[IEventListener] = []
        self._processors: list[IProcessor] = []
        self._running: bool = False
        self._connection_manager = connection_manager
        self._strategy_execute = strategy_execute
        self._emit_lock = threading.Lock()

    # region Internal

    def _start_processor(self, processor: IProcessor) -> None:
        proc_name = getattr(processor, "name", "unknown")
        try:
            start_time = Now.utc()
            # IProcessor contract uses start(); fall back to operation(Start)
            # if a custom processor only exposes the facade signature.
            if callable(getattr(processor, "start", None)):
                processor.start()
            elif callable(getattr(processor, "operation", None)):
                processor.operation(Operation.Start)
            else:
                raise TypeError(f"Processor {proc_name!r} exposes neither start() nor operation()")
            duration = (Now.utc() - start_time).total_seconds()

            self.emit_event(
                Event.Processed,
                processor=proc_name,
                duration=duration,
            )
        except Exception as e:
            # The listener stream and the audit stream have different readers:
            # emit_event notifies, the trace records the step (DR-WFL-018 t.2).
            self.emit_event(Event.Failed, processor=proc_name, error=str(e))
            self.debug(
                msg=Event.Process.name,
                step=Event.Failed.name,
                processor=proc_name,
                error=str(e),
            )
            raise OrchestratorException(
                self,
                f"Error processing {proc_name}: {e}",
            ) from e

    # endregion Internal

    # region Public

    def add_processor(self, processor: IProcessor) -> None:
        """Register a processor with the orchestrator.

        Requires a callable `start()` per IProcessor contract.
        """
        if not callable(getattr(processor, "start", None)):
            raise TypeError(
                "Processor {} is missing callable `start()`.".format(
                    getattr(processor, "name", "unknown"),
                )
            )
        self._processors.append(processor)

    def register_listener(self, listener: IEventListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def emit_event(self, event: Event, **kwargs) -> None:
        with self._emit_lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener.on_event(event, **kwargs)
            except TypeError:
                # Interface contract is on_event(event); allow strict listeners.
                listener.on_event(event)

    def operation(self, action: Operation):
        if action == Operation.Start:
            return self.start()
        if action == Operation.Stop:
            return self.stop()
        raise OrchestratorException(
            self,
            f"Unrecognised operation: {action!r}",
        )

    def start(self, parallel: bool = False) -> None:
        """Starts processor execution (sequentially or in parallel)."""
        if self._running:
            return
        self._running = True
        self.info(
            msg=Event.OrchestrationStarted.name,
            processors=len(self._processors),
            parallel=parallel,
        )
        self.emit_event(Event.OrchestrationStarted)

        try:
            if parallel:
                threads: list[threading.Thread] = []
                errors: list[BaseException] = []
                lock = threading.Lock()

                def _runner(p: IProcessor) -> None:
                    try:
                        self._start_processor(p)
                    except BaseException as e:  # noqa: BLE001
                        with lock:
                            errors.append(e)

                for processor in self._processors:
                    thread = threading.Thread(target=_runner, args=(processor,), daemon=False)
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()

                if errors:
                    raise errors[0]
            else:
                for processor in self._processors:
                    if not self._running:
                        break
                    self._start_processor(processor)
        finally:
            self._running = False
            self.info(
                msg=Event.OrchestrationCompleted.name,
                processors=len(self._processors),
            )
            self.emit_event(Event.OrchestrationCompleted)

    def stop(self) -> None:
        self._running = False
        self.info(msg=Event.OrchestrationStopped.name)
        self.emit_event(Event.OrchestrationStopped)

    # endregion Public


# --------------------------------------------------------------------------- #
# endregion Orchestrators                                                     #
# --------------------------------------------------------------------------- #


__all__ = ["Orchestrator"]
