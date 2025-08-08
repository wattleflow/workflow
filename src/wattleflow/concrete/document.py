# Module Name: helpers/document.py
# Description: This modul contains concrete document handling class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import ABC
from datetime import datetime
from logging import Handler, NOTSET
from typing import Dict, Generic, Optional, TypeVar
from uuid import uuid4
from wattleflow.core import IDocument, IAdaptee, IAdapter, ITarget, T
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event

A = TypeVar("A", bound=IAdaptee)


# GenericDocument
class Document(IDocument[T], AuditLogger, ABC):
    def __init__(self, level: int = NOTSET, handler: Optional[Handler] = None):
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(msg=Event.Constructor.value, level=level, handler=handler)

        self._identifier: str = str(uuid4())
        self._children: Dict[str, IAdaptee] = {}
        self._created: datetime = datetime.now()
        self._lastchange: datetime = self._created
        self._content: Optional[T] = None

    @property
    def children(self) -> Dict[str, IAdaptee]:
        return self._children

    @property
    def count(self) -> int:
        return len(self._children)

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def size(self) -> int:
        if self._content is None:
            return 0
        return len(self._content)

    def add(self, child_id: str, child: A) -> None:
        self.debug(msg=Event.Adding.value, child_id=child_id, child=child)
        self._children[child_id] = child

    def get(self, identifier: str) -> A:
        self.debug(msg=Event.Retrieving.value, identifier=identifier)
        child = self._children.get(identifier, None)
        if child is None:
            self.warning(
                msg=Event.Getting.value,
                id=identifier,
                error="child not found",
                child=child,
            )

    def request(self, identifier: str) -> Optional[A]:
        self.debug(msg=Event.Retrieving.value, identifier=identifier)
        return self.self._content

    def specific_request(self) -> T:
        return self

    def update_content(self, content: T) -> None:
        self.debug(msg=Event.Updating.value, data=content)

        if (
            self._content is not None
            and content is not None  # noqa: W503
            and not isinstance(content, type(self._content))  # noqa: W503
        ):
            raise TypeError(f"Expected type {type(self._content)}, found {type(content)}")

        self._content = content
        self._lastchange = datetime.now()


# Child Document
class Child(Document[A], ABC):
    pass


# Adapter with specific_request adaptee object call
class DocumentAdapter(Generic[A], IAdapter):
    def __init__(self, adaptee: A):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        super().__init__(adaptee)

    def request(self):
        return self._adaptee.specific_request()


# Facade implements ITarget and delegates access methods adaptee object
class DocumentFacade(Generic[A], ITarget):
    def __init__(self, adaptee: A):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        self._adapter = DocumentAdapter(adaptee)

    @property
    def identifier(self) -> str:
        return self._adapter._adaptee.identifier

    def request(self):
        result = self._adapter.request()
        if result is None:
            raise ValueError(f"Request returned None in {self.__class__.__name__}")
        return result

    def __getattr__(self, attr):
        if hasattr(self._adapter._adaptee, attr):
            return getattr(self._adapter._adaptee, attr)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{attr}'"
        )
