# Module Name: core/concrete/strategies.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete strategy classes.


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
from typing import Optional
from wattleflow.core import IStrategy
from wattleflow.core import ITarget
from wattleflow.core import IPipeline, IProcessor, IRepository
from wattleflow.concrete.attribute import Attribute


# Generic strategy
class Strategy(IStrategy, Attribute, ABC):
    @abstractmethod
    def call(self, caller, *args, **kwargs) -> object:
        pass

    @abstractmethod
    def execute(self, caller, *args, **kwargs) -> object:
        pass


class GenericStrategy(Strategy, ABC):
    def __init__(self, expected_type=ITarget):
        super().__init__()
        self.evaluate(expected_type, ITarget)
        self._expected_type = expected_type

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
    def read(self, pipeline: IPipeline, identifier: str, **kwargs) -> Optional[ITarget]:
        return self.call(caller=pipeline, identifier=identifier, **kwargs)


class StrategyWrite(GenericStrategy):
    def __init__(self):
        self._expected_type = bool

    def write(
        self, pipeline: IPipeline, repository: IRepository, item, *args, **kwargs
    ) -> bool:
        return self.call(pipeline, repository, item=item, **kwargs)
