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
from types import MappingProxyType
from typing import (
    Any,
    Generic,
)
from collections.abc import Mapping
from wattleflow.core import (
    IBlackboard,
    IPipeline,
    IProcessor,
    IRepository,
    IWattleflow,
)
from wattleflow.core.transactional import Item
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import BlackboardException
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator
# from wattleflow.decorators.measure import measured  # retired


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

Repositories = list[IRepository]

# --------------------------------------------------------------------------- #
# region State                                                                #
# --------------------------------------------------------------------------- #


class BlackboardState(str, Enum):
    IDLE = "idle"  # constructed, no repositories yet
    READY = "ready"  # repositories attached, canvas in sync
    DIRTY = "dirty"  # canvas holds an unflushed facade
    FAILED = "failed"
    CLEARED = "cleared"  # terminal


class BlackboardAction(str, Enum):
    REGISTER = "register"  # repository attached
    WRITE = "write"
    FLUSH = "flush"  # broadcast to repositories
    LOAD = "load"  # restore from memento
    FAIL = "fail"
    CLEAN = "clean"  # terminal reset


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
    # --- CLEAN (terminal, from any state) ---
    (BlackboardState.IDLE, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.READY, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.DIRTY, BlackboardAction.CLEAN): BlackboardState.CLEARED,
    (BlackboardState.FAILED, BlackboardAction.CLEAN): BlackboardState.CLEARED,
}


# --------------------------------------------------------------------------- #
# endregion State                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Blackboards                                                           #
# --------------------------------------------------------------------------- #


# Wattleflow precedes Generic[Item] so IWattleflow lands before Generic in the MRO,
# matching IOriginator's ordering; otherwise LargeBlackboard (GenericBlackboard +
# IOriginator) cannot linearise a consistent MRO.


# @measured()
class GenericBlackboard(Wattleflow, IBlackboard, Generic[Item], ABC):
    __slots__ = (
        "_canvas",
        "_fsm",
        "_preset",
        "_repositories",
        "_strategy_create",
    )

    # The generic layer injects this key, so it declares it; PresetGate unions
    # ALLOWED across the MRO, so a specialisation adds only its own keys.
    ALLOWED = ["defer_flush"]

    # region Private
    def __init__(
        self,
        strategy_create: StrategyCreate,
        canvas: Item,
        **kwargs,
    ):
        assert isinstance(strategy_create, StrategyCreate), (
            "Expected StrategyCreate. Found %s" % type(strategy_create)
        )

        # `fmt` was this class's own spelling of the logger's `formatting`, so
        # it never reached the logger; accepted as an alias so existing callers
        # keep working.
        if "fmt" in kwargs:
            kwargs.setdefault("formatting", kwargs.pop("fmt"))

        # Default to caching through the cycle and flushing at the end.
        if "defer_flush" not in kwargs:
            kwargs["defer_flush"] = True

        super().__init__(**kwargs)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        self.debug(
            msg=Event.Constructor,
            step=Event.Started,
            strategy_create=strategy_create,
            kwargs=kwargs,
        )

        self._strategy_create = strategy_create
        self._canvas: Item = canvas
        self._repositories: Repositories = []
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            BlackboardState.IDLE,
            name=type(self).__name__,
        )

        self.debug(msg=Event.Constructor, step=Event.Completed)

    def __del__(self):
        # __init__ may have raised before _preset was set — in that case any
        # debug/clean call would hit __getattr__ and mask the real exception.
        try:
            object.__getattribute__(self, "_preset")
        except AttributeError:
            return
        try:
            self.debug(msg=Event.Delete, step=Event.Started)
            self.clean()
            self._strategy_create = None
            self._preset = None
            self.debug(msg=Event.Delete, step=Event.Completed)
        except Exception as e:
            reason = "Destructor %s error: %s" % (self.__class__.__name__, str(e))
            try:
                self.error(msg=Event.Delete, reason=reason)
            except Exception:
                pass

    def __getattr__(self, name: str) -> Any:
        # During partial construction _preset is not set yet; raise a plain
        # AttributeError so callers (and Python itself) can treat the attribute
        # as missing instead of seeing a confusing internal trace.
        try:
            preset: PresetDecorator | None = object.__getattribute__(self, "_preset")
        except AttributeError:
            preset = None
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

    def __len__(self) -> int:
        return self.count

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        level = self.levelname or ""
        repos = self._repositories or "[0]"
        count = self.count or 0
        return f"{name}:{count}:{repos}:[{level}]"

    # endregion Private

    # region Property
    @property
    def canvas(self) -> Mapping[str, Item]:
        """Read-only view of the canvas: a mapping from identifier to item.

        A specialisation that keeps a single item overrides this property and
        answers with a one-entry (or empty) mapping.
        """
        return MappingProxyType(self._canvas)

    @property
    def state(self) -> BlackboardState:
        return self._fsm.state

    @property
    @abstractmethod
    def count(self) -> int: ...

    @property
    def repositories(self) -> Repositories:
        return list(self._repositories)

    # endregion Properties

    # region Public
    def register(self, repository: IRepository) -> None:
        self.debug(msg=Event.Register, step=Event.Started, repository=repository)
        assert isinstance(repository, IRepository), (
            "Expected IRepository. Found %s" % type(repository)
        )

        if repository in self._repositories:
            self.warning(
                msg=Event.Register,
                repository=repository,
                error="Repository already registered!",
            )
            return

        self._transition(BlackboardAction.REGISTER)
        self._repositories.append(repository)
        self._registered(repository)
        self.debug(msg=Event.Register, step=Event.Completed, added=repository)

    # endregion Public

    # region Protected
    def _transition(self, action: BlackboardAction) -> None:
        """Apply `action`; a transition the table does not allow is refused.

        Used for REGISTER, WRITE, FLUSH and LOAD: a call the automaton rejects
        must not change the canvas, so the caller transitions first.
        """
        if not self._fsm.can(action):
            raise BlackboardException(
                self,
                error=f"{action.name} is not allowed in state {self._fsm.state.name}.",
            )
        self._fsm.apply(action)

    def _try_transition(self, action: BlackboardAction) -> bool:
        """Apply `action` when allowed and answer whether it was; never raises.

        Used for FAIL and CLEAN, which must stay safe to repeat and to call
        from a destructor.
        """
        if not self._fsm.can(action):
            return False
        self._fsm.apply(action)
        return True

    def _registered(self, repository: IRepository) -> None:
        """Hook after a repository is attached and REGISTER is applied."""

    # endregion Protected

    # region Abstract
    @abstractmethod
    def clean(self): ...

    @abstractmethod
    def create(self, caller: IProcessor, **kwargs) -> Item: ...

    @abstractmethod
    def delete(self, identifier: str, **kwargs) -> None: ...

    @abstractmethod
    def flush(self, caller: IWattleflow, **kwargs) -> bool:
        """Broadcast the canvas to every repository and empty it.

        True only when the canvas held at least one document and every
        repository confirmed every document; False otherwise (including an
        empty canvas). The processor reads this outcome.
        """

    @abstractmethod
    def read(self, identifier: str, **kwargs) -> Item: ...

    @abstractmethod
    def write(self, pipeline: IPipeline, facade: Any, **kwargs) -> Any: ...

    # endregion Abstract


# --------------------------------------------------------------------------- #
# endregion Blackboards                                                        #
# --------------------------------------------------------------------------- #


__all__ = ["BlackboardAction", "BlackboardState", "GenericBlackboard", "TRANSITIONS"]
