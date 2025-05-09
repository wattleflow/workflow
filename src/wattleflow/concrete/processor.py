# Module Name: concrete/processor.py
# Description: This modul contains concrete base processor class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import abstractmethod, ABC
from logging import Handler, INFO
from typing import Final, Generator, Iterator, Optional, Type
from wattleflow.core import IBlackboard, IProcessor, T
from wattleflow.concrete import Attribute, AuditLogger, ProcessorException
from wattleflow.constants.enums import Event
from wattleflow.helpers.functions import _NC


# TODO: Add metrics
class GenericProcessor(IProcessor[T], Attribute, AuditLogger, ABC):
    _expected_type: Type[T] = T
    _cycle: int = 0
    _current: Optional[T] = None
    _blackboard: IBlackboard = None
    _pipelines: Final[list]
    _iterator: Iterator[T]
    _allowed: list = []

    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        allowed: list = [],
        level: int = INFO,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        IProcessor.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            blackboard=blackboard.name,
            pipelines=[p.name for p in pipelines],
            allowed=allowed,
            **kwargs,
        )

        self.evaluate(pipelines, list)

        if not len(pipelines) > 0:
            error = "Pipelines can not be empty."
            self.critical(msg=error)
            raise ValueError(error)

        self.evaluate(blackboard, IBlackboard)
        self.evaluate(allowed, list)

        self._blackboard = blackboard
        self._pipelines = pipelines
        self._allowed = allowed

        self.configure(**kwargs)

        # Child processor must make this call
        self._iterator = self.create_iterator()

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @property
    def cycle(self) -> int:
        return self._cycle

    def __del__(self):
        if self._blackboard:
            self._blackboard.clean()

    def __next__(self) -> T:
        try:
            self._current = next(self._iterator)
            self._cycle += 1
            return self._current
        except StopIteration:
            raise

    def configure(self, **kwargs):
        if not self.allowed(self._allowed, **kwargs):
            self.debug("Properties are not allowed.")
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
                self.debug(msg=Event.Configuring.value, name=name, value=value)
            else:
                error = f"Restricted properties found: {_NC(value)}.{name}. [bool, dict, list, str]"
                self.error(msg=error, name=name)
                raise AttributeError(error)

    def reset(self):
        self.debug(msg="reset")
        self._iterator = self.create_iterator()
        self._step = 0

    def process_tasks(self):
        self.debug(msg=Event.Processing.value, message="BEGIN")
        try:
            for item in self:
                for pipeline in self._pipelines:
                    self.debug(
                        msg=Event.ProcessingTask.value, item=item, pipeline=pipeline
                    )
                    pipeline.process(processor=self, item=item)
        except StopIteration:
            self.debug(msg="Stopping iteration")
            pass
        except AttributeError as e:
            self.critical(msg="Attribute error", error=str(e))
            raise AttributeError(e)
        except Exception as e:
            self.critical(msg="Exception", error=str(e))
            raise ProcessorException(caller=self, error=e)
        self.debug(msg=Event.Processing.value, message="END")

    @abstractmethod
    def create_iterator(self) -> Generator[T, None, None]:
        pass
