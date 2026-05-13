# Module name: concrete/processor.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import abstractmethod, ABC
from enum import Enum
from logging import Handler
from typing import Any, Generator, List, Optional
from wattleflow.core import (
    IBlackboard,
    IOriginator,
    IMemento,
    IPipeline,
    IProcessor,
    ITarget,
)
from wattleflow.concrete.logger import AuditLogger
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.constants.enums import Event
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute
from wattleflow.concrete.exception import PipelineException, ProcessorException
from wattleflow.constants.enums import Operation

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# ----------------------------------------------------------------------------#
# region State Nachine                                                        #
# ----------------------------------------------------------------------------#


class ProcessorState(str, Enum):
    IDLE = "idle"  # nothing is done
    STATE_LOADED = "state_loaded"  # restore
    RUNNING = "running"  # active transformation
    COMPLETED = "completed"  # dataset finnished
    FAILED = "failed"  # faild (important for resume)


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
# endregion State Nachine                                                     #
# ----------------------------------------------------------------------------#

# ----------------------------------------------------------------------------#
# region Processors                                                           #
# ----------------------------------------------------------------------------#


class GenericProcessor(IProcessor, IOriginator, AuditLogger, ABC):
    __slots__ = (
        "_blackboard",
        "_current",
        "_cycle",
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
        level = kwargs.pop("level", 0)
        handler: Optional[Handler] = kwargs.pop("handler", None)

        blackboard: Optional[IBlackboard] = kwargs.pop("blackboard", None)
        pipelines: Optional[List[IPipeline]] = kwargs.pop("pipelines", None)

        IProcessor.__init__(self)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        IOriginator.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Starting.value,
            blackboard=blackboard,
            pipelines=pipelines,
            kwargs=kwargs,
        )

        if blackboard:
            Attribute.evaluate(self, blackboard, IBlackboard)

        if pipelines:
            Attribute.evaluate(self, pipelines, list)

        self._cycle: int = 0
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            ProcessorState.IDLE,
            name="ProcessorFSM",
        )

        self._blackboard: Optional[IBlackboard] = blackboard
        self._pipelines: List[IPipeline] = pipelines if pipelines else []
        self._generator: Optional[Generator[ITarget]] = None
        self._current: Optional[ITarget] = None

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            cycle=self._cycle,
            preset=self._preset,
            state=self._fsm.state.name,
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
            self.debug(Event.Delete.name, step=Event.Started.name)

            if self._blackboard:
                try:
                    self._blackboard.clean()
                except Exception as e:
                    self.error(Event.Deleting.name, member="_blackboard", error=e)
                self._blackboard = None

            self._current = None
            self._pipelines.clear()
            self._generator = None
            self._preset = None

        except Exception:
            pass

        self.debug(Event.Delete.name, step=Event.Completed.name)

    # endregion Private

    # region Property

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @property
    def cycle(self) -> int:
        return self._cycle

    # endregion Property

    @abstractmethod
    def create_generator(self) -> Generator[ITarget, None, None]:
        pass

    # region Memento

    def save_state(self) -> IMemento:
        return GenericMemento(cycle=self._cycle, state=self._fsm.state)

    def restore_state(self, memento: IMemento) -> None:
        # if not isinstance(memento, ProcessorMemento):
        #     raise ProcessorException(caller=self, error="Invalid memento")

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
            msg="operation",
            action=action.name,
            error="Action not supported by processor",
        )
        return False

    def start(self) -> None:
        self.debug(msg=Event.Start.value, step=Event.Started.value)

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
                    self.blackboard.flush(self)
                except Exception as e:
                    self.error(msg="Pipeline processing failed", error=str(e))
                    raise PipelineException(caller=self, error=str(e)) from e

            self._fsm.apply(ProcessorAction.RECORDS_PROCESSED)

        except PipelineException as e:
            raise e
        except Exception as e:
            if self._fsm.can(ProcessorAction.FAIL):
                self._fsm.apply(ProcessorAction.FAIL)
            raise ProcessorException(caller=self, error=str(e)) from e

        self.debug(msg=Event.Start.name, step=Event.Completed.name)

    def register_blackboard(self, blackboard: IBlackboard) -> None:
        self.debug(Event.Register.name, step=Event.Starting.name, blackboard=self._blackboard)
        Attribute.evaluate(self, blackboard, IBlackboard)
        self._blackboard = blackboard
        self.debug(Event.Register.name, step=Event.Completed.name, added=self._blackboard)

    def register_pipeline(self, pipeline: IPipeline) -> None:
        self.debug(Event.Register.name, step=Event.Starting.name, pipeline=pipeline)
        Attribute.evaluate(self, pipeline, IPipeline)
        self._pipelines.append(pipeline)
        self.debug(
            Event.Register.name,
            step=Event.Completed.name,
            added=pipeline,
            count=len(self._pipelines),
        )

    # endregion public


# ----------------------------------------------------------------------------#
# endregion Processors                                                        #
# ----------------------------------------------------------------------------#
