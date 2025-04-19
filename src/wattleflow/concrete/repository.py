# Module Name: concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains repository classes.

"""
1. Inheritance & Dependencies
- Inherits from:
    - IRepository: Defines the repository interface.
    - Attribute: Provides dynamic attribute handling (evaluate, push, allowed).
    - ABC: Enforces abstraction.
- Depends on:
    - IStrategy: Defines how reading (_strategy_read) and writing (_strategy_write) work.
    - IPipeline: Passed to write() for processing.
    - ITarget: Used for data validation in read().

2. Core Responsibilities
- Reading Data (read)
    - Uses _strategy_read.read() to fetch a document.
    - Ensures the returned document is of type ITarget.
    - Uses audit(event=Event.Reading, id=identifier) for logging.

- Writing Data (write)
    - Uses _strategy_write.write() to store the data.
    - Passes pipeline, self (repository), and item to _strategy_write.write().
    - Increments _counter on each write operation.

- Dynamic Configuration (configure)
    - Uses allowed(self._allowed, **kwargs) to filter attributes.
    - Restricts accepted types to bool, dict, list, str.
    - Raises an AttributeError for invalid types.

- Type Validation (evaluate)
    - Ensures strategy_read and strategy_write are valid instances of IStrategy.
    - Ensures the document returned by read() is an ITarget.
"""
from abc import ABC
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IBlackboard, IStrategy, ITarget, IPipeline, IRepository, T
from wattleflow.constants.enums import Event
from wattleflow.concrete import Attribute, AuditLogger, _NC


class GenericRepository(IRepository, Attribute, AuditLogger, ABC):
    def __init__(
        self,
        strategy_read: IStrategy,
        strategy_write: IStrategy,
        allowed: list = [],
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        IRepository.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.evaluate(strategy_read, IStrategy)
        self.evaluate(strategy_write, IStrategy)

        self._counter: int = 0
        self._strategy_read = strategy_read
        self._strategy_write = strategy_write
        self._allowed = allowed

        self.debug(
            msg=Event.Constructor.value,
            strategy_read=self._strategy_read,
            strategy_write=self._strategy_write,
            allowed=allowed,
        )

        self.configure(**kwargs)

        self.debug(msg=Event.Constructor.value, status="finalised")

    @property
    def count(self) -> int:
        return self._counter

    def configure(self, **kwargs):
        self.allowed(self._allowed, **kwargs)

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
                self.debug(msg=Event.Configuring.value, name=name, value=value)
            else:
                error = f"{_NC(value)}) is restricted type. [bool, dict, list, str]"
                self.error(msg=error, name=name)
                raise AttributeError(error)

    def read(self, identifier: str, item: ITarget, **kwargs) -> T:
        self.debug("read", id=identifier, item=item.identifier, kwargs=kwargs)
        self.evaluate(item, ITarget)

        document = self._strategy_read.read(caller=self, item=item, identifier=identifier, **kwargs)
        self.evaluate(document, ITarget)

        self.info(
            msg=Event.Retrieved.value,
            id=item.identifier,
            success=True,
            document=document,
        )
        return document

    def write(self, pipeline: IPipeline, item: T, **kwargs) -> bool:
        try:
            self._counter += 1
            self.info(
                msg=Event.Writting.value,
                counter=self._counter,
                pipeline=pipeline.name,
                item=item,
            )
            return self._strategy_write.write(pipeline, self, item=item, **kwargs)
        except Exception as e:
            error = f"Write operation failed in {self.__class__.__name__}: {e}"
            self.exception(msg=error, counter=self._counter)
            raise RuntimeError(error)
