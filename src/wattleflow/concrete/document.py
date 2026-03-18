# Module name: document.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: Defines the core document abstraction layer within the Wattleflow framework.
Provides generic Document, Adapter, and Facade classes implementing the
Adapter–Facade pattern to manage content, metadata, and identity of data
objects. Includes type-safe content updates, UTC-based metadata tracking,
and consistent audit logging for document lifecycle operations.
"""


from abc import ABC, abstractmethod
from datetime import datetime, timezone
from logging import Handler, NOTSET
from typing import Dict, Generic, Mapping, Optional, TypeVar, Type
from types import MappingProxyType
from uuid import uuid4
from wattleflow.core import IAdaptee, IAdapter, ITarget, T
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event


A = TypeVar("A", bound=IAdaptee)

# Keys managed internally by update_metadata — must not be set by callers directly.
_AUDIT_KEYS: frozenset = frozenset({"last_change_key", "last_change_time"})


class Document(IAdaptee, Generic[T], AuditLogger, ABC):
    # region FIX-01: Added missing '_expected_type' to __slots__
    # '_expected_type' is assigned in __init__ but was absent from __slots__,
    # causing AttributeError on first assignment in classes that use __slots__.
    __slots__ = (
        "_content",
        "_expected_type",
        "_identifier",
        "_initialised",
        "_metadata",
    )
    # endregion FIX-01

    def __init__(
        self,
        content: T,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        IAdaptee.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            level=level,
            handler=handler,
        )

        # internal interface
        self._identifier: str = str(uuid4())
        self._content: Optional[T] = None
        self._metadata: Dict[str, object] = {}
        # lock after first assignment
        self._expected_type: Optional[Type[object]] = None

        self.update_metadata(key="created_at", value=datetime.now(timezone.utc))
        self.update_content(content=content)

        self.debug(msg=Event.Constructor.value, step=Event.Completed.value)

    @property
    def content(self) -> T:
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

    def specific_request(self) -> "Document":
        return self

    def update_content(self, content: T) -> None:
        self.debug(
            msg=Event.Updating.value,
            fnc="update_content",
            content=type(content),
        )

        if content is None:
            self._content = None  # Can clear the content
            # Record the change directly — avoids calling update_metadata with
            # reserved audit keys, which is now guarded (see FIX-06).
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
        # Record the change directly — same reason as above.
        self._metadata["last_change_key"] = "content"
        self._metadata["last_change_time"] = self.utc_time_stamp()

    def update_metadata(self, key: str, value: object) -> None:
        self.debug(
            msg=Event.Update.value,
            step=Event.Started.value,
            key=key,
            value=value,
        )

        # region FIX-02: Reject empty or whitespace-only keys
        # The original check (`key is None`) never triggers because the type hint
        # is `str`; a caller passing "" would silently create an empty dict key.
        if not key or not key.strip():
            raise ValueError(f"{self.name}.update_metadata: key must be non-empty")
        # endregion FIX-02

        # region FIX-06: Protect reserved audit keys from external modification
        # 'last_change_key' and 'last_change_time' are set internally by this
        # method to maintain a trustworthy audit trail. Allowing callers to
        # write these keys directly would let them silently falsify the history.
        # update_content uses direct dict writes for these keys instead.
        if key in _AUDIT_KEYS:
            raise ValueError(
                f"{self.name}.update_metadata: '{key}' is a reserved audit key "
                "and cannot be set directly."
            )
        # endregion FIX-06

        # region FIX-03: Internal audit tracking uses direct dict writes
        # Previously, the method wrote `_metadata[key] = value` then immediately
        # overwrote `_metadata["last_change_key"] = key`. If `key` was
        # "last_change_key", the caller's value was silently discarded.
        # Reserved keys are now blocked above, so the writes below can never
        # conflict with `_metadata[key] = value`.
        self._metadata[key] = value
        self._metadata["last_change_key"] = key
        self._metadata["last_change_time"] = self.utc_time_stamp()
        # endregion FIX-03

        self.debug(
            msg=Event.Update.value,
            step=Event.Completed.value,
        )

    def utc_time_stamp(self) -> datetime:
        return datetime.now(timezone.utc)

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


# Adapter with specific_request adaptee object call
class DocumentAdapter(IAdapter, Generic[T]):
    def __init__(self, adaptee: T):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        IAdapter.__init__(self, adaptee=adaptee)

    def request(self):
        return self._adaptee.specific_request()


# Facade implements ITarget and delegates access methods adaptee object
class DocumentFacade(ITarget, Generic[A], ABC):
    # region FIX-04: '__slots__' must be a tuple, not a bare string
    # `__slots__ = "_adapter"` iterates over the characters of the string,
    # creating individual slots for '_', 'a', 'd', etc. instead of one slot
    # named "_adapter". The trailing comma makes it a single-element tuple.
    __slots__ = ("_adapter",)
    # endregion FIX-04

    def __init__(self, adaptee: A):
        ITarget.__init__(self)
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        self._adapter = DocumentAdapter(adaptee)

    def request(self):
        result = self._adapter.request()
        if result is None:
            raise ValueError(f"Request returned None in {self.__class__.__name__}")
        return result

    # region FIX-05: Prevent private attribute exposure through __getattr__
    # The original implementation forwarded any attribute lookup — including
    # names starting with '_' — directly to the internal adaptee, bypassing
    # encapsulation and leaking private state to any caller. Private and dunder
    # attributes are now blocked; only public attributes are proxied.
    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{attr}'"
            )
        adaptee = self._adapter.request()
        if hasattr(adaptee, attr):
            return getattr(adaptee, attr)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{attr}'"
        )
    # endregion FIX-05

    def __repr__(self) -> str:
        return f"{self.name}:{getattr(self, 'identifier', '')}"
