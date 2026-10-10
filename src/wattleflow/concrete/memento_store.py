# Module name: concrete/memento_store.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "FileMementoStore",
    "MementoStore",
    "MementoStoreException",
    "MemoryMementoStore",
]

import json
import os
import re
import tempfile
import threading
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any
from wattleflow.core import IStrategy, IWattleflow
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class MementoStoreException(AuditException):
    pass


class MementoStore(Wattleflow, IStrategy, ABC):
    """Where a memento survives between runs: the persistence strategy of FRQ-MEM.

    A store holds the latest snapshot per key. It never interprets the payload;
    turning a stored value back into a domain type is the originator's job.
    """

    __slots__ = ()

    # A key becomes a file name, so it is a plain name and never a path.
    _KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    @classmethod
    def _check_key(cls, key: object) -> str:
        if not isinstance(key, str) or not cls._KEY.fullmatch(key) or key.endswith("."):
            raise MementoStoreException(cls, f"Invalid memento key {key!r}: a plain name is required")
        return key

    @classmethod
    def _check_memento(cls, memento: object) -> GenericMemento:
        if not isinstance(memento, GenericMemento):
            raise MementoStoreException(
                cls, f"Expected GenericMemento, found {type(memento).__name__}"
            )
        return memento

    @classmethod
    def _plain(cls, value: Any) -> Any:
        # Stores hold plain data, so every backend returns the same values. json writes a `str` Enum by value and never reaches `default`, so the names are set here.
        if isinstance(value, Enum):
            return value.name
        if isinstance(value, dict):
            return {key: cls._plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._plain(item) for item in value]
        return value

    @abstractmethod
    def write(self, key: str, memento: GenericMemento) -> None: ...

    @abstractmethod
    def read(self, key: str) -> GenericMemento | None: ...

    @abstractmethod
    def clear(self, key: str) -> None: ...

    def execute(self, caller: IWattleflow, **kwargs) -> Any:
        action = kwargs.get("action")
        if action == "write":
            return self.write(kwargs.get("key"), kwargs.get("memento"))
        if action == "read":
            return self.read(kwargs.get("key"))
        if action == "clear":
            return self.clear(kwargs.get("key"))
        raise MementoStoreException(self, f"Unknown memento action {action!r}")


class MemoryMementoStore(MementoStore):
    """Snapshots held in the process: they outlive a failed run, not the process."""

    __slots__ = ("_snapshots", "_guard")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._guard = threading.Lock()

    def write(self, key: str, memento: GenericMemento) -> None:
        key = self._check_key(key)
        payload = self._plain(self._check_memento(memento).to_dict())
        with self._guard:
            self._snapshots[key] = payload

    def read(self, key: str) -> GenericMemento | None:
        key = self._check_key(key)
        with self._guard:
            payload = self._snapshots.get(key)
        return None if payload is None else GenericMemento(**payload)

    def clear(self, key: str) -> None:
        key = self._check_key(key)
        with self._guard:
            self._snapshots.pop(key, None)


class FileMementoStore(MementoStore):
    """One JSON file per key under `path`, replaced atomically.

    The same path after a restart is what lets a run resume. A value is stored as
    JSON: an Enum is written as its member name, anything else JSON cannot hold
    is refused and the previous snapshot stays as it was.
    """

    __slots__ = ("_path",)

    def __init__(self, path: str | os.PathLike | None = None, **kwargs) -> None:
        if path is None or not str(path).strip():
            raise MementoStoreException(type(self), "FileMementoStore needs a `path`")
        super().__init__(**kwargs)
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _file(self, key: str) -> Path:
        return self._path / f"{self._check_key(key)}.json"

    def write(self, key: str, memento: GenericMemento) -> None:
        target = self._file(key)
        payload = self._check_memento(memento).to_dict()
        try:
            text = json.dumps(self._plain(payload))
        except (TypeError, ValueError) as error:
            raise MementoStoreException(self, f"Cannot store memento {key!r}: {error}") from error
        temporary: str | None = None
        try:
            self._path.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=self._path, prefix=".", suffix=".tmp")
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            temporary = None
        except OSError as error:
            raise MementoStoreException(self, f"Cannot write memento {key!r}: {error}") from error
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        self.debug(msg=Event.Write, step=Event.Completed, key=key, file=str(target))

    def read(self, key: str) -> GenericMemento | None:
        source = self._file(key)
        try:
            text = source.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as error:
            raise MementoStoreException(self, f"Cannot read memento {key!r}: {error}") from error
        try:
            payload = json.loads(text)
        except ValueError as error:
            raise MementoStoreException(self, f"Memento {key!r} is corrupt: {error}") from error
        if not isinstance(payload, dict):
            raise MementoStoreException(
                self, f"Memento {key!r} is corrupt: expected an object, found {type(payload).__name__}"
            )
        self.debug(msg=Event.Read, step=Event.Completed, key=key, file=str(source))
        return GenericMemento(**payload)

    def clear(self, key: str) -> None:
        target = self._file(key)
        try:
            target.unlink(missing_ok=True)
        except OSError as error:
            raise MementoStoreException(self, f"Cannot clear memento {key!r}: {error}") from error


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
