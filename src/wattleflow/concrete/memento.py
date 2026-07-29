# Module name: concrete/memento.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from types import MappingProxyType
from typing import Any, Dict, Mapping
from wattleflow.core import IMemento
from wattleflow.concrete.wattleflow import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class GenericMemento(Wattleflow, IMemento):
    """Immutable snapshot container.

    Accepts arbitrary keyword payload and exposes it via attribute-style
    access, ``get_state()`` (canonical "state" key), or ``to_dict()``.
    Performs a shallow copy of the payload mapping; values are stored
    by reference. Owners are responsible for snapshot integrity if the
    referenced values are mutable.

    TODO: persistence layer — pluggable read/write strategies (analogous to
    ``PresetDecorator``) for serialising mementos to disk / database.
    """

    __slots__ = ("_data",)

    def __init__(self, **payload: Any) -> None:
        IMemento.__init__(self)
        self._data: Mapping[str, Any] = MappingProxyType(dict(payload))

    def __getattr__(self, key: str) -> Any:
        try:
            return object.__getattribute__(self, "_data")[key]
        except KeyError:
            raise AttributeError(key) from None

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        fields = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"{name}({fields})"

    def get_state(self) -> Any:
        return self._data.get("state")

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
