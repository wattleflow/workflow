# Module name: concrete/memento.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["GenericMemento"]

import copy
from types import MappingProxyType
from typing import Any
from collections.abc import Mapping
from wattleflow.core import IMemento, IObservable
from wattleflow.concrete.base import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class MementoClass(IMemento):
    def __init__(self, state):
        self._state = copy.deepcopy(state)

    def get_state(self):
        return self._state


class ObservableClass(IObservable):
    def __init__(self):
        self._listeners = []

    def notify(self, **kwargs):
        for listener in self._listeners:
            listener.update(**kwargs)

    def attach(self, listener):
        self._listeners.append(listener)

    def detach(self, listener):
        self._listeners = [known for known in self._listeners if known is not listener]


class GenericMemento(Wattleflow, IMemento):
    """Immutable snapshot container."""

    __slots__ = ("_data",)

    def __init__(self, **payload: Any) -> None:
        super().__init__(**payload)
        self._data: Mapping[str, Any] = MappingProxyType(dict(payload))

    def __getattr__(self, key: str) -> Any:
        data: Mapping[str, Any] = object.__getattribute__(self, "_data")
        if key not in data:
            raise AttributeError(key)
        return data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        return f"{name}(keys=[{', '.join(self._data)}])"

    def get_state(self) -> Any:
        return self._data.get("state")

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
