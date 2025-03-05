# Module Name: core/helpers/document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains document handling class.

import os
import stat
from abc import ABC
from uuid import uuid4
from rdflib import Graph
from datetime import datetime
from typing import Generic, TypeVar
from wattleflow.core import IAdaptee, IAdapter, ITarget

T = TypeVar("T")
U = TypeVar("U", bound=IAdaptee)


class IDocument(IAdaptee, Generic[T], ABC):
    @property
    def identifier(self) -> str:
        pass

    def update_content(self, data: T):
        pass

    def specific_request(self) -> T:
        pass


# GenericDocument
class Document(IDocument[T], ABC):
    def __init__(self):
        self._identifier: str = str(uuid4())
        # self._children: Dict[str, U] = {}
        self._created: datetime = datetime.now()
        self._lastchange: datetime = self._created
        self._data: T = None

    @property
    def identifier(self) -> str:
        return self._identifier

    def specific_request(self) -> T:
        return self._data

    def update_content(self, data: T):  # -> T:
        if not isinstance(data, type(self._data)) and self._data is not None:
            raise TypeError(f"Expected type {type(self._data)}, found {type(data)}")
        self._data = data  # .copy(deep=False)
        self._lastchange = datetime.now()

    # @property
    # def children(self) -> Dict[str, U]:
    #     return self._children

    # @property
    # def count(self) -> int:
    #     return len(self._children)

    # def add(self, child_id: str, child: U) -> None:
    #     self._children[child_id] = child

    # def request(self, identifier: str) -> U:
    #     return self._children.get(identifier, None)


# Child Document
class Child(Document[U], ABC):
    pass


# Document that works with item
class ItemDocument(Document[str]):
    def __init__(self, item: str):
        super().__init__()
        self._item = item
        self._data = ""

    @property
    def item(self) -> str:
        return self._item


# Dict document (dict)
class DictDocument(Document[dict]):
    def __init__(self, **kwargs):
        super().__init__()
        # self._data = {}
        data = kwargs if kwargs else {}
        self.update_content(data)

    @property
    def size(self):
        return self._data


# Document based on file, with automatic retrieval of metadata
class FileDocument(Document[str]):
    def __init__(self, filename: str):
        super().__init__()
        self._metadata = {}
        self._filename = filename
        self.__populate__()

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def metadata(self) -> dict:
        return self._metadata

    def update_filename(self, filename):
        self._filename = filename

    def __populate__(self) -> None:
        if not os.path.exists(self.filename):
            raise FileNotFoundError(f"Invalid file name: {self.filename}.")
        try:
            stats = os.stat(self.filename)
            self._metadata = {
                "features": {},
                "size": stats.st_size,
                "mtime": datetime.fromtimestamp(stats.st_mtime),
                "atime": datetime.fromtimestamp(stats.st_atime),
                "ctime": datetime.fromtimestamp(stats.st_ctime),
                "file_permissions": stat.filemode(stats.st_mode),
                "uid": stats.st_uid,
                "gid": stats.st_gid,
            }
        except Exception as e:
            raise TypeError(e)


# Document based on RDF graph
class GraphDocument(Document[Graph]):
    def __init__(self):
        super().__init__(content=Graph())


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
        return self._adapter.request()

    def __getattr__(self, attr):
        return getattr(self._adapter._adaptee, attr, None)
