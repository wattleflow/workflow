# Module Name: concrete/connection.py
# Description: This modul contains concrete connection classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from abc import abstractmethod, ABC
from contextlib import contextmanager
from logging import Handler
from typing import Dict, Optional
from wattleflow.core import (
    IObservable,
    IObserver,
    IFacade,
)
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event, Operation


class ConnectionObserverInterface(IObservable, IFacade, ABC):
    # Reduce memory footprint and eliminate __dict__ i __weakref__
    __slots__ = (
        "_initialised",
        "_observers",
        "_connection_name",
        "_preset",
        "_connection",
        "_connected",
        # _level: int = NOTSET
        # _handler: Optional[Handler] = None
    )

    def __init__(
        self,
    ):
        IObservable.__init__(self)
        IFacade.__init__(self)
        self._observers: Dict[str, IObserver] = {}

    def subscribe(self, observer: IObserver) -> None:
        self.subscribe_observer(observer)

    def subscribe_observer(self, observer: IObserver) -> None:
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def notify(self, owner, **kwargs):
        for observer in self._observers.values():
            observer.update(owner, **kwargs)

    @abstractmethod
    def operation(self, action: Operation) -> bool:
        pass


class GenericConnection(
    ConnectionObserverInterface,
    AuditLogger,
    ABC,
):
    def __init__(
        self,
        level: int,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        from wattleflow.helpers.preset import (
            Preset,
        )  # pylint: disable=import-outside-toplevel

        self._preset: Preset = Preset()
        self._connection: Optional[object] = None
        self._connected: bool = False

        ConnectionObserverInterface.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._connection_name: Optional[str] = self.name
        self._preset.configure(raise_errors=True, **kwargs)
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
        if action == Operation.Disconnect:
            return self.disconnect()

        from wattleflow.concrete import (
            ConnectionException,
        )  # pylint: disable=import-outside-toplevel

        raise ConnectionException(
            caller=self, error=f"Urecognised operation! [{action}]"
        )

    @contextmanager
    def context(self):
        self.debug(msg="context.__enter__")
        try:
            self.connect()
            yield self
        finally:
            self.debug(msg="context.__exit__")
            self.disconnect()

    def __enter__(self):
        return self.context().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self.context().__exit__(exc_type, exc_value, traceback)

    @abstractmethod
    def create_connection(self, **configuration):
        pass

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass
