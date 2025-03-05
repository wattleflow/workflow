# Module Name: core/concrete/connection.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete connection classes.

from abc import abstractmethod, ABC
from enum import Enum
from typing import Dict, Optional
from wattleflow.core import IStrategy, IObservable, IObserver
from wattleflow.core import IPrototype
from wattleflow.core import IFacade
from wattleflow.concrete.exception import ConnectionException
from wattleflow.constants.errors import ERROR_UNEXPECTED_TYPE
from wattleflow.concrete.attribute import Attribute
from wattleflow.helpers.functions import _NC, _NT


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


class Operation(Enum):
    Connect = 1
    Disconnect = 0


class Settings(Attribute):
    def __init__(self, allowed: list, mandatory: list, **kwargs):

        self.allowed(allowed=allowed, **kwargs)

        for key in mandatory:
            self.mandatory(name=key, cls=object, kwargs=kwargs)

        for name, value in kwargs.items():
            self.push(name, value)

    def get(self, name: str):
        if hasattr(self, name):
            return getattr(self, name) if name != "password" else None
        return None


class ConnectionObserverInterface(IObservable):
    def __init__(self):
        self._observers: Dict[str, IObserver] = {}

    def subscribe(self, observer: IObserver) -> None:
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def notify(self, owner, **kwargs):
        for observer in self._observers.values():
            observer.update(owner, **kwargs)


class GenericConnection(IFacade, IPrototype, ConnectionObserverInterface, ABC):
    def __init__(
        self, strategy_audit: IStrategy, connection_manager: IObserver, **settings
    ):
        super().__init__()

        if not isinstance(strategy_audit, IStrategy):
            raise ConnectionException(
                caller=self,
                error=ERROR_UNEXPECTED_TYPE.format(_NC(strategy_audit), _NT(IStrategy)),
            )

        self._strategy_audit = strategy_audit
        self._manager: Optional[IObserver] = connection_manager
        self._settings: Optional[object] = None
        self._connection: Optional[object] = None
        self._connected: bool = False
        self.create_conenction(**settings)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def connection(self) -> object:
        return self._connection

    def audit(self, event, **kwargs) -> None:
        self._strategy_audit.write(caller=self, event=event, **kwargs)

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            return self.connect()
        elif action == Operation.Disconnect:
            return self.disconnect()
        else:
            raise ConnectionException(
                caller=self, error=f"Urecognised operation! [{action}]"
            )

    @abstractmethod
    def create_connection(self) -> None:
        pass

    @abstractmethod
    def clone(self) -> IFacade:
        pass

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass
