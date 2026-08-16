# Module name: concrete/document.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Document, Adapter and Facade — content, metadata and identity of a data object."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar
from collections.abc import Mapping
from types import MappingProxyType
from uuid import uuid4
from wattleflow.core import IAdaptee, IAdapter, ITarget
from wattleflow.core.transactional import Content
from wattleflow.concrete.base import Wattleflow
from wattleflow.constants import Event
from wattleflow.helpers.dtime import Now

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

Adaptee = TypeVar("Adaptee", bound=IAdaptee)

# Keys managed internally by update_metadata — must not be set by callers directly.
_AUDIT_KEYS: frozenset = frozenset({"last_change_key", "last_change_time"})


# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region GenericDocument                                                      #
# --------------------------------------------------------------------------- #


# Wattleflow precedes Generic[Content] so IWattleflow lands before Generic in the
# MRO (same constraint as GenericBlackboard); otherwise a subclass mixing in
# IOriginator cannot linearise.
class Document(Wattleflow, IAdaptee, Generic[Content], ABC):
    __slots__ = (
        "_content",
        "_expected_type",
        "_identifier",
        "_initialised",
        "_metadata",
    )

    def __init__(self, content: Content, **kwargs):
        super().__init__(**kwargs)

        self.debug(msg=Event.Constructor.value, step=Event.Started.name, kwargs=kwargs)

        # internal interface
        self._identifier: str = str(uuid4())
        self._content: Content | None = None
        self._metadata: dict[str, object] = {}
        # lock after first assignment
        self._expected_type: type[object] | None = None

        self.update_metadata(key="created_at", value=Now.utc())
        self.update_content(content=content)

        self.debug(msg=Event.Constructor.value, step=Event.Completed.name)

    @property
    def content(self) -> Content:
        obj = getattr(self, "_content", None)
        if obj is None:
            raise ValueError("Content value is missing or uninitialised.")
        return obj

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def metadata(self) -> Mapping[str, object]:
        return MappingProxyType(self._metadata)

    @property
    @abstractmethod
    def size(self) -> int: ...  # noqa: E704

    def clean(self) -> None:
        self.debug(msg=Event.Clean.name, step=Event.Starting.name)
        self._content = None
        self._metadata.clear()
        self.debug(msg=Event.Clean.name, step=Event.Completed.name)

    def specific_request(self) -> "Document":
        return self

    def update_content(self, content: type) -> None:
        self.debug(
            msg=Event.Updating.value,
            fnc="update_content",
            content=type(content),
        )

        if content is None:
            self._content = None
            self._metadata["last_change_key"] = "content"
            self._metadata["last_change_time"] = self.utc_time_stamp()
            return

        if self._expected_type is None:
            self._expected_type = type(content)
        elif not isinstance(content, self._expected_type):
            raise TypeError(
                f"{self.name}.update_content: expected {self._expected_type.__name__}, "
                f"got {type(content).__name__}"
            )

        self._content = content
        self._metadata["last_change_key"] = "content"
        self._metadata["last_change_time"] = self.utc_time_stamp()

    def update_metadata(self, key: str, value: object) -> None:
        self.debug(
            msg=Event.Update.value,
            step=Event.Started.name,
            key=key,
            value=value,
        )

        if not key or not key.strip():
            raise ValueError(f"{self.name}.update_metadata: key must be non-empty")

        # Reserved audit keys are written internally only; a caller able to set
        # them could falsify the change history.
        if key in _AUDIT_KEYS:
            raise ValueError(
                f"{self.name}.update_metadata: '{key}' is a reserved audit key "
                "and cannot be set directly."
            )

        self._metadata[key] = value
        self._metadata["last_change_key"] = key
        self._metadata["last_change_time"] = self.utc_time_stamp()

        self.debug(
            msg=Event.Update.value,
            step=Event.Completed.name,
        )

    def utc_time_stamp(self) -> datetime:
        return Now.utc()

    def __del__(self):
        try:
            self.clean()
        except Exception:
            pass

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Document)
            and self.identifier == other.identifier  # noqa: W503
            and type(self) is type(other)  # noqa: W503
        )

    def __repr__(self) -> str:
        return f"{self.name}:{self.identifier}"

    def __str__(self) -> str:
        return f"{self.identifier}"


# --------------------------------------------------------------------------- #
# endregion GenericDocument                                                   #
# --------------------------------------------------------------------------- #

# Adapter with specific_request adaptee object call
# --------------------------------------------------------------------------- #
# region Adapter                                                              #
# --------------------------------------------------------------------------- #


class DocumentAdapter(Wattleflow, IAdapter, Generic[Adaptee]):
    __slots__ = ("_adaptee",)

    def __init__(self, adaptee: Adaptee, **kwargs):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        super().__init__(**kwargs)
        self._adaptee = adaptee

    # IAdapter contract: the adapter exposes the adaptee it wraps.
    @property
    def adaptee(self) -> Adaptee:
        return self._adaptee

    def request(self):
        return self._adaptee.specific_request()


# --------------------------------------------------------------------------- #
# endregion Adapter                                                           #
# --------------------------------------------------------------------------- #

# Facade implements ITarget and delegates access methods adaptee object
# --------------------------------------------------------------------------- #
# region Facade                                                               #
# --------------------------------------------------------------------------- #


class DocumentFacade(Wattleflow, ITarget, Generic[Adaptee], ABC):
    __slots__ = ("_adapter",)

    def __init__(self, adaptee: IAdaptee, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        # The adapter is an implementation detail of this facade, so it audits
        # under the same configuration rather than falling back to defaults.
        self._adapter = DocumentAdapter(adaptee, **kwargs)

    def request(self) -> Adaptee:
        result = self._adapter.request()
        if result is None:
            raise ValueError(f"Request returned None in {self.__class__.__name__}")
        return result

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")
        adaptee = self._adapter.request()
        if hasattr(adaptee, attr):
            return getattr(adaptee, attr)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    def __repr__(self) -> str:
        return f"{self.name}:{getattr(self, 'identifier', '')}"


# --------------------------------------------------------------------------- #
# endregion Facade                                                            #
# --------------------------------------------------------------------------- #


__all__ = ["Document", "DocumentAdapter", "DocumentFacade"]
