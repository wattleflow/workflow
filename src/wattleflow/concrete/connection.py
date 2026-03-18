# Module name: connection.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: Defines abstract, observable connection classes for the Wattleflow framework.
Provides a stateful connection lifecycle (create, connect, disconnect), observer notifications,
 ontext-manager support, and integrated audit logging. Implements a PresetDecorator hook
for runtime configuration and exposes a generic operation interface for connect/disconnect actions.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from contextlib import contextmanager
from typing import Any, Dict, Generator, Generic, Optional, Union

from wattleflow.core import IObservable, IObserver, IFacade, T
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event, Operation
from wattleflow.decorators.preset import PresetDecorator


Operational = Generator[T, None, None]


class State(Enum):
    Closed = 0
    Constructing = 1
    Creating = 2
    New = 3
    Created = 4
    Connecting = 5
    Connected = 6


class ConnectionObserverInterface(IObservable, IFacade, ABC):
    __slots__ = ("_observers",)

    def __init__(self) -> None:
        IObservable.__init__(self)
        IFacade.__init__(self)
        self._observers: Dict[str, IObserver] = {}

    # region FIX-8
    # Provjera tipa observera prije dodavanja
    # Bez provjere, svaki objekt s .name atributom mogao bi biti ubačen kao observer.
    def subscribe(self, observer: IObserver) -> None:
        if not isinstance(observer, IObserver):
            raise TypeError(f"Expected IObserver, got {type(observer).__name__}")
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    # endregion FIX-8

    def subscribe_observer(self, observer: IObserver) -> None:
        self.subscribe(observer)

    # region FIX-7
    # Iznimke pojedinog observera ne smiju blokirati ostale
    # Ako jedan observer baci iznimku, ostali bi ostali ne-pozvani, što može
    # prekinuti lifecycle konekcije. Svaki observer se sada obrađuje izolirano.
    def notify(self, owner, **kwargs) -> None:
        for observer in self._observers.values():
            try:
                observer.update(owner, **kwargs)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "Observer '%s' raised an exception during notify: %s",
                    observer.name,
                    e,
                )

    # endregion FIX-7

    @abstractmethod
    def operation(self, action: Any) -> Any:
        pass


class GenericConnection(ConnectionObserverInterface, AuditLogger, Generic[T], ABC):
    # region FIX-1: Uklonjen duplikat '_observers' iz __slots__
    # '_observers' je već deklariran u ConnectionObserverInterface.__slots__.
    # Duplikat u podklasi može uzrokovati AttributeError pri višestrukom nasljeđivanju.
    #
    # FIX-2:
    # Dodan '_context' koji nedostajao u __slots__
    # '__enter__' koristi self._context, ali bez deklaracije u __slots__
    # svaki pristup uzrokovao bi AttributeError.
    __slots__ = (
        "_connection",
        "_connection_name",
        "_context",
        "_engine",
        "_initialised",
        "_logger",
        "_preset",
        "_state",
    )
    # endregion FIX-2

    def __init__(
        self,
        level: int,
        connection_name: str,
        handler: Optional[logging.Handler] = None,
        **kwargs: Any,
    ) -> None:

        self._state = State.Constructing
        self._engine: object = None
        self._connection: T = None  # type: ignore
        self._context = None
        self._connection_name: str = connection_name
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        ConnectionObserverInterface.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.create_connection()

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            connection_name=self._connection_name,
            state=self.state.name,
            preset=repr(self._preset),
        )

    @property
    def connected(self) -> bool:
        return self._state is State.Connected

    # region FIX-5
    # Dokumentirano da property vraća None kada veza nije uspostavljena
    # Pozivatelji koji ne provjere stanje mogu dobiti None bez jasnog razloga.
    # Ponašanje je zadržano, ali je eksplicitno dokumentirano kako bi se spriječilo
    # neočekivano korištenje.
    @property
    def connection(self) -> Optional[T]:
        """Returns the active connection, or None if not connected.
        Always check `self.connected` before use."""
        return self._connection if self.connected else None

    # endregion FIX-5

    @property
    def connection_name(self) -> str:
        return self._connection_name

    @property
    def state(self) -> State:
        return self._state

    # region FIX-3
    # Event.Completed is logged after the operaction
    def operation(self, action: Operation) -> Union[Operational, None]:
        self.debug(msg=Event.Operation.value, step=Event.Started.value, action=action)
        if action is Operation.Connect:
            result = self.connect()
            self.debug(
                msg=Event.Operation.value,
                step=Event.Completed.value,
                action=action,
            )
            return result

        if action is Operation.Disconnect:
            result = self.disconnect()
            self.debug(
                msg=Event.Operation.value,
                step=Event.Completed.value,
                action=action,
            )
            return result

        self.debug(
            msg=Event.Operation.value,
            step=Event.Completed.value,
            action="raise error",
        )
        raise RuntimeError(f"Unknown operation: {action.value}")

    # endregion FIX-3

    # region Abstract methods
    @abstractmethod
    def create_connection(self) -> None:
        """
        Create connection and return new connection type.
        NOTE: Don't forget to change state = State.Created
        """
        ...

    @contextmanager
    @abstractmethod
    def connect(self) -> Generator[T, None, None]:
        """
        NOTE: Change state = State.Connected

        Context manager returns connection:
            with conn.connect() as connection:
                ...
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close active connection and reset status.
        NOTE: Change state = State.Closed
        """
        ...

    # endregion Abstract methods

    # region Context handling
    @contextmanager
    def context(self) -> Generator[T, None, None]:
        self.debug(msg=Event.Context.value, step=Event.Started.value, fnc="context")
        with self.connect() as connection:
            yield connection
        self.debug(msg=Event.Context.value, step=Event.Completed.value, fnc="context")

    # endregion Context handling

    # region FIX-4
    def __del__(self):
        try:
            self.debug(
                msg=Event.Delete.value,
                step=Event.Starting.value,
                fnc="__del__",
            )
            self.disconnect()
            self.debug(
                msg=Event.Delete.value,
                step=Event.Completed.value,
                fnc="__del__",
            )
        except Exception as e:
            self.warning(
                msg=Event.Delete.value,
                error=f"Caught during __del__ disconnect: {e}",
                connection=self._connection_name,
            )

    # endregion FIX-4

    def __enter__(self):
        self.debug(msg=Event.Enter.value, step=Event.Starting.value, fnc="__enter__")
        self._context = self.connect()
        self.debug(msg=Event.Enter.value, step=Event.Completed.value, fnc="__enter__")
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        self.debug(msg="__exit__")
        try:
            return self._context.__exit__(exc_type, exc, tb)
        finally:
            self._context = None

    # region FIX-6: __getattr__ provjerava __slots__ cijelog MRO-a, ne samo lokalne
    # Originalnim kodom se provjeravao samo self.__slots__ (lokalni), što znači da
    # atributi iz roditeljskih klasa (npr. _observers iz ConnectionObserverInterface)
    # nisu bili zaštićeni i prosljeđivali su se na PresetDecorator — potencijalno
    # izlažući interne atribute.
    def __getattr__(self, name: str) -> Any:
        all_slots: set = set()
        for cls in type(self).__mro__:
            all_slots.update(getattr(cls, "__slots__", ()))

        if name in all_slots:
            return object.__getattribute__(self, name)

        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    # endregion

    def __repr__(self) -> str:
        return f"{self.name}:{self.state.name}"
