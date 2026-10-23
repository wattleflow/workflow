# Module name: concrete/document.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Document, Adapter and Facade — content, metadata and identity of a data object."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["Document", "DocumentAdapter", "DocumentFacade"]

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from collections.abc import Mapping
from types import MappingProxyType
from uuid import uuid4
from wattleflow.core import IAdaptee, IAdapter, ITarget
from wattleflow.core.transactional import Content
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
from wattleflow.helpers.moment import MomentAwareHelper

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

Adaptee = TypeVar("Adaptee", bound=IAdaptee)
_AUDIT_KEYS: frozenset = frozenset({"last_change_key", "last_change_time"})


# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Document Classes                                                     #
# --------------------------------------------------------------------------- #


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

        self.debug(msg=Event.Constructor, step=Event.Started, kwargs=kwargs)

        self._identifier: str = str(uuid4())
        self._content: Content | None = None
        self._metadata: dict[str, object] = {}
        self._expected_type: type[object] | None = None

        self.update_metadata(key="created_at", value=MomentAwareHelper.now())
        self.update_content(content=content)

        self.debug(msg=Event.Constructor, step=Event.Completed)

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

    def clear(self) -> None:
        self.debug(msg=Event.Clear, step=Event.Starting)
        self._content = None
        self._metadata.clear()
        self.debug(msg=Event.Clear, step=Event.Completed)

    def specific_request(self) -> "Document":
        return self

    def update_content(self, content: type) -> None:
        self.debug(
            msg=Event.Updating,
            fnc="update_content",
            content=type(content),
        )

        if content is None:
            raise ValueError(f"{self.name}.update_content: content must not be None")

        if self._expected_type is None:
            self._expected_type = type(content)
        elif not isinstance(content, self._expected_type):
            raise TypeError(
                f"{self.name}.update_content: expected {self._expected_type.__name__}, "
                f"got {type(content).__name__}"
            )

        self._content = content
        self._metadata["last_change_key"] = "content"
        self._metadata["last_change_time"] = MomentAwareHelper.now()

    def update_metadata(self, key: str, value: object) -> None:
        if not key or not key.strip():
            raise ValueError(f"{self.name}.update_metadata: key must be non-empty")

        if key in _AUDIT_KEYS:
            raise ValueError(
                f"{self.name}.update_metadata: '{key}' is a reserved audit key "
                "and cannot be set directly."
            )

        self._metadata[key] = value
        self._metadata["last_change_key"] = key
        self._metadata["last_change_time"] = MomentAwareHelper.now()


    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Document)
            and self.identifier == other.identifier  # noqa: W503
            and type(self) is type(other)  # noqa: W503
        )

    def __hash__(self) -> int:
        return hash((type(self), self.identifier))

    def __repr__(self) -> str:
        return f"{self.name}:{self.identifier}"

    def __str__(self) -> str:
        return f"{self.identifier}"


class DocumentAdapter(Wattleflow, IAdapter, Generic[Adaptee]):
    __slots__ = ("_adaptee",)

    def __init__(self, adaptee: Adaptee, **kwargs):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        super().__init__(**kwargs)
        self._adaptee = adaptee

    @property
    def adaptee(self) -> Adaptee:
        return self._adaptee

    def request(self):
        return self._adaptee.specific_request()


class DocumentFacade(Wattleflow, ITarget, Generic[Adaptee], ABC):
    __slots__ = ("_adapter",)

    def __init__(self, adaptee: IAdaptee, **kwargs):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        super().__init__(**kwargs)
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
        try:
            return getattr(adaptee, attr)
        except AttributeError :
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}'"
            ) from None

    def __repr__(self) -> str:
        return f"{self.name}:{getattr(self, 'identifier', '')}"


# --------------------------------------------------------------------------- #
# region Document Classes                                                     #
# --------------------------------------------------------------------------- #
