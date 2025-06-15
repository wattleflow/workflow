# Module Name: concrete/connection.py
# Description: This modul contains concrete connection classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import abstractmethod, ABC
from logging import Handler, NOTSET
from typing import Dict, Generator, Optional
from wattleflow.core import (
    IObservable,
    IObserver,
    IPrototype,
    IFacade,
)
from wattleflow.concrete import Attribute, AuditLogger
from wattleflow.constants import Event, Operation


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

    def get(self, name: str, default: Optional[str] = None):
        result = getattr(self, name, default)
        if result is None:
            return default
        return result

    def to_dict(self):
        return self.__dict__


class ConnectionObserverInterface(IObservable):
    def __init__(self):
        IObservable.__init__(self)
        self._observers: Dict[str, IObserver] = {}

    def subscribe(self, observer: IObserver) -> None:
        self.subscribe_observer(observer)

    def subscribe_observer(self, observer: IObserver) -> None:
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def notify(self, owner, **kwargs):
        for observer in self._observers.values():
            observer.update(owner, **kwargs)


class GenericConnection(
    IFacade,
    IPrototype,
    Attribute,
    AuditLogger,
    ConnectionObserverInterface,
    ABC,
):
    def __init__(
        self,
        level: int,
        handler: Optional[Handler] = None,
        **configuration,
    ):
        self._name: Optional[str] = None
        self._config: Optional[Settings] = None
        self._connection: Optional[object] = None
        self._connected: bool = False
        self._level: int = NOTSET
        self._handler: Optional[Handler] = None

        IFacade.__init__(self)
        ConnectionObserverInterface.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._level = level
        self._handler = handler
        self.create_connection(**configuration)
        self.debug(msg=Event.Constructor.value)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def connection(self) -> object:
        if self._connected:
            return self._connection
        return None

    def operation(self, action: Operation) -> bool:
        self.debug(msg="operation", action=action.value)

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
        self.debug(msg="__enter__")
        # self.connect()
        next(self.connect())  # aktivira generator
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.debug(msg="__exit__")
        self.disconnect()

    @abstractmethod
    def create_connection(self, **configuration):
        pass

    @abstractmethod
    def clone(self) -> object:
        pass

    @abstractmethod
    def connect(self) -> Generator["GenericConnection", None, None]:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass
