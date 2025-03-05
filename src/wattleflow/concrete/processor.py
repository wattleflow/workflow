# Module Name: core/concrete/processor.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete base processor class.

from abc import abstractmethod, ABC
from typing import Final, Generator, Iterator, List, TypeVar
from wattleflow.core import IStrategy
from wattleflow.core import IBlackboard, IProcessor, IPipeline
from wattleflow.concrete.attribute import Attribute
from wattleflow.concrete.exception import ProcessorException
from wattleflow.helpers.functions import _NC

T = TypeVar("T")


class GenericProcessor(IProcessor[T], Attribute, ABC):
    _cycle: int = 0
    _current: T = None
    _blackboard: IBlackboard = None
    _pipelines: Final[List[IPipeline]]
    _iterator: Iterator[T]

    def __init__(
        self,
        strategy_audit: IStrategy,
        blackboard: IBlackboard,
        pipelines: List[IPipeline],
        allowed: list = [],
        *args,
        **kwargs,
    ):
        super().__init__()
        self.evaluate(pipelines, List)
        if not len(pipelines) > 0:
            raise ValueError("Empty list: [pipelines].")

        self.evaluate(strategy_audit, IStrategy)
        self.evaluate(blackboard, IBlackboard)
        self.evaluate(allowed, List)

        self._allowed = allowed
        self.configure(**kwargs)

        self._strategy_audit = strategy_audit
        self._blackboard = blackboard
        self._pipelines = pipelines
        # hack ...
        self._blackboard.audit = self.audit
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

    def audit(self, caller, *args, **kwargs):
        self._strategy_audit.generate(caller=self, owner=caller, *args, **kwargs)

    def configure(self, **kwargs):
        if not self.allowed(self._allowed, **kwargs):
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
            else:
                error = f"Restricted type: {_NC(value)}.{name}. [bool, dict, list, str]"
                raise AttributeError(error)

    def reset(self):
        self._iterator = self.create_iterator()
        self._step = 0

    def process_tasks(self):
        try:
            for item in self:
                for pipeline in self._pipelines:
                    pipeline.process(processor=self, item=item)
        except StopIteration:
            pass
        except AttributeError as e:
            raise AttributeError(e)
        except Exception as e:
            raise ProcessorException(caller=self, error=e)
            # error=f"Processor caught exception: {e}")

    @abstractmethod
    def create_iterator(self) -> Generator[T, None, None]:
        pass
