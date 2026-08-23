# Module name: concrete/processor.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import gc
from abc import abstractmethod, ABC
from enum import Enum
from typing import Any
from collections.abc import Generator
from wattleflow.core import (
    IBlackboard,
    IOriginator,
    IPipeline,
    IProcessor,
    ITarget,
)
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.concrete.exception import PipelineException, ProcessorException

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# ----------------------------------------------------------------------------#
# region State machine                                                        #
# ----------------------------------------------------------------------------#


class ProcessorState(str, Enum):
    IDLE = "idle"
    STATE_LOADED = "state_loaded"  # restore
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"  # resumable


class ProcessorAction(str, Enum):
    LOAD = "load"  # restore state
    START = "start"  # start / resume
    NEXT_ITEM = "next_item"  # iteration
    CYCLE_COMPLETED = "cycle_completed"  # record went through pipeline
    RECORDS_PROCESSED = "records_processed"  # dataset finished
    FAIL = "fail"  # error
    STORE = "store"  # save memento


TRANSITIONS = {
    # --- INIT ---
    (ProcessorState.IDLE, ProcessorAction.LOAD): ProcessorState.STATE_LOADED,
    (ProcessorState.IDLE, ProcessorAction.START): ProcessorState.RUNNING,
    # --- RESUME ---
    (ProcessorState.STATE_LOADED, ProcessorAction.START): ProcessorState.RUNNING,
    # --- MAIN LOOP ---
    (ProcessorState.RUNNING, ProcessorAction.NEXT_ITEM): ProcessorState.RUNNING,
    (ProcessorState.RUNNING, ProcessorAction.CYCLE_COMPLETED): ProcessorState.RUNNING,
    # --- COMPLETE ---
    (
        ProcessorState.RUNNING,
        ProcessorAction.RECORDS_PROCESSED,
    ): ProcessorState.COMPLETED,
    # --- FAILURE ---
    (ProcessorState.RUNNING, ProcessorAction.FAIL): ProcessorState.FAILED,
    # --- RECOVERY ---
    (ProcessorState.FAILED, ProcessorAction.LOAD): ProcessorState.STATE_LOADED,
    # --- STORE ---
    (ProcessorState.COMPLETED, ProcessorAction.STORE): ProcessorState.COMPLETED,
    (ProcessorState.FAILED, ProcessorAction.STORE): ProcessorState.FAILED,
}
# ----------------------------------------------------------------------------#
# endregion State machine                                                     #
# ----------------------------------------------------------------------------#

# ----------------------------------------------------------------------------#
# region Processors                                                           #
# ----------------------------------------------------------------------------#


class GenericProcessor(Wattleflow, IProcessor, IOriginator, ABC):
    __slots__ = (
        "_blackboard",
        "_current",
        "_cycle",
        "_flush_per_cycle",
        "_fsm",
        "_generator",
        "_pipelines",
        "_preset",
    )

    # region Private

    def __init__(
        self,
        **kwargs,
    ):
        blackboard: IBlackboard | None = kwargs.pop("blackboard", None)
        pipelines: list[IPipeline] | None = kwargs.pop("pipelines", None)
        flush_per_cycle = kwargs.pop("flush_per_cycle", None)
        legacy_defer = kwargs.pop("defer_flush", None)

        if flush_per_cycle is None and legacy_defer is not None:
            flush_per_cycle = not bool(legacy_defer)
        if flush_per_cycle is None:
            flush_per_cycle = True

        if blackboard is not None:
            assert isinstance(blackboard, IBlackboard), "Expected IBlackboard. Found %s" % type(
                blackboard
            )
        if pipelines is not None:
            assert isinstance(pipelines, list), "Expected list. Found %s" % type(pipelines)

        super().__init__(**kwargs)

        # ALLOWED is resolved by PresetDecorator from the class (NFR-ORG-07);
        # an explicit allowed= in kwargs still overrides it.
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor.name,
            step=Event.Starting.value,
            blackboard=blackboard,
            pipelines=pipelines,
            flush_per_cycle=flush_per_cycle,
            kwargs=kwargs,
        )

        if legacy_defer is not None:
            self.warning(
                msg=Event.Configure.name,
                component="config",
                deprecated="defer_flush",
                use="flush_per_cycle",
                value=flush_per_cycle,
            )

        self._cycle: int = 0
        self._flush_per_cycle: bool = bool(flush_per_cycle)
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            ProcessorState.IDLE,
            name="ProcessorFSM",
        )

        self._blackboard: IBlackboard | None = blackboard
        self._pipelines: list[IPipeline] = pipelines if pipelines else []
        self._generator: Generator[ITarget] | None = None
        self._current: ITarget | None = None

        self.debug(
            msg=Event.Constructor.name,
            step=Event.Completed.name,
            cycle=self._cycle,
            preset=self._preset,
        )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}: [{len(self._pipelines)}]:[{self.levelname}]"

    def __del__(self):
        try:
            self.debug(msg=Event.Delete.name, step=Event.Started.name)

            if self._blackboard:
                try:
                    self._blackboard.clean()
                except Exception as e:
                    name = self.__class__.__name__
                    reason = f"{name} destructor error: {str(e)}"
                    self.error(
                        msg=Event.Deleting.name,
                        member="_blackboard",
                        reason=reason,
                        # trace=traceback.format_exc(),
                    )
                self._blackboard = None

            self._current = None
            self._pipelines.clear()
            self._generator = None
            self._preset = None
        except Exception as e:
            reason = (
                "Destructor %s.__del__  error: %s" % self.__class__.__name__,
                str(e),
            )
            self.error(
                msg=Event.Deleting.name,
                reason=reason,
                # trace=traceback.format_exc(),
            )
        finally:
            self.debug(msg=Event.Delete.name, step=Event.Completed.name)
            gc.collect()

    # endregion Private

    # region Property

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @property
    def cycle(self) -> int:
        return self._cycle

    @property
    def flush_per_cycle(self) -> bool:
        return self._flush_per_cycle

    # endregion Property

    @abstractmethod
    def create_generator(self) -> Generator[ITarget, None, None]:
        pass

    # region Memento

    def save_state(self) -> GenericMemento:
        return GenericMemento(cycle=self._cycle, state=self._fsm.state)

    def restore_state(self, memento: GenericMemento) -> None:
        saved_state = memento.get_state()
        # LOAD recovery only valid from IDLE or FAILED — validate before mutating.
        if (saved_state, ProcessorAction.LOAD) not in TRANSITIONS:
            raise ProcessorException(
                caller=self,
                error=f"Cannot restore: LOAD not allowed from saved state {saved_state.name}",
            )

        self._fsm.state = saved_state
        self._fsm.apply(ProcessorAction.LOAD)

        self._cycle = memento.cycle
        self._generator = self.create_generator()

        skipped = 0
        try:
            while skipped < self._cycle:
                next(self._generator)
                skipped += 1
        except StopIteration:
            raise ProcessorException(
                caller=self,
                error="Restore failed: dataset shorter than saved cycle",
            ) from None

    # endregion Memento

    # region Public

    def operation(self, action: Operation, **kwargs) -> bool:
        if action is Operation.Start:
            self.start(**kwargs)
            return True
        self.warning(
            msg=Event.Operation.name,
            action=action.name,
            error="Action not supported by processor",
        )
        return False

    def start(self) -> None:
        self.debug(msg=Event.Start.name, step=Event.Started.name)

        if self._blackboard is None:
            raise ProcessorException(self, f"Missing {self.name!r} blackboard!")

        if len(self._pipelines) < 1:
            raise ProcessorException(self, f"Missing {self.name!r} pipelines!")

        try:
            if self._generator is None:
                self._generator = self.create_generator()

            self._fsm.apply(ProcessorAction.START)

            for facade in self._generator:
                self._current = facade
                self._fsm.apply(ProcessorAction.NEXT_ITEM)

                try:
                    for pipeline in self._pipelines:
                        pipeline.process(processor=self, facade=facade)

                    self._cycle += 1
                    self._fsm.apply(ProcessorAction.CYCLE_COMPLETED)
                    if self._flush_per_cycle:
                        self.blackboard.flush(caller=self)
                except Exception as e:
                    reason = "%s.start error: Pipeline processing failed: %s" % (
                        self.__class__.__name__,
                        str(e),
                    )
                    self.error(
                        msg=Event.Start.name,
                        reason=reason,
                    )
                    raise PipelineException(
                        caller=self,
                        error=reason,
                    ) from e

            self._fsm.apply(ProcessorAction.RECORDS_PROCESSED)

        except PipelineException as e:
            raise e
        except Exception as e:
            if self._fsm.can(ProcessorAction.FAIL):
                self._fsm.apply(ProcessorAction.FAIL)
            raise ProcessorException(caller=self, error=str(e)) from e

        self.debug(msg=Event.Start.name, step=Event.Completed.name)

    def register_blackboard(self, blackboard: IBlackboard) -> None:
        self.debug(msg=Event.Register.name, step=Event.Starting.name, blackboard=self._blackboard)
        assert isinstance(blackboard, IBlackboard), "Expected IBlackboard. Found %s" % type(
            blackboard
        )
        self._blackboard = blackboard
        self.debug(msg=Event.Register.name, step=Event.Completed.name, added=self._blackboard)

    def register_pipeline(self, pipeline: IPipeline) -> None:
        self.debug(msg=Event.Register.name, step=Event.Starting.name, pipeline=pipeline)
        assert isinstance(pipeline, IPipeline), "Expected IPipeline. Found %s" % type(pipeline)
        self._pipelines.append(pipeline)
        self.debug(
            msg=Event.Register.name,
            step=Event.Completed.name,
            added=pipeline,
            count=len(self._pipelines),
        )

    # endregion public


# ----------------------------------------------------------------------------#
# endregion Processors                                                        #
# ----------------------------------------------------------------------------#


__all__ = ["GenericProcessor", "ProcessorAction", "ProcessorState"]
