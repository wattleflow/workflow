# Module name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["GenericRepository", "RepositoryWithDriver"]

from abc import ABC
from typing import Any
from wattleflow.core import IBlackboard, IRepository, ITarget
from wattleflow.enums.event import Event
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.driver import IDriver
from wattleflow.concrete.exception import RepositoryException
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.decorators.preset import PresetDecorator


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Repositories                                                         #
# --------------------------------------------------------------------------- #


class GenericRepository(Wattleflow, IRepository, ABC):
    """Read and write documents through strategies, and count what was written."""

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
        strategy_read: StrategyRead | None = None,
        **kwargs,
    ):
        if not isinstance(strategy_write, StrategyWrite):
            raise RepositoryException(
                caller=type(self),
                error="Expected StrategyWrite. Found %s" % type(strategy_write),
            )
        if strategy_read is not None and not isinstance(strategy_read, StrategyRead):
            raise RepositoryException(
                caller=type(self),
                error="Expected StrategyRead. Found %s" % type(strategy_read),
            )

        super().__init__(**kwargs)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor,
            step=Event.Started,
            strategy_write=strategy_write,
            strategy_read=strategy_read,
            kwargs=kwargs,
        )

        self._write_counter: int = 0
        self._strategy_write: StrategyWrite = strategy_write
        self._strategy_read: StrategyRead | None = strategy_read or None

        self.debug(msg=Event.Constructor, step=Event.Completed)

    def __getattr__(self, name: str) -> Any:
        try:
            preset: PresetDecorator = object.__getattribute__(self, "_preset")
        except AttributeError:
            raise AttributeError(name) from None
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        context = "".join(
            ":%s" % getattr(value, "name", type(value).__name__)
            for value in self._strategy_context().values()
        )
        counter = self._write_counter
        level = self.levelname or "UNKNOWN"
        return f"{self.name}{context}:[{id(self)}:{counter}]:[{level}]"

    # endregion Private

    # region Protected

    def _strategy_context(self) -> dict[str, Any]:
        """Keywords this repository contributes to every strategy call."""
        return {}

    # endregion Protected

    # region Property

    @property
    def count(self) -> int:
        return self._write_counter

    # endregion Property

    # region Public

    def clear(self) -> None:
        self.info(
            msg=Event.Clear,
            written=self._write_counter,
        )
        self._write_counter = 0

    def read(self, identifier: str, **kwargs) -> ITarget | None:
        self.debug(
            msg=Event.Read,
            step=Event.Started,
            id=identifier,
            kwargs=kwargs,
        )

        if self._strategy_read is None:
            self.warning(
                msg=Event.Read,
                step=Event.Check,
                reason="Read strategy is not assigned!",
            )
            return None

        try:
            facade: ITarget = self._strategy_read.read(
                caller=self,
                identifier=identifier,
                **self._strategy_context(),
                **kwargs,
            )

            self.debug(
                msg=Event.Read,
                step=Event.Completed,
                facade=facade,
            )
        except Exception as e:
            reason = f"[{self.name}] Read strategy failed: {type(e).__name__}"
            self.debug(
                msg=Event.Read,
                step=Event.Failed,
                id=identifier,
                error=reason,
            )
            raise RepositoryException(
                caller=self,
                error=reason,
                id=identifier,
            ) from None

        return facade

    def write(self, caller: IBlackboard, facade: ITarget, **kwargs) -> bool:
        context: dict[str, Any] = self._strategy_context()
        if not isinstance(caller, IBlackboard):
            raise RepositoryException(
                caller=self, error="Expected IBlackboard. Found %s" % type(caller)
            )
        if not isinstance(facade, ITarget):
            raise RepositoryException(
                caller=self, error="Expected ITarget. Found %s" % type(facade)
            )

        try:
            self.debug(
                msg=Event.Write,
                step=Event.Started,
                caller=caller.name,
                counter=self._write_counter,
                facade=facade,
            )

            result: bool = self._strategy_write.write(
                caller=self,
                facade=facade,
                repository=self,
                **context,
                **kwargs,
            )

            if result:
                self._write_counter += 1

            self.debug(
                msg=Event.Write,
                step=Event.Completed,
                strategy=self._strategy_write.name,
                counter=self._write_counter,
            )

            return result

        except Exception as e:
            owned = {key: type(value).__name__ for key, value in context.items()}
            parts = [f"strategy={self._strategy_write.name}"]
            parts += [f"{key}={value}" for key, value in owned.items()]
            parts += [
                f"uid={facade.identifier}",
                f"caller={caller.name}",
            ]
            reason = "[%s] write failed: %s -> %s: %s" % (
                self.name,
                " ".join(parts),
                type(e).__name__,
                e,
            )

            self.debug(
                msg=Event.Write,
                step=Event.Failed,
                strategy=self._strategy_write.name,
                uid=facade.identifier,
                counter=self._write_counter,
                error=reason,
                context=owned,
            )
            raise RepositoryException(caller=self, error=reason, facade=facade) from None

    # endregion Public


class RepositoryWithDriver(GenericRepository):
    __slots__ = ()

    ALLOWED = ["driver"]

    # region Constructor

    def __init__(
        self,
        **kwargs,
    ):
        driver = kwargs.get("driver", None)
        if not isinstance(driver, IDriver):
            raise RepositoryException(
                caller=type(self),
                error="Expected IDriver. Found %s" % type(driver),
            )
        super().__init__(**kwargs)

    # endregion Constructor

    # region Protected

    def _strategy_context(self) -> dict[str, Any]:
        return {"driver": self.driver}

    # endregion Protected


# --------------------------------------------------------------------------- #
# endregion Repositories                                                      #
# --------------------------------------------------------------------------- #
