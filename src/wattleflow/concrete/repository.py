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
from wattleflow.core import IBlackboard, IRepository, ITarget
from wattleflow.constants.enums import Event
from wattleflow.concrete.wattleflow import Wattleflow
from wattleflow.concrete.driver import GenericDriver
from wattleflow.concrete.exception import RepositoryException
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers.system import ClassLoader

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Repositories                                                         #
# --------------------------------------------------------------------------- #


class GenericRepository(Wattleflow, IRepository, ABC):
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
        assert isinstance(strategy_write, StrategyWrite), (
            "Expected StrategyWrite. Found %s" % type(strategy_write)
        )
        if strategy_read is not None:
            assert isinstance(strategy_read, StrategyRead), (
                "Expected StrategyRead. Found %s" % type(strategy_read)
            )

        super().__init__(**kwargs)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.name,
            strategy_write=strategy_write,
            strategy_read=strategy_read,
            kwargs=kwargs,
        )

        self._write_counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: Optional[StrategyRead] = strategy_read or None

        self.debug(msg=Event.Constructor.value, step=Event.Completed.name)

    def __eq__(self, other: "GenericRepository") -> bool:
        if not isinstance(other, GenericRepository):
            return NotImplemented
        self.debug(msg=Event.Probing.value, eq=hash(self) == hash(other))
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
            step=Event.Started.name,
        )
        self._write_counter = 0

    def read(self, identifier: str, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.name,
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
            # caller=self -> Strategy.execute asertira IRepository.
            facade: ITarget = self._strategy_read.read(
                caller=self,
                identifier=identifier,
                **kwargs,
            )

            self.debug(
                msg=Event.Read.value,
                step=Event.Completed.name,
                facade=facade,
            )
        except Exception as e:
            reason = f"[{self.name}] Read strategy failed: {e}"
            self.error(
                msg=Event.Read.name,
                caller=self,
                reason=reason,
                id=identifier,
                # trace=traceback.format_exc(),
            )
            raise RepositoryException(
                caller=self,
                error=reason,
                id=identifier,
                # trace=traceback.format_exc(),
            ) from e

        return facade

    def write(self, caller: IBlackboard, facade: ITarget, **kwargs) -> bool:
        try:
            self.debug(
                msg=Event.Write.value,
                step=Event.Started.name,
                caller=caller.name,
                counter=self._write_counter,
                facade=facade,
            )

            assert isinstance(caller, IBlackboard), (
                "Expected IBlackboard. Found %s" % type(caller)
            )
            assert isinstance(facade, ITarget), "Expected ITarget. Found %s" % type(
                facade
            )

            # The repository passes ITSELF as caller so the owning blackboard
            # Strategy.execute asertira (IRepository, IDriver) — upstream caller
            # does not leak into the strategy layer.
            result: bool = self._strategy_write.write(
                caller=self,
                facade=facade,
                repository=self,
                **kwargs,
            )

            self._write_counter += 1

            self.debug(
                msg=Event.Write.value,
                step=Event.Completed.name,
                counter=self._write_counter,
                facade=facade,
            )

            return result

        except Exception as e:
            reason = "%s.write strategy failed:  %s!" % self.__class__.__name__, str(e)
            self.error(
                msg=Event.Write.name,
                caller=caller,
                reason=reason,
                counter=self._write_counter,
                # trace=traceback.format_exc(),
            )
            raise RepositoryException(caller=self, error=reason, facade=facade) from e

    # endregion Public


class RepositoryWithDriver(GenericRepository):
    ALLOWED = [
        "driver",
    ]

    # region Private

    def __init__(
        self,
        strategy_write: StrategyWrite,
        strategy_read: Optional[StrategyRead] = None,
        **kwargs,
    ):

        driver = kwargs.pop("driver", None)
        if driver is None:
            raise ValueError(f"{self.__class__.__name__}: Missing driver parameter!")

        super().__init__(
            strategy_write=strategy_write, strategy_read=strategy_read, **kwargs
        )

        self._driver: GenericDriver = (
            driver
            if isinstance(driver, GenericDriver)
            else ClassLoader(class_path=driver, **kwargs).instance
        )

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
        name = self.name or self.__class__.__name__
        counter = self._write_counter
        level = self.levelname or "UNKNOWN"
        driver = self.driver.name
        return f"{name}:{driver}:{counter}:[{level}]"

    # endregion Private

    # region Property
    @property
    def count(self) -> int:
        return self._write_counter

    @property
    def driver(self) -> GenericDriver:
        return self._driver

    # endregion Property

    # region Public

    def clear(self) -> None:
        self.debug(msg=Event.Clear.value, step=Event.Started.value)
        self._write_counter = 0
        self._driver.clear()
        self._strategy_write = None
        self._strategy_read = None
        self.debug(msg=Event.Clear.value, step=Event.Completed.value)

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

    def write(self, caller: IBlackboard, facade: ITarget, **kwargs) -> bool:
        try:
            self.debug(
                msg=Event.Write.value,
                step=Event.Started.value,
                caller=caller.name,
                counter=self._write_counter,
                facade=facade,
            )

            assert isinstance(caller, IBlackboard), (
                "Expected IBlackboard. Found %s" % type(caller)
            )
            assert isinstance(facade, ITarget), "Expected ITarget. Found %s" % type(
                facade
            )

            # The repository passes ITSELF as caller so the owning blackboard
            # Strategy.execute asertira (IRepository, IDriver).
            result: bool = self._strategy_write.write(
                caller=self,
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
            strategy_cls = self._strategy_write.__class__.__name__
            driver_cls = self._driver.__class__.__name__
            doc_id = getattr(facade, "identifier", None)
            root = type(e).__name__
            error = (
                f"[{self.name}] write failed: strategy={strategy_cls} "
                f"driver={driver_cls} document={doc_id} "
                f"caller={getattr(caller, 'name', caller.__class__.__name__)} "
                f"-> {root}: {e}"
            )

            self.exception(
                msg=error,
                caller=caller,
                error=e,
                strategy=strategy_cls,
                driver=driver_cls,
                document=doc_id,
                counter=self._write_counter,
                # trace=traceback.format_exc(),
            )
            raise RepositoryException(caller=self, error=error, facade=facade) from e

    # endregion Public


# --------------------------------------------------------------------------- #
# endregion Repositories                                                      #
# --------------------------------------------------------------------------- #
