# Module Name: concrete/strategies.py
# Description: This modul contains concrete strategy classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


"""
1. Generic Strategy Implementation
    Strategy (Base Class)
        - Defines call() and execute(), both abstract methods.
        - Forces subclasses to implement their behavior.
    GenericStrategy
        - Implements call(), which:
            - Calls execute()
            - Ensures the output matches _expected_type.
        - Enforces ITarget as the expected type by default.

2. Concrete Strategies
    StrategyGenerate
        - Calls execute() for object generation.
    StrategyCreate
        - Calls execute() using a processor.
        - Used for creating objects in a workflow.
    StrategyRead
        - Calls execute() to fetch an object by identifier.
    StrategyWrite
        - Calls execute() to store an object in a repository.
        - Uses _expected_type = bool, meaning execution must return True/False.
"""

from abc import abstractmethod, ABC
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import (
    IPipeline,
    IProcessor,
    IRepository,
    IStrategy,
    ITarget,
)
from wattleflow.concrete import Attribute, AuditLogger


# Generic strategy
class Strategy(IStrategy, Attribute, ABC):
    _expected_type = None

    @abstractmethod
    def call(self, caller, *args, **kwargs) -> object:
        pass

    @abstractmethod
    def execute(self, caller, *args, **kwargs) -> object:
        pass


class GenericStrategy(Strategy, AuditLogger, ABC):
    def __init__(
        self,
        expected_type=ITarget,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        self._expected_type = expected_type

        Strategy.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

    def call(self, caller, *args, **kwargs) -> object:
        output = self.execute(caller, *args, **kwargs)
        self.evaluate(output, self._expected_type)
        return output

    @abstractmethod
    def execute(self, caller, *args, **kwargs) -> Optional[ITarget]:
        pass


class StrategyGenerate(GenericStrategy):
    def generate(self, caller, *args, **kwargs) -> Optional[object]:
        return self.execute(caller, *args, **kwargs)


class StrategyCreate(GenericStrategy):
    def create(self, processor: IProcessor, *args, **kwargs) -> Optional[ITarget]:
        return self.call(caller=processor, *args, **kwargs)


class StrategyRead(GenericStrategy):
    def read(self, identifier: str, item: ITarget, **kwargs) -> Optional[ITarget]:
        return self.call(identifier=identifier, item=item, **kwargs)


class StrategyWrite(GenericStrategy):
    def __init__(
        self,
        expected_type=bool,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        self.evaluate(expected_type, bool)

        GenericStrategy.__init__(
            self, expected_type=expected_type, level=level, handler=handler
        )

    def write(
        self,
        pipeline: IPipeline,
        repository: IRepository,
        item: ITarget,
        *args,
        **kwargs,
    ) -> bool:
        return self.call(pipeline, repository, item=item, **kwargs)
