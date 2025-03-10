# Module Name: core/concrete/repository.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete repository classes.

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
from typing import TypeVar
from wattleflow.core import IStrategy
from wattleflow.core import ITarget
from wattleflow.core import IPipeline, IRepository
from wattleflow.constants.enums import Event
from wattleflow.concrete.attribute import Attribute
from wattleflow.helpers.functions import _NC


T = TypeVar("T")


class GenericRepository(IRepository, Attribute, ABC):
    def __init__(
        self,
        strategy_read: IStrategy,
        strategy_write: IStrategy,
        allowed: list = [],
        *args,
        **kwargs,
    ):
        super().__init__()
        self.evaluate(strategy_read, IStrategy)
        self.evaluate(strategy_write, IStrategy)
        self._counter: int = 0
        self._strategy_read = strategy_read
        self._strategy_write = strategy_write
        self._allowed = allowed
        self.configure(**kwargs)

    @property
    def count(self) -> int:
        return self._counter

    def configure(self, **kwargs):
        self.allowed(self._allowed, **kwargs)

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
            else:
                error = f"{_NC(value)}) is restricted type. [bool, dict, list, str]"
                raise AttributeError(error)

    def read(self, identifier: str) -> T:
        document = self._strategy_read.read(caller=self, id=identifier)
        self.evaluate(document, ITarget)
        self.audit(event=Event.Reading, id=identifier, success=True)
        return document

    def write(self, pipeline: IPipeline, item: T, **kwargs) -> bool:
        try:
            self._counter += 1
            return self._strategy_write.write(pipeline, self, item=item, **kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Write operation failed in {self.__class__.__name__}: {e}"
            )
