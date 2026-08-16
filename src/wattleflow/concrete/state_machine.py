# Module name: concrete/state_machine.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC
from enum import Enum
from typing import Generic, TypeVar
from collections.abc import Callable, Mapping
from wattleflow.core import IStateMachine

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

State = TypeVar("State", bound=Enum)
Action = TypeVar("Action", bound=Enum)

# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region StateMachine                                                         #
# --------------------------------------------------------------------------- #


class StateMachine(IStateMachine, Generic[State, Action], ABC):
    __slots__ = ("_name", "_state", "_transitions")

    def __init__(
        self,
        transitions: Mapping[tuple[State, Action], State],
        initial: State,
        name: str | None = None,
    ) -> None:
        IStateMachine.__init__(self)
        self._name: str | None = name
        self._transitions = transitions
        self._state = initial

    @property
    def name(self) -> str:
        return self._name or self.__class__.__name__

    @property
    def state(self) -> State:
        return self._state

    def can(self, action: Action) -> bool:
        return (self._state, action) in self._transitions

    def apply(self, action: Action) -> None:
        key = (self._state, action)
        if key not in self._transitions:
            raise ValueError(f"{action} not allowed in state {self._state}")
        self._state = self._transitions[key]

    def __repr__(self) -> str:
        state = self._state.name
        return f"{self.name}:[{state}]"


# --------------------------------------------------------------------------- #
# endregion StateMachine                                                      #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region GuardedStateMachine                                                  #
# --------------------------------------------------------------------------- #


class GuardedStateMachine(IStateMachine, ABC):
    """One-shot guard wrapper for a StateMachine (GoF Decorator pattern).

    Runs ``guard(inner)`` exactly once, before the first ``apply()`` call.
    If the guard raises, the underlying transition does not happen. After a
    successful guard the wrapper transparently delegates to the inner FSM.
    """

    __slots__ = ("_guard", "_inner", "_name", "_consumed")

    def __init__(
        self,
        inner: StateMachine,
        guard: Callable[[StateMachine], None],
        name: str | None = None,
    ) -> None:
        IStateMachine.__init__(self)
        # Preserve the inner FSM's name so logs stay consistent.
        self._name: str | None = name or getattr(inner, "name", None)
        self._inner = inner
        self._guard = guard
        self._consumed = False

    @property
    def name(self) -> str:
        return self._name or self.__class__.__name__

    @property
    def inner(self) -> StateMachine:
        return self._inner

    @property
    def state(self):
        return self._inner.state

    def can(self, action) -> bool:
        return self._inner.can(action)

    def apply(self, action) -> None:
        if not self._consumed:
            self._guard(self._inner)
            self._consumed = True
        self._inner.apply(action)

    def __repr__(self) -> str:
        return f"Guarded({self._inner!r})"


# --------------------------------------------------------------------------- #
# endregion GuardedStateMachine                                               #
# --------------------------------------------------------------------------- #


__all__ = ["GuardedStateMachine", "StateMachine"]
