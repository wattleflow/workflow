# Module name: driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Defines an abstract, extensible driver base class for the Wattleflow framework.
Provides a unified interface for loading, reading, and writing data sources,
with optional lazy initialisation, integrated audit logging, and dynamic
configuration via the PresetDecorator. Serves as a foundation for concrete
driver implementations handling data persistence and transport.
"""


import logging
from abc import abstractmethod
from typing import Any, Optional
from wattleflow.core import IDriver, ITarget
from wattleflow.concrete import AuditLogger
from wattleflow.decorators.preset import PresetDecorator


class GenericDriverClass(IDriver, AuditLogger):
    __slots__ = [
        "_initialised",
        "_lazy_load",
        "_loaded",
        "_preset",
    ]

    def __init__(
        self,
        level: int,
        handler: Optional[logging.Handler],
        lazy_load: bool = False,
        **kwargs,
    ):
        IDriver.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._loaded = False
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

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __hash__(self) -> int:
        return hash(
            (
                id(self),
                self.name,
                self._preset,
            )
        )
