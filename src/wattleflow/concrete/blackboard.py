# Module name: concrete/blackboard.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from logging import Handler
from types import MappingProxyType
from typing import (
    Any,
    List,
    Generic,
    Mapping,
    Optional,
    Union,
)
from wattleflow.core import (
    IBlackboard,
    IRepository,
    T,
)
from wattleflow.concrete.logger import AuditLogger
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants.enums import Event
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers.attribute import Attribute


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


Repositories = List[IRepository]


# --------------------------------------------------------------------------- #
# region Blacboards                                                           #
# --------------------------------------------------------------------------- #


class BlackboardState(str, Enum):
    IDLE = "idle"  # konstruirano, bez repozitorija
    READY = "ready"  # ima repozitorije, canvas u sinku
    DIRTY = "dirty"  # canvas ima unflushed facade
    FAILED = "failed"  # greška
    CLEARED = "cleared"  # clean() — terminalno


class BlackboardAction(str, Enum):
    REGISTER = "register"  # repository pridružen
    WRITE = "write"  # facade upisan u canvas
    FLUSH = "flush"  # broadcast u repozitorije, canvas u sink
    LOAD = "load"  # restore iz mementa
    FAIL = "fail"  # greška
    CLEAN = "clean"  # terminalni reset


TRANSITIONS = {
    # --- INIT ---
    (BlackboardState.IDLE, BlackboardAction.REGISTER): BlackboardState.READY,
    (BlackboardState.IDLE, BlackboardAction.LOAD): BlackboardState.READY,
    # --- READY ---
    (BlackboardState.READY, BlackboardAction.REGISTER): BlackboardState.READY,
    (BlackboardState.READY, BlackboardAction.WRITE): BlackboardState.DIRTY,
    (BlackboardState.READY, BlackboardAction.FLUSH): BlackboardState.READY,
    # --- DIRTY ---
    (BlackboardState.DIRTY, BlackboardAction.WRITE): BlackboardState.DIRTY,
    (BlackboardState.DIRTY, BlackboardAction.FLUSH): BlackboardState.READY,
    # --- RECOVERY ---
    (BlackboardState.FAILED, BlackboardAction.LOAD): BlackboardState.READY,
    # --- FAILURE ---
    (BlackboardState.IDLE, BlackboardAction.FAIL): BlackboardState.FAILED,
    (BlackboardState.READY, BlackboardAction.FAIL): BlackboardState.FAILED,
    (BlackboardState.DIRTY, BlackboardAction.FAIL): BlackboardState.FAILED,
    # --- CLEAN (terminalno iz bilo kojeg stanja) ---
    (BlackboardState.IDLE, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.READY, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.DIRTY, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.FAILED, BlackboardAction.CLEAN): BlackboardState.CLEARED,
}


class GenericBlackboard(IBlackboard, Generic[T], AuditLogger, ABC):
    __slots__ = (
        "_canvas",
        "_preset",
        "_repositories",
        "_strategy_create",
    )

    # region Private
    def __init__(
        self,
        strategy_create: StrategyCreate,
        canvas: T,
        **kwargs,
    ):
        level: Union[str, int] = kwargs.pop("level", "NOTSET")
        handler: Optional[Handler] = kwargs.pop("handler", None)
        fmt: dict = {"fmt": kwargs.pop("fmt", {})} if kwargs.get("fmt", None) else {}

        IBlackboard.__init__(self)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        AuditLogger.__init__(self, level=level, handler=handler, **fmt)
        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_create=strategy_create,
            kwargs=kwargs,
        )

        Attribute.evaluate(self, strategy_create, StrategyCreate)

        self._strategy_create = strategy_create
        self._canvas: T = canvas
        self._repositories: Repositories = []

        self.debug(msg=Event.Constructor.value, step=Event.Completed.value)

    def __del__(self):
        try:
            self.debug(msg=Event.Delete.name, step=Event.Started.name)
            self.clean()
            self._strategy_create = None
            self._preset = None
            self.debug(msg=Event.Delete.name, step=Event.Completed.name)
        except Exception as e:
            self.error(msg=Event.Delete.name, error=str(e))

    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        if preset:
            return preset.__getattr__(name)
        return None

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        level = self.levelname or ""
        repos = self._repositories or "[0]"
        count = self.count or 0
        return f"{name}:{count}:{repos}:[{level}]"

    # endregion Private

    # region Property
    @property
    def canvas(self) -> Mapping[T]:
        return MappingProxyType(self._canvas)

    @property
    @abstractmethod
    def count(self) -> int: ...

    @property
    def repositories(self) -> Repositories:
        return list(self._repositories)

    # endregion Properties

    # region Abstract
    @abstractmethod
    def clean(self): ...

    @abstractmethod
    def create(self, **kwargs) -> T: ...

    @abstractmethod
    def delete(self, **kwargs) -> None: ...

    @abstractmethod
    def flush(self, **kwargs) -> None: ...

    @abstractmethod
    def read(self, **kwargs) -> T: ...

    # endregion Abstract


# --------------------------------------------------------------------------- #
# endregion Blacboards                                                        #
# --------------------------------------------------------------------------- #
