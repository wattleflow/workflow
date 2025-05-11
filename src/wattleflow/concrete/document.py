# Module Name: helpers/document.py
# Description: This modul contains concrete document handling class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

"""
This library manages document abstraction and handling.

1. Design Patterns
- Adapter Pattern (DocumentAdapter)
    - Converts IAdaptee into a compatible interface (IAdapter).
    - Implements request() by calling specific_request() on IAdaptee.

- Facade Pattern (DocumentFacade)
    - Wraps DocumentAdapter to provide a simpler API (ITarget).

- Composite Pattern (Commented Out)
    - Document class previously stored child documents but was commented out.

2. Document Types Implemented
- Document[T] (Base Class)
    - Generic document class storing _data and _identifier.
    - Supports update_content() for modifying content.
"""

from abc import ABC
from uuid import uuid4
from datetime import datetime
from typing import Dict, Generic, TypeVar
from wattleflow.core import IDocument, IAdaptee, IAdapter, ITarget

T = TypeVar("T")
U = TypeVar("U", bound=IAdaptee)


# GenericDocument
class Document(IDocument[T], ABC):
    def __init__(self):
        self._identifier: str = str(uuid4())
        self._children: Dict[str, U] = {}
        self._created: datetime = datetime.now()
        self._lastchange: datetime = self._created
        self._data: T = None

    @property
    def identifier(self) -> str:
        return self._identifier

    def specific_request(self) -> T:
        return self

    def update_content(self, data: T):
        if (
            self._data is not None
            and data is not None
            and not isinstance(data, type(self._data))
        ):
            raise TypeError(f"Expected type {type(self._data)}, found {type(data)}")
        self._data = data
        self._lastchange = datetime.now()

    @property
    def children(self) -> Dict[str, U]:
        return self._children

    @property
    def count(self) -> int:
        return len(self._children)

    def add(self, child_id: str, child: U) -> None:
        self._children[child_id] = child

    def request(self, identifier: str) -> U:
        return self._children.get(identifier, None)


# Child Document
class Child(Document[U], ABC):
    pass


# Adapter with specific_request adaptee object call
class DocumentAdapter(Generic[U], IAdapter):
    def __init__(self, adaptee: U):
        if not isinstance(adaptee, IAdaptee):
            raise TypeError("IAdaptee must be used.")
        super().__init__(adaptee)

    def request(self):
        return self._adaptee.specific_request()


# Facade implements ITarget and delegates access methods adaptee object
class DocumentFacade(Generic[U], ITarget):
    def __init__(self, adaptee: U):
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
