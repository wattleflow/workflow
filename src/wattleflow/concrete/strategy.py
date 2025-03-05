# Module Name: core/concrete/strategies.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete strategy classes.

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
        self.name = self.__class__.__name__
        self.evaluate(expected_type, ITarget)
        self._expected_type = expected_type

    def call(self, caller, *args, **kwargs) -> object:
        output = self.execute(caller, *args, **kwargs)
        self.evaluate(output, self._expected_type)
        return output

    @abstractmethod
    def execute(self, caller, *args, **kwargs) -> Optional[ITarget]:
        pass


# Blackboard strategies - Generate | Create | Read | Write
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
