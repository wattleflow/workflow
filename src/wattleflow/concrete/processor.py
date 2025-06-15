# Module Name: concrete/processor.py
# Description: This modul contains concrete base processor class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import abstractmethod, ABC
from logging import Handler, INFO
from typing import AsyncGenerator, Generator, Generic, Optional
from wattleflow.core import IBlackboard, IPipeline, IProcessor, T
from wattleflow.concrete import Attribute, AuditLogger  # ProcessorException
from wattleflow.constants.enums import Event


class GenericProcessor(IProcessor, AuditLogger, Attribute, Generic[T], ABC):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        allowed: list[str] = None,
        level: int = INFO,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        if allowed is None:
            allowed = []

        IProcessor.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        Attribute.__init__(self)

        self._blackboard: IBlackboard = blackboard
        self._pipelines: list = pipelines
        self._allowed: list = allowed
        self._generator: Optional[Generator[T]] = None
        self._current: Optional[T] = None
        self._cycle: int = 0

        self.evaluate(self._pipelines, list)
        self.evaluate(self._allowed, list)

        if not self._pipelines or not len(self._pipelines) > 0:
            error = "Valid list of pipelines excpected."
            self.critical(msg=error)
            raise ValueError(error)

        from wattleflow.core import IPipeline

        self.debug(
            msg=Event.Constructor.value,
            pipelines=[p.name if isinstance(p, IPipeline) else p for p in pipelines],
            allowed=allowed,
        )

        self.configure(**kwargs)

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    def configure(self, **kwargs):
        if not self.allowed(self._allowed, **kwargs):
            self.debug("No configurable properties allowed.")
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, str, list, dict)):
                self.push(name, value)
                self.debug(msg=Event.Configuring.value, name=name, value=value)
            else:
                error = (
                    f"Restricted property: {name} ({type(value).__name__}) "
                    f"Allowed types: bool, str, list, dict"
                )
                self.error(msg=error)
                raise AttributeError(error)

    @abstractmethod
    def create_generator(self) -> Generator[T, None, None]:
        pass

    def start(self) -> None:
        if self._generator is None:
            self._generator = self.create_generator()

        for item in self._generator:
            self._current = item
            self._cycle += 1

            for pipeline in self._pipelines:
                if isinstance(pipeline, IPipeline):
                    self.debug(
                        msg=Event.Processing.value,
                        item=item,
                        pipeline=pipeline.name,
                    )
                    pipeline.process(processor=self, item=item)
                else:
                    self.error(
                        msg="Assigned object is not a pipline.",
                        reason=pipeline.__class__.__name__,
                    )


class GenericAsyncProcessor(IProcessor, AuditLogger, Attribute, Generic[T], ABC):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        allowed: Optional[list[str]] = None,
        level: int = 20,
        handler=None,
        **kwargs,
    ):
        AuditLogger.__init__(self, level=level, handler=handler)
        Attribute.__init__(self)

        self._blackboard = blackboard
        self._pipelines = pipelines
        self._allowed = allowed or []
        self._cycle: int = 0
        self._current: Optional[T] = None

        self.evaluate(self._pipelines, list)
        self.evaluate(self._allowed, list)

        if not self._pipelines:
            self.critical("Pipelines cannot be empty.")
            raise ValueError("Pipelines cannot be empty.")

        self.debug(
            msg="AsyncProcessor constructed",
            pipelines=[p.name for p in self._pipelines],
            allowed=self._allowed,
        )

        self.configure(**kwargs)

    def configure(self, **kwargs):
        if not self.allowed(self._allowed, **kwargs):
            self.debug("No configurable properties allowed.")
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, str, list, dict)):
                self.push(name, value)
                self.debug(msg="Configuring", name=name, value=value)
            else:
                error = f"Invalid config type: {name} ({type(value).__name__})"
                self.error(msg=error)
                raise AttributeError(error)

    @abstractmethod
    async def create_generator(self) -> AsyncGenerator[T, None]:
        pass

    async def start(self) -> None:
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
