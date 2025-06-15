# Module Name: concrete/strategies.py
# Description: This modul contains concrete strategy classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


from abc import abstractmethod, ABC
from logging import Handler, NOTSET
from typing import Any, Generic, Optional
from wattleflow.core import IStrategy, ITarget, T, C
from wattleflow.concrete import Attribute, AuditLogger


# Generic strategy
class Strategy(IStrategy, Attribute, ABC):
    _expected_type = None

    @abstractmethod
    def call(self, caller: C, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def execute(self, caller: C, *args, **kwargs) -> Any:
        pass


class GenericStrategy(Strategy, Generic[T], AuditLogger, ABC):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        Strategy.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

    def call(self, caller: C, *args, **kwargs) -> Optional[T]:
        output = self.execute(caller, *args, **kwargs)
        type_hint = kwargs.get("type_hint")
        if type_hint and not isinstance(
            output, (type_hint if isinstance(type_hint, tuple) else (type_hint,))
        ):
            raise TypeError(f"Expected {type_hint}, got {type(output)}")

        return output

    @abstractmethod
    def execute(self, caller: C, *args, **kwargs) -> Optional[T]:
        pass


class StrategyGenerate(GenericStrategy, Generic[T], ABC):
    def generate(self, caller: C, *args, **kwargs) -> Optional[T]:
        return self.execute(caller, *args, **kwargs)


class StrategyCreate(GenericStrategy, Generic[T], ABC):
    def create(self, caller: C, *args, **kwargs) -> T:
        return self.execute(caller, *args, **kwargs)


class StrategyRead(GenericStrategy, Generic[T], ABC):
    def read(self, caller: C, identifier: str, *args, **kwargs) -> Optional[T]:
        return self.call(caller=caller, identifier=identifier, *args, **kwargs)


class StrategyWrite(GenericStrategy, Generic[T], ABC):
    def write(self, caller: C, item: ITarget, *args, **kwargs) -> Optional[T]:
        return self.call(caller=caller, item=item, *args, **kwargs)
