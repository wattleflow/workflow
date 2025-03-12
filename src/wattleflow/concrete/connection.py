# Module Name: core/concrete/connection.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete connection classes.

from abc import abstractmethod, ABC
from typing import Dict, Generator, Optional
from wattleflow.core import (
    IStrategy,
    IObservable,
    IObserver,
    IPrototype,
    IFacade,
)
from wattleflow.concrete import Attribute
from wattleflow.constants import Operation


"""
1. Connection Lifecycle Management
    - operation(action: Operation) → bool
        - Delegates connection actions to connect() and disconnect().
        - Raises ConnectionException for unknown operations.
    - create_connection() (Abstract)
        - Meant to be implemented in concrete subclasses.

2. Observer Pattern Implementation
    - ConnectionObserverInterface
        - Maintains a _observers dictionary for tracking connected observers.
        - subscribe(observer): Registers observers to listen for changes.
        - notify(owner, **kwargs): Notifies observers of state changes.

3. Settings Management
    - Settings Class
        - Ensures only allowed settings are stored.
        - Handles mandatory settings validation using self.mandatory().

4. Connection Cloning (Prototype Pattern)
    - clone() (Abstract)
        - Enables creating a copy of an existing connection.
        - Expected to be implemented by subclasses.
"""


class Settings(Attribute):
    def __init__(self, allowed: list, **kwargs):
        self.allowed(allowed=allowed, **kwargs)
        # for key in mandatory:
        #     self.mandatory(name=key, cls=object, **kwargs)
        for name, value in kwargs.items():
            self.push(name, value)

    def __getattr__(self, name):
        try:
            return self.__dict__[name]
        except KeyError:
            return None

    def get(self, name: str, default: str = None):
        return getattr(self, name, default)

    def todict(self):
        return self.__dict__


class ConnectionObserverInterface(IObservable):
    def __init__(self):
        self._observers: Dict[str, IObserver] = {}

    def subscribe(self, observer: IObserver) -> None:
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def notify(self, owner, **kwargs):
        for observer in self._observers.values():
            observer.update(owner, **kwargs)


class GenericConnection(
    IFacade, IPrototype, Attribute, ConnectionObserverInterface, ABC
):
    _name: str = None
    _config: Settings = None
    _connection: Optional[object] = None
    _connected: bool = False

    def __init__(self, strategy_audit: IStrategy, **configuration):
        super().__init__()
        self.evaluate(strategy_audit, IStrategy)
        self._strategy_audit = strategy_audit
        self.create_connection(**configuration)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def connection(self) -> object:
        if self._connected:
            return self._connection
        return None

    def audit(self, event, **kwargs) -> None:
        self._strategy_audit.generate(caller=self, event=event, **kwargs)

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            return self.connect()
        elif action == Operation.Disconnect:
            return self.disconnect()
        else:
            from wattleflow.concrete import ConnectionException

            raise ConnectionException(
                caller=self, error=f"Urecognised operation! [{action}]"
            )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    @abstractmethod
    def create_connection(self, **configuration):
        pass

    @abstractmethod
    def clone(self) -> object:
        pass

    @abstractmethod
    def connect(self) -> Generator['GenericConnection', None, None]:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass
