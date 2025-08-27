# Module Name: concrete/processor.py
# Description: This modul contains concrete base processor class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from abc import abstractmethod, ABC
from logging import Handler, INFO
from typing import AsyncGenerator, Generator, List, Optional
from wattleflow.core import IBlackboard, IPipeline, IProcessor, ITarget
from wattleflow.concrete import AuditLogger, ProcessorException
from wattleflow.constants.enums import Event
from wattleflow.helpers import Attribute

PERMITED_VALUES = (
    "_blackboard",
    "_current",
    "_cycle",
    "_generator",
    "_pipelines",
    "_preset",
)


class GenericProcessor(IProcessor, AuditLogger, ABC):
    __slots__ = PERMITED_VALUES

    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: List[IPipeline],
        level: int = INFO,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        IProcessor.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            status="initialising",
            blackboard=blackboard,
            pipelines=[p.name if isinstance(p, IPipeline) else p for p in pipelines],
            level=level,
            handler=handler,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=pipelines, expected_type=list)
        Attribute.evaluate(caller=self, target=blackboard, expected_type=IBlackboard)

        self._cycle: int = 0
        self._blackboard: IBlackboard = blackboard
        self._pipelines: list = pipelines
        self._generator: Optional[Generator[ITarget]] = None
        self._current: Optional[ITarget] = None

        from wattleflow.helpers.preset import Preset

        self._preset: Preset = Preset()
        self._preset.configure(caller=self, **kwargs)

        self.debug(
            msg=Event.Constructor.value,
            status="completed",
            generator=self._generator,
            current=self._current,
            cycle=self._cycle,
            preset=self._preset,
        )

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @abstractmethod
    def create_generator(self) -> Generator[ITarget, None, None]:
        pass

    def start(self) -> None:
        if self._generator is None:
            self._generator = self.create_generator()

        for document in self._generator:
            self._current = document
            self._cycle += 1

            for pipeline in self._pipelines:
                if isinstance(pipeline, IPipeline):
                    self.debug(
                        msg=Event.Processing.value,
                        document=document,
                        pipeline=pipeline.name,
                    )
                    pipeline.process(processor=self, document=document)
                else:
                    self.error(
                        msg=Event.Processing.value,
                        reason="Assigned object is not a pipline.",
                        class_name=Attribute.class_name(pipeline),
                        type_name=Attribute.type_name(pipeline),
                    )
                    raise ProcessorException(
                        caller=self, error="Inccorect pipeline type."
                    )

    def __repr__(self) -> str:
        return f"{self.name}: {len(self._pipelines)}"


class GenericAsyncProcessor(IProcessor, AuditLogger, ABC):
    __slots__ = PERMITED_VALUES

    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: List[IPipeline],
        level: int = 20,
        handler=None,
        **kwargs,
    ):
        IProcessor.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            status="initialising",
            blackboard=blackboard,
            pipelines=[p.name if isinstance(p, IPipeline) else p for p in pipelines],
            level=level,
            handler=handler,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=pipelines, expected_type=List[IPipeline])
        Attribute.evaluate(caller=self, target=blackboard, expected_type=IBlackboard)

        self._cycle: int = 0
        self._blackboard: IBlackboard = blackboard
        self._pipelines: list = pipelines
        self._generator: Optional[AsyncGenerator[ITarget]] = None
        self._current: Optional[ITarget] = None

        from wattleflow.helpers.preset import Preset

        self._preset = Preset()
        self._preset.configure(caller=self, raise_errors=True, **kwargs)

        self.debug(
            msg=Event.Constructor.value,
            status="completed",
            generator=self._generator,
            current=self._current,
            cycle=self._cycle,
            preset=self._preset,
        )

    @abstractmethod
    async def create_generator(self) -> AsyncGenerator[ITarget, None]:
        pass

    async def start(self) -> None:
        if self._generator is None:
            self._generator = await self.create_generator()

        async for item in await self.create_generator():
            self._current = item
            self._cycle += 1
            for pipeline in self._pipelines:
                try:
                    self.debug(msg="Processing item", item=item, pipeline=pipeline.name)
                    await pipeline.process(processor=self, item=item)
                except Exception as e:
                    self.error(msg="Pipeline failed", error=str(e))
                    raise
