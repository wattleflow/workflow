# Module name: concrete/processor.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from abc import abstractmethod, ABC
from logging import Handler
from typing import Any, Generator, List, Optional
from wattleflow.core import (
    IBlackboard,
    IOriginator,
    IMemento,
    IPipeline,
    IProcessor,
    ITarget,
    IStateMachine,
)
from wattleflow.concrete.logger import AuditLogger
from wattleflow.constants.enums import Event
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute
from wattleflow.concrete.exception import PipelineException, ProcessorException


__SLOTS__ = (
    "_blackboard",
    "_current",
    "_cycle",
    "_generator",
    "_pipelines",
    "_preset",
    "_state",
)

from enum import Enum


class ProcessorState(str, Enum):
    IDLE = "idle"  # ništa nije učinjeno
    STATE_LOADED = "state_loaded"  # restore iz mementa
    RUNNING = "running"  # aktivna obrada
    NEXT_ITEM = "next_item"  # iteracija
    COMPLETED = "completed"  # dataset gotov
    FAILED = "failed"  # prekid (bitno za resume)


class ProcessorAction(str, Enum):
    LOAD = "load"  # restore state
    START = "start"  # start ili resume
    NEXT_ITEM = "next_item"  # iteracija
    CYCLE_COMPLETED = "cycle_completed"  # jedan item prošao kroz pipeline
    RECORDS_PROCESSED = "records_processed"  # dataset gotov
    FAIL = "fail"  # greška
    STORE = "store"  # save memento


PROCESSOR_TRANSITIONS = {
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


class ProcessorMemento(IMemento):
    __slots__ = ("_cycle", "_state")

    def __init__(self, cycle: int, state: ProcessorState):
        self._cycle = cycle
        self._state = state

    @property
    def cycle(self) -> int:
        return self._cycle

    def get_state(self) -> ProcessorState:
        return self._state


class ProcessorFSM(IStateMachine, ABC):
    __slots__ = ("state",)

    def __init__(self, initial: ProcessorState = ProcessorState.IDLE) -> None:
        IStateMachine.__init__(self)
        self.state = initial

    def can(self, action: ProcessorAction) -> bool:
        return (self.state, action) in PROCESSOR_TRANSITIONS

    def apply(self, action: ProcessorAction) -> None:
        key = (self.state, action)
        if key not in PROCESSOR_TRANSITIONS:
            raise RuntimeError(f"{action} not allowed in state {self.state}")
        self.state = PROCESSOR_TRANSITIONS[key]

    def __repr__(self) -> str:
        return f"{self.name}:[{self.state.name}]"


class GenericProcessor(IProcessor, IOriginator, AuditLogger, ABC):
    __slots__ = __SLOTS__

    def __init__(
        self,
        **kwargs,
    ):
        level = kwargs.pop("level", 0)
        handler: Optional[Handler] = kwargs.pop("handler", None)

        blackboard: Optional[IBlackboard] = kwargs.pop("blackboard", None)
        pipelines: Optional[List[IPipeline]] = kwargs.pop("pipelines", None)

        IProcessor.__init__(self)
        IOriginator.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            blackboard=blackboard,
            pipelines=pipelines,
            level=self._level,
            handler=self._handler,
            kwargs=kwargs,
        )

        if blackboard:
            Attribute.evaluate(self, blackboard, IBlackboard)

        if pipelines:
            Attribute.evaluate(self, pipelines, list)

        self._cycle: int = 0
        self._state: ProcessorState = ProcessorState.IDLE
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)
        self._blackboard: Optional[IBlackboard] = blackboard
        self._pipelines: List[IPipeline] = pipelines if pipelines else []
        self._generator: Optional[Generator[ITarget]] = None
        self._current: Optional[ITarget] = None

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            state=self._state.name,
            generator=self._generator,
            current=self._current,
            cycle=self._cycle,
            # pipelines=[p.name if isinstance(p, IPipeline) else p for p in pipelines],
            preset=self._preset,
        )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    # def __getattr__(self, name: str) -> Any:
    #     all_slots: set = set()
    #     for cls in type(self).__mro__:
    #         all_slots.update(getattr(cls, "__slots__", ()))

    #     if name in all_slots:
    #         return object.__getattribute__(self, name)

    #     preset: PresetDecorator = object.__getattribute__(self, "_preset")
    #     return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}: [{len(self._pipelines)}]:[{self.levelname}]"

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @property
    def cycle(self) -> int:
        return self._cycle

    @abstractmethod
    def create_generator(self) -> Generator[ITarget, None, None]:
        pass

    # region Memento
    def save_state(self) -> IMemento:
        return ProcessorMemento(cycle=self._cycle, state=self._state)

    def restore_state(self, memento: IMemento) -> None:
        if not isinstance(memento, ProcessorMemento):
            raise ProcessorException(caller=self, error="Invalid memento")

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

    def start(self) -> None:
        self.debug(
            msg=Event.Start.value,
            step=Event.Started.value,
        )

        if self._blackboard is None:
            raise ProcessorException(self, f"Missing {self.name!r} blackboard!")

        if len(self._pipelines) < 1:
            raise ProcessorException(self, f"Missing {self.name!r} pipelines!")

        fsm = ProcessorFSM()

        try:
            if self._generator is None:
                self._generator = self.create_generator()

            if fsm.can(ProcessorAction.START):
                fsm.apply(ProcessorAction.START)

            for facade in self._generator:
                self._current = facade

                if fsm.can(ProcessorAction.NEXT_ITEM):
                    fsm.apply(ProcessorAction.NEXT_ITEM)

                try:
                    for pipeline in self._pipelines:
                        pipeline.process(processor=self, facade=facade)

                    self._cycle += 1

                    if fsm.can(ProcessorAction.CYCLE_COMPLETED):
                        fsm.apply(ProcessorAction.CYCLE_COMPLETED)

                except Exception as e:
                    self.error(msg="Pipeline processing failed", error=str(e))
                    if fsm.can(ProcessorAction.FAIL):
                        fsm.apply(ProcessorAction.FAIL)

                    raise PipelineException(caller=self, error=str(e)) from e

            if fsm.can(ProcessorAction.RECORDS_PROCESSED):
                fsm.apply(ProcessorAction.RECORDS_PROCESSED)

        except Exception as e:
            self.blackboard.save_state()
            raise ProcessorException(caller=self, error=str(e)) from e

        self.debug(
            msg=Event.Start.name,
            step=Event.Completed.name,
        )

    def register_blackboard(self, blackboard: IBlackboard) -> None:
        self.debug(
            Event.Register.name, step=Event.Starting.name, blackboard=self._blackboard
        )
        Attribute.evaluate(self, blackboard, IBlackboard)
        self._blackboard = blackboard
        self.debug(
            Event.Register.name, step=Event.Completed.name, added=self._blackboard
        )

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


# class GenericAsyncProcessor(IProcessor, AuditLogger, ABC):
#     __slots__ = __SLOTS__

#     def __init__(
#         self,
#         blackboard: IBlackboard,
#         pipelines: List[IPipeline],
#         **kwargs,
#     ):

#         self._level: int = kwargs.pop("level", NOTSET)
#         self._handler: Optional[Handler] = kwargs.pop("handler", None)

#         IProcessor.__init__(self)
#         AuditLogger.__init__(self, level=self._level, handler=self._handler)

#         self.debug(
#             msg=Event.Constructor.value,
#             step=Event.Started.value,
#             blackboard=blackboard,
#             pipelines=[p.name if isinstance(p, IPipeline) else p for p in pipelines],
#             level=self._level,
#             handler=self._handler,
#             kwargs=kwargs,
#         )

#         Attribute.evaluate(self, pipelines, list)
#         Attribute.evaluate(self, blackboard, IBlackboard)

#         self._preset: PresetDecorator = PresetDecorator(self, **kwargs)
#         self._cycle: int = 0
#         self._blackboard: IBlackboard = blackboard
#         self._pipelines: list = pipelines
#         self._generator: Optional[AsyncGenerator[ITarget]] = None
#         self._current: Optional[ITarget] = None

#         self.debug(
#             msg=Event.Constructor.value,
#             status=Event.Completed.value,
#             generator=self._generator,
#             current=self._current,
#             cycle=self._cycle,
#             preset=self._preset,
#         )

#     @abstractmethod
#     async def create_generator(self) -> AsyncGenerator[ITarget, None]:
#         pass

#     async def start(self) -> None:
#         if self._generator is None:
#             self._generator = await self.create_generator()

#         async for item in self._generator:
#             self.debug(
#                 msg=Event.Start.value,
#                 step=Event.Started.value,
#                 item=item,
#                 cycle=self._cycle,
#             )
#             self._current = item
#             self._cycle += 1
#             for pipeline in self._pipelines:
#                 try:
#                     self.debug(
#                         msg=Event.Processing.value,
#                         step="Processing async item",
#                         item=item,
#                         pipeline=pipeline.name,
#                     )
#                     await pipeline.process(processor=self, item=item)
#                 except Exception as e:
#                     self.error(msg="Pipeline processing failed", error=str(e))
#                     raise

#     # Must be implemented if using PresetDecorator
#     # def __getattr__(self, name: str) -> Any:
#     #     preset: PresetDecorator = object.__getattribute__(self, "_preset")
#     #     return preset.__getattr__(name)

#     def __getattr__(self, name: str) -> Any:
#         all_slots: set = set()
#         for cls in type(self).__mro__:
#             all_slots.update(getattr(cls, "__slots__", ()))

#         if name in all_slots:
#             return object.__getattribute__(self, name)

#         preset: PresetDecorator = object.__getattribute__(self, "_preset")
#         return preset.__getattr__(name)

#     def __repr__(self) -> str:
#         return f"{self.name}: {len(self._pipelines)}"
