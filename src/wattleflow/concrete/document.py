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

A = TypeVar("A", bound=IAdaptee)

# GenericDocument
class Document(IDocument[T], AuditLogger, ABC):
    def __init__(self, level: int = NOTSET, handler: Optional[Handler] = None):
        AuditLogger.__init__(self, level=level, handler=handler)
        self._identifier: str = str(uuid4())
        self._children: Dict[str, IAdaptee] = {}
        self._created: datetime = datetime.now()
        self._lastchange: datetime = self._created
        self._data: Optional[T] = None

    @property
    def identifier(self) -> str:
        return self._identifier

    def specific_request(self) -> T:
        return self

    def update_content(self, data: T):
        if (
            self._data is not None
            and data is not None                        # noqa: W503
            and not isinstance(data, type(self._data))  # noqa: W503
        ):
            raise TypeError(f"Expected type {type(self._data)}, found {type(data)}")
        self._data = data
        self._lastchange = datetime.now()

    @property
    def children(self) -> Dict[str, IAdaptee]:
        return self._children

    @property
    def count(self) -> int:
        return len(self._children)

    def add(self, child_id: str, child: A) -> None:
        self._children[child_id] = child

    def request(self, identifier: str) -> A:
        return self._children.get(identifier, None)


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
