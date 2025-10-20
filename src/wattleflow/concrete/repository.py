# Module Name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains repository classes.

from abc import ABC
from logging import Handler, NOTSET
from typing import Any, Optional
from wattleflow.core import IUnitOfWork, IRepository, IStrategy, ITarget, IWattleflow
from wattleflow.constants.enums import Event
from wattleflow.concrete import AuditLogger
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute


class GenericRepository(IRepository, AuditLogger):
    __slots__ = (
        "_counter",
        "_driver",
        "_initialized",
        "_preset",
        "_strategy_read",
        "_strategy_write",
    )

    def __init__(
        self,
        strategy_write: StrategyWrite,
        strategy_read: Optional[StrategyRead] = None,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        driver: Optional[IUnitOfWork] = None,
        *args,
        **kwargs,
    ):

        IRepository.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_read=strategy_read,
            strategy_write=strategy_write,
            *args,
            **kwargs,
        )

        Attribute.evaluate(
            caller=self,
            target=strategy_write,
            expected_type=IStrategy,
        )

        self._counter: int = 0
        self._driver = driver
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read or None
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)
        self.debug(msg=Event.Constructor.value, step=Event.Finnished.value)

    @property
    def count(self) -> int:
        return self._counter

    def clear(self) -> None:
        self.debug(
            msg=Event.Clear.value,
            step=Event.Started.value,
        )
        self._counter = 0

    def read(self, identifier: str, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            id=identifier,
            **kwargs,
        )

        if self._strategy_read is None:
            self.warning(
                msg=Event.Read.value,
                step=Event.Configuration.value,
                error="Read strategy is not assigned!",
            )
            return None

        document: ITarget = self._strategy_read.read(  # type: ignore
            caller=self,
            identifier=identifier,
            *args,
            **kwargs,
        )

        self.info(
            msg=Event.Read.value,
            step=Event.Completed.value,
            document=document,
        )

        return document

    def write(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
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

            self.debug(
                msg=Event.Write.value,
                step=Event.Completed.value,
                caller=caller.name,
                document=document,
                counter=self._counter,
            )

            return result

        except Exception as e:
            error = f"[{self.name}] Write strategy failed: {e}"
            self.exception(
                msg=error,
                caller=caller,
                error=e,
                counter=self._counter,
            )
            raise RuntimeError(error) from e

    def __eq__(self, other: "GenericRepository") -> bool:
        if not isinstance(other, GenericRepository):
            return NotImplemented
        self.info(msg=Event.Probing.value, eq=hash(self) == hash(other))
        return hash(self) == hash(other)

    def __hash__(self) -> int:
        return hash(
            (
                id(self),
                self.name,
                self._counter,
                self._driver,
                self._preset,
                self._strategy_write,
                self._strategy_read,
                self._driver,
            )
        )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}:[{id(self)})]"
