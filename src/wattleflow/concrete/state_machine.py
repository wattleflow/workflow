# Module name: concrete/state_machine.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from enum import Enum
from typing import Generic, Mapping, Optional, Tuple, TypeVar
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


class StateMachine(IStateMachine, Generic[State, Action]):
    __slots__ = ("_state", "_transitions")

    def __init__(
        self,
        transitions: Mapping[Tuple[State, Action], State],
        initial: State,
        name: Optional[str] = None,
    ) -> None:
        IStateMachine.__init__(self)
        if name is not None:
            self.name = name
        self._transitions = transitions
        self._state = initial

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
        name = self.name or self.__class__.__name__
        state = self._state.name
        return f"{name}:[{state}]"


# --------------------------------------------------------------------------- #
# endregion StateMachine                                                      #
# --------------------------------------------------------------------------- #
