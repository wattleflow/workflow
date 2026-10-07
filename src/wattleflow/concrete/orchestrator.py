# Module name: concrete/orchestrator.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Orchestrator Implementation for WattleFlow Workflow
The Orchestrator class:
    - Holds processors and starts them in registration order, or all at once in threads.
    - Reports each step to its listeners (Processed, Failed, Orchestration*) and to the audit.
    - Holds the connection manager and an optional execute strategy for specialisations; the
      orchestrator itself does not use either.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import inspect
import threading
from wattleflow.helpers.moment import MomentAwareHelper
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
from wattleflow.concrete.helpers import Attribute
from wattleflow.concrete.base import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Orchestrators                                                        #
# --------------------------------------------------------------------------- #


class Orchestrator(Wattleflow, IEventSource, IFacade):
    __slots__ = (
        "_listeners",
        "_processors",
        "_running",
        "_connection_manager",
        "_strategy_execute",
        "_emit_lock",
        "_state_lock",
    )

    def __init__(
        self,
        connection_manager: ConnectionManager,
        strategy_execute: IStrategy | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        Attribute.evaluate(self, connection_manager, ConnectionManager)
        if strategy_execute is not None:
            Attribute.evaluate(self, strategy_execute, IStrategy)
        self._listeners: list[IEventListener] = []
        self._processors: list[IProcessor] = []
        self._running: bool = False
        self._connection_manager = connection_manager
        self._strategy_execute = strategy_execute
        self._emit_lock = threading.Lock()
        self._state_lock = threading.Lock()

    @property
    def connection_manager(self) -> ConnectionManager:
        return self._connection_manager

    @property
    def strategy_execute(self) -> IStrategy | None:
        return self._strategy_execute

    @property
    def running(self) -> bool:
        return self._running

    # region Internal

    def _start_processor(self, processor: IProcessor) -> None:
        proc_name = getattr(processor, "name", "unknown")
        try:
            start_time = MomentAwareHelper.now()
            # IProcessor contract uses start(); fall back to operation(Start)
            # if a custom processor only exposes the facade signature.
            if callable(getattr(processor, "start", None)):
                processor.start()
            elif callable(getattr(processor, "operation", None)):
                processor.operation(Operation.Start)
            else:
                raise TypeError(
                    f"Processor {proc_name!r} exposes neither start() nor operation()"
                )
            duration = (MomentAwareHelper.now() - start_time).total_seconds()

            self.emit_event(
                Event.Processed,
                processor=proc_name,
                duration=duration,
            )
        except Exception as e:
            # The listener stream and the audit stream have different readers:
            # emit_event notifies, the trace records the step.
            self.emit_event(Event.Failed, processor=proc_name, error=str(e))
            self.debug(
                msg=Event.Process,
                step=Event.Failed,
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
            raise OrchestratorException(
                self,
                "Processor {} is missing callable `start()`.".format(
                    getattr(processor, "name", "unknown"),
                ),
            )
        with self._state_lock:
            # Identity: the same processor twice would run twice.
            if not any(known is processor for known in self._processors):
                self._processors.append(processor)

    def register_listener(self, listener: IEventListener) -> None:
        with self._emit_lock:
            # Identity, not ==: a listener is registered as an object.
            if not any(known is listener for known in self._listeners):
                self._listeners.append(listener)

    @staticmethod
    def _accepts_metadata(listener: IEventListener, event: Event, kwargs: dict) -> bool:
        """The contract is on_event(event); a listener that also takes the metadata gets it.
        Decided from the signature, so a TypeError raised inside the listener is its own bug
        and is never mistaken for a signature mismatch and called a second time."""
        try:
            inspect.signature(listener.on_event).bind(event, **kwargs)
        except TypeError:
            return False
        except ValueError:  # no signature available: pass everything, as the contract allows
            return True
        return True

    def emit_event(self, event: Event, **kwargs) -> None:
        with self._emit_lock:
            listeners = list(self._listeners)
        # A listener that fails must not turn a processor that ran into a failure, hide the
        # error of one that did not, or keep the others from hearing the event.
        for listener in listeners:
            try:
                if self._accepts_metadata(listener, event, kwargs):
                    listener.on_event(event, **kwargs)
                else:
                    listener.on_event(event)
            except Exception as error:
                self.exception(
                    msg=Event.Notify,
                    reason="Listener raised during on_event",
                    listener=listener,
                    error=str(error),
                )

    def operation(self, action: Operation, **kwargs):
        if action == Operation.Start:
            return self.start(**kwargs)
        if action == Operation.Stop:
            return self.stop()
        raise OrchestratorException(
            self,
            f"Unrecognised operation: {action!r}",
        )

    def start(self, parallel: bool = False) -> None:
        """Starts processor execution (sequentially or in parallel)."""
        with self._state_lock:
            if self._running:
                return
            self._running = True
        self.info(
            msg=Event.OrchestrationStarted,
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
                    thread = threading.Thread(
                        target=_runner, args=(processor,), daemon=False
                    )
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()

                if errors:
                    if len(errors) == 1:
                        raise errors[0]
                    raise OrchestratorException(
                        self,
                        f"{len(errors)} processors failed: " + "; ".join(str(e) for e in errors),
                    ) from errors[0]
            else:
                for processor in self._processors:
                    if not self._running:
                        break
                    self._start_processor(processor)
        finally:
            with self._state_lock:
                self._running = False
            self.info(
                msg=Event.OrchestrationCompleted,
                processors=len(self._processors),
            )
            self.emit_event(Event.OrchestrationCompleted)

    def stop(self) -> None:
        with self._state_lock:
            self._running = False
        self.info(msg=Event.OrchestrationStopped)
        self.emit_event(Event.OrchestrationStopped)

    # endregion Public


# --------------------------------------------------------------------------- #
# endregion Orchestrators                                                     #
# --------------------------------------------------------------------------- #


__all__ = ["Orchestrator"]
