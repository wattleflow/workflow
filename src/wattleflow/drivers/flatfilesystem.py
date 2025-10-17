# Module Name: drivers/flatfilesystem.py
# Description: This modul contains driver classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


import logging
from abc import abstractmethod
from typing import Any, Optional
from wattleflow.core import IMessageQueue, IRepository, ITarget
from wattleflow.concrete import AuditLogger
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers.attribute import Attribute

# def prepare(self) -> None:
#     pass

# def commit(self) -> None:
#     pass

# def rollback(self) -> None:
#     pass

# def register_new(self, entity: T, *args, **kwargs) -> None:
#     pass

# def register_dirty(self, entity: T, *args, **kwargs) -> None:
#     pass

# def register_deleted(self, entity: T, *args, **kwargs) -> None:
#     pass


class IDriver(IMessageQueue, AuditLogger):
    __slots__ = [
        "_initialized",
        "_lazy_load",
        "_preset",
        "_repository",
    ]

    def __init__(
        self,
        repository: IRepository,
        level: int,
        handle: Optional[logging.Handler],
        lazy_load: bool = False,
        **kwargs,
    ):
        IMessageQueue.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handle)
        Attribute.evaluate(caller=self, target=repository, expected_type=IRepository)

        self._repository = repository
        self._preset = PresetDecorator(parent=self, **kwargs)

        if not lazy_load:
            self.load()

    @abstractmethod
    def load(self) -> None:
        pass

    @abstractmethod
    def read(self, identifer: str, **kwargs) -> Any:
        pass

    @abstractmethod
    def write(self, document: ITarget, **kwargs) -> bool:
        pass

    def send(self, identifer: str, **kwargs) -> Any:
        return self.write(identifer=identifer, **kwargs)

    def recieve(self, identifer: str, **kwargs) -> Any:
        return self.read(identifer=identifer, **kwargs)


class FlatFileSystem(IDriver):
    def load(self) -> None:
        pass

    def read(self, identifer: str, **kwargs) -> Any:
        pass

    def write(self, document: ITarget, **kwargs) -> Any:
        pass
