# Module name: connections/memory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""An in-process key-value store behind the connection contract (SyRS-CNC-memory)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["MemoryConnection", "MemoryStore"]

from collections.abc import Generator
from contextlib import contextmanager
from copy import deepcopy
from typing import Any

from wattleflow.core import IAdaptee
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.connection import (
    ConnectionAction,
    ConnectionState,
    GenericConnection,
)
from wattleflow.concrete.exception import ConnectionException
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Store                                                                #
# --------------------------------------------------------------------------- #


class MemoryStore(Wattleflow, IAdaptee):
    """The session: values go in and come out as copies, so a caller cannot
    change stored state without `set`."""

    __slots__ = ("_data",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict[str, Any] = {}

    def __len__(self) -> int:
        return len(self._data)

    def specific_request(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._data:
            return default
        return deepcopy(self._data[key])

    def set(self, key: str, value: Any) -> None:
        self._data[key] = deepcopy(value)

    def delete(self, key: str) -> bool:
        return self._data.pop(key, _MISSING) is not _MISSING

    def keys(self, prefix: str = "") -> list[str]:
        return sorted(k for k in self._data if k.startswith(prefix))

    def increment(self, key: str, amount: int = 1) -> int:
        current = self._data.get(key, 0)
        if type(current) is not int:
            raise ConnectionException(
                caller=self,
                error=f"increment: key {key!r} holds a {type(current).__name__}, not an int",
            )
        self._data[key] = current + amount
        return self._data[key]

    def clear(self) -> None:
        self._data.clear()


_MISSING = object()

# --------------------------------------------------------------------------- #
# endregion Store                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Connection                                                           #
# --------------------------------------------------------------------------- #


class MemoryConnection(GenericConnection[MemoryStore]):
    """Holds one `MemoryStore` for the life of the connection; every session
    yields the same store."""

    ALLOWED = ["connection_name", "lazy_loading"]

    def create_connection(self) -> None:
        self.debug(msg=Event.Create, step=Event.Started, state=self.state.value)
        if self.state is ConnectionState.FAILED:
            raise ConnectionException(
                caller=self,
                error=f"Cannot create connection in state '{self.state.value}'",
            )
        if self._connection is None:
            self._connection = MemoryStore()
        self.debug(msg=Event.Created, state=self.state.value)

    @contextmanager
    def connect(self) -> Generator[MemoryStore, None, None]:
        self._ensure_created()
        if self._connection is None:
            raise ConnectionException(caller=self, error=f"{self.name}.connect: store is None")

        if self._fsm.can(ConnectionAction.CONNECT):
            self._fsm.apply(ConnectionAction.CONNECT)
            self._fsm.apply(ConnectionAction.CONNECT_OK)
        self.debug(msg=Event.Connected, state=self.state.value)
        try:
            yield self._connection
        finally:
            if self._fsm.can(ConnectionAction.DISCONNECT):
                self._fsm.apply(ConnectionAction.DISCONNECT)

    def disconnect(self) -> None:
        self.debug(msg=Event.Disconnect, state=self.state.value)
        if self._connection is not None:
            self._connection.clear()
            self._connection = None
        self.debug(msg=Event.Disconnected, state=self.state.value)


# --------------------------------------------------------------------------- #
# endregion Connection                                                        #
# --------------------------------------------------------------------------- #
