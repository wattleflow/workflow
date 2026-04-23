# Module name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines concrete Repository classes within the Wattleflow
Workflow framework. It provides structured and reusable mechanisms for managing
data persistence, ensuring consistency between business logic, drivers, and
read/write strategies. The repositories coordinate controlled data operations,
supporting extensible design patterns aligned with Wattleflow’s “build once,
use often” philosophy.
"""

from __future__ import annotations
from abc import ABC
from logging import NOTSET
from typing import Any, Optional, Union
from wattleflow.core import IRepository, IStrategy, ITarget, IWattleflow
from wattleflow.constants.enums import Event
from wattleflow.concrete import AuditLogger, GenericDriver
from wattleflow.concrete.exception import RepositoryException
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute, ClassLoader


class GenericRepository(IRepository, AuditLogger, ABC):
    __slots__ = (
        "_write_counter",
        "_preset",
        "_strategy_read",
        "_strategy_write",
    )

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

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_read=strategy_read,
            strategy_write=strategy_write,
            **kwargs,
        )

        Attribute.evaluate(
            caller=self,
            target=strategy_write,
            expected_type=IStrategy,
        )

        self._write_counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read or None
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            strategy_read=self._strategy_read,
            strategy_write=self._strategy_write,
        )

    @property
    def count(self) -> int:
        return self._write_counter

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
            facade: ITarget = self._strategy_read.read(  # type: ignore
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
            self.exception(
                msg=error,
                caller=self,
                error=e,
                id=identifier,
            )
            raise RepositoryException(caller=self, error=error, id=identifier) from e

        return facade

    # region FIX: v0.0.0.62 - 26/3/17
    # - Added Attribute.evaluate() guard for caller before
    # accessing caller.name; previously an invalid caller raised an unhandled AttributeError
    # outside the try/except block, bypassing the structured error reporting path.
    # - Moved _write_counter increment to after a successful
    # strategy write; previously the counter was incremented before the write executed,
    # so a failed write still increased the count, making count() unreliable.
    # endregion FIX: v0.0.0.62 - 26/3/17
    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        try:
            self.debug(
                msg=Event.Write.value,
                step=Event.Started.value,
                caller=caller.name,
                counter=self._write_counter,
                facade=facade,
            )

            Attribute.evaluate(caller=self, target=caller, expected_type=IWattleflow)
            Attribute.evaluate(caller=self, target=facade, expected_type=ITarget)

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
            self.exception(
                msg=error,
                caller=caller,
                error=e,
                counter=self._write_counter,
            )
            raise RepositoryException(caller=self, error=error, facade=facade) from e

    def __eq__(self, other: "GenericRepository") -> bool:
        if not isinstance(other, GenericRepository):
            return NotImplemented
        self.info(msg=Event.Probing.value, eq=hash(self) == hash(other))
        return hash(self) == hash(other)

    # region FIX: v0.0.0.62 - 26/3/17 - Removed mutable _write_counter from hash tuple
    # including a value that changes on every write() call caused the object's hash
    # to change whilst it was stored in sets or dicts, producing silent look-up failures.
    # Also removed the duplicate self._driver entry (was listed twice).
    # endregion FIX: v0.0.0.62 - 26/3/17 - Removed mutable _write_counter from hash tuple
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

    # region FIX: v0.0.0.62 - 26/3/17 - Fixed mismatched bracket in f-string; the original
    # produced "Name:[12345):0]" — a stray ")" replaced with the correct closing "]".
    # endregion FIX: v0.0.0.62 - 26/3/17 - Fixed mismatched bracket in f-string; the original
    def __repr__(self) -> str:
        return f"{self.name}:[{id(self)}:{self._write_counter}]:[{self.levelname}]"


class GenericRepositoryDriver(IRepository, AuditLogger, ABC):
    __slots__ = (
        "_write_counter",
        "_driver",
        "_strategy_read",
        "_strategy_write",
    )

    def __init__(
        self,
        strategy_write: StrategyWrite,
        strategy_read: Optional[StrategyRead] = None,
        **kwargs,
    ):

        level = kwargs.pop("level", NOTSET)
        handler = kwargs.pop("handler", None)

        driver = kwargs.pop("driver", None)
        if driver is None:
            raise ValueError(f"{self.__class__.__name__}: Missing driver parameter!")

        Attribute.evaluate(
            caller=self,
            target=strategy_write,
            expected_type=IStrategy,
        )

        IRepository.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_read=strategy_read,
            strategy_write=strategy_write,
            level=level,
            handler=handler,
            driver=driver,
            **kwargs,
        )

        self._write_counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read or None
        self._driver: GenericDriver = (
            driver
            if isinstance(driver, GenericDriver)
            else ClassLoader(class_path=driver, **kwargs).instance
        )

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            driver=self._driver,
            strategy_read=self._strategy_read,
            strategy_write=self._strategy_write,
        )

    @property
    def count(self) -> int:
        return self._write_counter

    @property
    def driver(self) -> GenericDriver:
        return self._driver

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

        facade: ITarget = self._strategy_read.read(  # type: ignore
            caller=self,
            identifier=identifier,
            **kwargs,
        )

        self.debug(
            msg=Event.Read.value,
            step=Event.Completed.value,
            facade=facade,
        )

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

            Attribute.evaluate(caller=self, target=caller, expected_type=IWattleflow)
            Attribute.evaluate(caller=self, target=facade, expected_type=ITarget)

            result: bool = self._strategy_write.write(
                caller=caller,
                facade=facade,
                repository=self,
                driver=self.driver,
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
            error = "[%s] Write strategy `%s` failed: %s" % (
                self.name,
                self._strategy_write.name,
                str(e),
            )

            self.exception(
                msg=error,
                caller=caller,
                error=e,
                counter=self._write_counter,
            )
            raise RepositoryException(caller=self, error=error, facade=facade) from e

    def __eq__(self, other: "GenericRepositoryDriver") -> bool:
        if not isinstance(other, GenericRepositoryDriver):
            return NotImplemented
        self.info(msg=Event.Probing.value, eq=hash(self) == hash(other))
        return hash(self) == hash(other)

    def __hash__(self) -> int:
        return hash(
            (
                id(self),
                self.name,
                self._driver,
                self._strategy_write,
                self._strategy_read,
            )
        )

    def __repr__(self) -> str:
        return f"{self.name}:[{id(self)}:{self._write_counter}]:[{self.levelname}]"
