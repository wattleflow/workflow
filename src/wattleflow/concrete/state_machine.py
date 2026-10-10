# Module name: concrete/state_machine.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["GuardedStateMachine", "StateMachine"]

import threading
from abc import ABC
from enum import Enum
from types import MappingProxyType
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
# region StateMachine Classes                                                 #
# --------------------------------------------------------------------------- #


class StateMachine(IStateMachine, Generic[State, Action], ABC):
    __slots__ = ("_name", "_transitions", "_state", "_lock")

    def __init__(
        self,
        transitions: Mapping[tuple[State, Action], State],
        initial: State,
        name: str | None = None,
    ) -> None:
        IStateMachine.__init__(self)
        self._name: str | None = name
        # A read-only copy: the owner keeps its dictionary,
        # but the FSM cannot change it. The mapping is from (state, action) to state.
        table = MappingProxyType(dict(transitions))
        known = {source for source, _ in table} | set(table.values())
        if initial not in known:
            raise ValueError(f"Start state {initial!r} does not appear in the transition table")
        self._transitions = table
        self._state = initial
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name or self.__class__.__name__

    @property
    def state(self) -> State:
        return self._state

    def can(self, action: Action) -> bool:
        return (self._state, action) in self._transitions

    def apply(self, action: Action) -> None:
        # Check and write are one step: two threads cannot both take the same transition.
        with self._lock:
            key = (self._state, action)
            if key not in self._transitions:
                raise ValueError(f"{action} not allowed in state {self._state}")
            self._state = self._transitions[key]

    def try_apply(self, action: Action) -> bool:
        """`can` then `apply` as one atomic step: True when the transition was taken."""
        with self._lock:
            key = (self._state, action)
            if key not in self._transitions:
                return False
            self._state = self._transitions[key]
            return True

    def __repr__(self) -> str:
        state = self._state.name
        return f"{self.name}:[{state}]"


class GuardedStateMachine(IStateMachine, Generic[State, Action], ABC):
    """One-shot guard wrapper for a StateMachine (GoF Decorator pattern)."""

    __slots__ = ("_guard", "_inner", "_name", "_consumed", "_guard_lock")

    def __init__(
        self,
        inner: StateMachine[State, Action],
        guard: Callable[[StateMachine[State, Action]], None],
        name: str | None = None,
    ) -> None:
        IStateMachine.__init__(self)
        # Preserve the inner FSM's name so logs stay consistent.
        self._name: str | None = name or getattr(inner, "name", None)
        self._inner = inner
        self._guard = guard
        self._consumed = False
        self._guard_lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name or self.__class__.__name__

    @property
    def inner(self) -> StateMachine[State, Action]:
        return self._inner

    @property
    def state(self) -> State:
        return self._inner.state

    def can(self, action: Action) -> bool:
        return self._inner.can(action)

    def _check(self) -> None:
        # The guard runs once, before the first transition, also when threads arrive together:
        # the others wait for it.
        with self._guard_lock:
            if not self._consumed:
                self._guard(self._inner)
                self._consumed = True

    def apply(self, action: Action) -> None:
        self._check()
        self._inner.apply(action)

    def try_apply(self, action: Action) -> bool:
        self._check()
        return self._inner.try_apply(action)

    def __repr__(self) -> str:
        return f"Guarded({self._inner!r})"


# --------------------------------------------------------------------------- #
# endregion StateMachine Classes                                              #
# --------------------------------------------------------------------------- #
