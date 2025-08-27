# Module Name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains repository classes.

from abc import ABC
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IRepository, IStrategy, ITarget, IWattleflow
from wattleflow.constants.enums import Event
from wattleflow.concrete import (
    AuditLogger,
)
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.helpers import Attribute

PERMITED_SLOTS = (
    "_allowed",
    "_counter",
    "_strategy_read",
    "_strategy_write",
    "_preset",
    "_initialised",
)


class GenericRepository(IRepository, AuditLogger, ABC):
    __slots__ = PERMITED_SLOTS

    def __init__(
        self,
        strategy_write: StrategyWrite,
        strategy_read: Optional[StrategyRead] = None,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):

        IRepository.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            strategy_read=strategy_read,
            strategy_write=strategy_write,
            *args,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=strategy_read, expected_type=IStrategy)
        Attribute.evaluate(caller=self, target=strategy_write, expected_type=IStrategy)

        self._counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read

        from wattleflow.helpers.preset import Preset

        self._preset: Preset = Preset()
        self._preset.configure(self, raise_errors=True, **kwargs)

        self.debug(msg=Event.Constructor.value, status="created")

    @property
    def count(self) -> int:
        return self._counter

    def clear(self) -> None:
        self.debug(msg=Event.Cleaning.value)
        self._counter = 0

    def read(self, identifier: str, *args, **kwargs) -> ITarget:
        self.debug(
            Event.Reading.value,
            id=identifier,
            **kwargs,
        )

        document: ITarget = self._strategy_read.read(  # type: ignore
            caller=self,
            identifier=identifier,
            *args,
            **kwargs,
        )

        self.info(
            msg=Event.Retrieved.value,
            id=Attribute.get_attr(document, "identifier"),
            document=document,
        )

        return document

    def write(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Storing.value,
            caller=caller.name,
            document=document,
            counter=self._counter,
        )

        try:
            Attribute.evaluate(caller=self, target=document, expected_type=ITarget)
            self._counter += 1
            result: bool = self._strategy_write.write(
                caller=caller,
                document=document,
                repository=self,
                **kwargs,
            )
            return result

        except Exception as e:
            error = f"[{self.name}] Write strategy failed: {e}"
            self.error(
                msg=error, counter=self._counter
            )  # TODO: self.exception to self.error
            raise RuntimeError(error) from e

    def __getattr__(self, name: str) -> object:
        if name in self.__slots__:
            return Attribute.get_attr(caller=self, name=name)

        return Attribute.get_attr(caller=self._preset, name=name)

    def __repr__(self) -> str:
        return f"{self.name}: {self.count}"
