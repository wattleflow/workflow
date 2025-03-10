# Module Name: core/concrete/processor.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete base processor class.

"""
The GenericProcessor class is a concrete implementation of the IProcessor
   interface in Wattleflow.
1. Inheritance & Dependencies
    Inherits from:
        - IProcessor[T] (interface from wattleflow.core)
        - Attribute (from wattleflow.concrete.attribute)
        - ABC (abstract base class for enforcing @abstractmethod)
    Uses:
        - IStrategy: For auditing/logging.
        - IBlackboard: Shared state management.
        - IPipeline: Executes tasks within workflows.

2. Core Responsibilities
    Task Processing
        - process_tasks(): Iterates over a dataset (self._iterator) and processes
          items using pipelines.
    Auditing
        - Uses _strategy_audit to generate logs.
    Blackboard Integration
        - _blackboard.audit = self.audit: Hooks into the blackboard's auditing system.
        - Ensures cleanup via __del__().
    Configuration & Type Safety
        - Uses evaluate() for runtime type checks.
        - Limits allowed types for configuration parameters.
    Iterator-Based Data Processing
        - Implements __next__() for iterable behavior.
        - Calls create_iterator() (abstract) to define data sources.

3. Since GenericProcessor inherits from Attribute, it benefits from:
    - Strict Type Validation
    - evaluate() ensures strategy_audit, blackboard, pipelines match expected types.
    - allowed(self._allowed, **kwargs) enforces allowed attributes.

4. Dynamic Configuration
    - configure(**kwargs) calls push() to store attributes dynamically.
    - Restricts attributes to bool, dict, list, str.
    - Class Instantiation & Injection
"""

from abc import abstractmethod, ABC
from typing import Final, Generator, Iterator, Optional, Type, TypeVar
from wattleflow.core import IStrategy
from wattleflow.core import IBlackboard, IProcessor
from wattleflow.concrete.attribute import Attribute
from wattleflow.concrete.exception import ProcessorException
from wattleflow.helpers.functions import _NC

T = TypeVar("T")


class GenericProcessor(IProcessor[T], Attribute, ABC):
    _expected_type: Type[T] = T
    _cycle: int = 0
    _current: Optional[T] = None
    _blackboard: IBlackboard = None
    _pipelines: Final[list]
    _iterator: Iterator[T]
    _allowed: list = []

    def __init__(
        self,
        strategy_audit: IStrategy,
        blackboard: IBlackboard,
        pipelines: list,
        allowed: list = [],
        **kwargs,
    ):
        super().__init__()
        self.evaluate(pipelines, list)
        if not len(pipelines) > 0:
            raise ValueError("Empty list: [pipelines].")

        self.evaluate(strategy_audit, IStrategy)
        self.evaluate(blackboard, IBlackboard)
        self.evaluate(allowed, list)
        self._strategy_audit = strategy_audit
        self._blackboard = blackboard
        self._pipelines = pipelines
        self._allowed = allowed
        self.configure(**kwargs)

        # hack ...
        self._blackboard.audit = self.audit
        self._iterator = self.create_iterator()

    @property
    def blackboard(self) -> IBlackboard:
        return self._blackboard

    @property
    def cycle(self) -> int:
        return self._cycle

    def __del__(self):
        if self._blackboard:
            self._blackboard.clean()

    def __next__(self) -> T:
        try:
            self._current = next(self._iterator)
            self._cycle += 1
            return self._current
        except StopIteration:
            raise

    def audit(self, caller, *args, **kwargs):
        self._strategy_audit.generate(caller=self, owner=caller, *args, **kwargs)

    def configure(self, **kwargs):
        if not self.allowed(self._allowed, **kwargs):
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
            else:
                error = f"Restricted type: {_NC(value)}.{name}. [bool, dict, list, str]"
                raise AttributeError(error)

    def reset(self):
        self._iterator = self.create_iterator()
        self._step = 0

    def process_tasks(self):
        try:
            for item in self:
                for pipeline in self._pipelines:
                    pipeline.process(processor=self, item=item)
        except StopIteration:
            pass
        except AttributeError as e:
            raise AttributeError(e)
        except Exception as e:
            raise ProcessorException(caller=self, error=e)

    @abstractmethod
    def create_iterator(self) -> Generator[T, None, None]:
        pass
