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
    IPipeline,
    IProcessor,
    IRepository,
    IWattleflow,
    T,
)
from wattleflow.concrete.logger import AuditLogger
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants.enums import Event
from wattleflow.decorators.preset import PresetDecorator


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

Repositories = List[IRepository]

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region State                                                                #
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
    READ = "read"  # facade pročitan iz canvasa (rezervirano — nema tranziciju)
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


# --------------------------------------------------------------------------- #
# endregion State                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Blacboards                                                           #
# --------------------------------------------------------------------------- #


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

        # defer_flush default je True (normalan rad: cache kroz cycle, flush na kraju).
        # Postavi se na False za audit/debug — pisanje pri svakoj izmjeni.
        if "defer_flush" not in kwargs:
            kwargs["defer_flush"] = True

        assert isinstance(strategy_create, StrategyCreate), (
            "Expected StrategyCreate. Found %s" % type(strategy_create)
        )

        IBlackboard.__init__(self)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        AuditLogger.__init__(self, level=level, handler=handler, **fmt)
        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.name,
            strategy_create=strategy_create,
            kwargs=kwargs,
        )

        self._strategy_create = strategy_create
        self._canvas: T = canvas
        self._repositories: Repositories = []

        self.debug(msg=Event.Constructor.value, step=Event.Completed.name)

    def __del__(self):
        # __init__ may have raised before _preset was set — in that case any
        # debug/clean call would hit __getattr__ and mask the real exception.
        try:
            object.__getattribute__(self, "_preset")
        except AttributeError:
            return
        try:
            self.debug(msg=Event.Delete.name, step=Event.Started.name)
            self.clean()
            self._strategy_create = None
            self._preset = None
            self.debug(msg=Event.Delete.name, step=Event.Completed.name)
        except Exception as e:
            reason = "Destructor %s error: %s" % (self.__class__.__name__, str(e))
            try:
                self.error(msg=Event.Delete.name, reason=reason)
            except Exception:
                pass

    def __getattr__(self, name: str) -> Any:
        # During partial construction _preset is not set yet; raise a plain
        # AttributeError so callers (and Python itself) can treat the attribute
        # as missing instead of seeing a confusing internal trace.
        try:
            preset: PresetDecorator = object.__getattribute__(self, "_preset")
        except AttributeError:
            raise AttributeError(name) from None
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

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
    def create(self, caller: IProcessor, **kwargs) -> T: ...

    @abstractmethod
    def delete(self, identifier: str, **kwargs) -> None: ...

    @abstractmethod
    def flush(self, caller: IWattleflow, **kwargs) -> None: ...

    @abstractmethod
    def read(self, identifier: str, **kwargs) -> T: ...

    @abstractmethod
    def write(self, pipeline: IPipeline, facade: Any, **kwargs) -> Any: ...

    # endregion Abstract


# --------------------------------------------------------------------------- #
# endregion Blacboards                                                        #
# --------------------------------------------------------------------------- #
