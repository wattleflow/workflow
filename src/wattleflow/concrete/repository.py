# Module name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC
from typing import Any, Optional
from wattleflow.core import IRepository, IStrategy, ITarget, IWattleflow
from wattleflow.constants.enums import Event
from wattleflow.concrete import AuditLogger
from wattleflow.concrete.exception import RepositoryException
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Repositories                                                         #
# --------------------------------------------------------------------------- #


class GenericRepository(IRepository, AuditLogger, ABC):
    __slots__ = (
        "_write_counter",
        "_preset",
        "_strategy_read",
        "_strategy_write",
    )

    # region Private

    def __init__(
        self,
        strategy_write: StrategyWrite,
        strategy_read: Optional[StrategyRead] = None,
        **kwargs,
    ):
        level = kwargs.pop("level", 0)
        handler = kwargs.pop("handler", None)

        IRepository.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_read=strategy_write,
            strategy_write=strategy_read,
            kwargs=kwargs,
        )

        Attribute.evaluate(self, strategy_write, IStrategy)

        self._write_counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read or None

        self.debug(msg=Event.Constructor.value, step=Event.Completed.value)

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
                self._driver,
                self._preset,
                self._strategy_write,
                self._strategy_read,
            )
        )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        counter = str(self._write_counter) or "0"
        level = self.name or "UNKNOWN"
        return f"{name}:[{id(self)}:{counter}]:[{level}]"

    # endregion Private

    # region Property

    @property
    def count(self) -> int:
        return self._write_counter

    # endregion Property

    # region Public

    def clear(self) -> None:
        self.debug(
            msg=Event.Clear.value,
            step=Event.Started.value,
        )
        self._write_counter = 0

    def read(self, identifier: str, **kwargs) -> Optional[ITarget]:
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

        try:
            facade: ITarget = self._strategy_read.read(
                caller=self,
                identifier=identifier,
                **kwargs,
            )

            self.debug(
                msg=Event.Read.value,
                step=Event.Completed.value,
                facade=facade,
            )
        except Exception as e:
            error = f"[{self.name}] Read strategy failed: {e}"
            self.error(
                msg=error,
                caller=self,
                error=e,
                id=identifier,
            )
            raise RepositoryException(caller=self, error=error, id=identifier) from e

        return facade

    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        try:
            self.debug(
                msg=Event.Write.value,
                step=Event.Started.value,
                caller=caller.name,
                counter=self._write_counter,
                facade=facade,
            )

            Attribute.evaluate(self, caller, IWattleflow)
            Attribute.evaluate(self, facade, ITarget)

            result: bool = self._strategy_write.write(
                caller=caller,
                facade=facade,
                repository=self,
                **kwargs,
            )

            self._write_counter += 1

            self.debug(
                msg=Event.Write.value,
                step=Event.Completed.value,
                counter=self._write_counter,
                facade=facade,
            )

            return result

        except Exception as e:
            error = f"[{self.name}] Write strategy failed: {e}"
            self.error(
                msg=error,
                caller=caller,
                error=e,
                counter=self._write_counter,
            )
            raise RepositoryException(caller=self, error=error, facade=facade) from e

    # endregion Public


# --------------------------------------------------------------------------- #
# endregion Repositories                                                      #
# --------------------------------------------------------------------------- #
