import logging
from abc import ABC, abstractmethod
from enum import Enum
from contextlib import contextmanager
from typing import Any, Dict, Generator, Generic, Optional, TypeVar, Union

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

    def subscribe(self, observer: IObserver) -> None:
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def subscribe_observer(self, observer: IObserver) -> None:
        self.subscribe(observer)

    def notify(self, owner, **kwargs) -> None:
        for observer in self._observers.values():
            observer.update(owner, **kwargs)

    @abstractmethod
    def operation(self, action: Any) -> Any: ...


class GenericConnection(ConnectionObserverInterface, AuditLogger, Generic[T], ABC):
    __slots__ = (
        "_connection",
        "_connection_name",
        "_context",
        "_engine",
        "_logger",
        "_observers",
        "_preset",
        "_state",
    )

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
        self._connection_name: str = connection_name
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

        ConnectionObserverInterface.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.create_connection()

        self.debug(
            msg=Event.Constructor.value,
            connection_name=self._connection_name,
            state=self.state.name,
            preset=repr(self._preset),
        )

    @property
    def connected(self) -> bool:
        return self._state is State.Connected

    @property
    def connection(self) -> Optional[T]:
        return self._connection if self.connected else None

    @property
    def connection_name(self) -> str:
        return self._connection_name

    @property
    def state(self) -> State:
        return self._state

    def operation(self, action: Operation) -> Union[Operational, None]:
        if action is Operation.Connect:
            return self.connect()

        if action is Operation.Disconnect:
            return self.disconnect()

        raise RuntimeError(f"Unknown operation: {action.value}")

    # ---------- Abstract methods ----------
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

    # ---------- Context handling ----------
    @contextmanager
    def context(self) -> Generator[T, None, None]:
        with self.connect() as connection:
            yield connection

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    # def __enter__(self) -> "GenericConnection[T]":
    #     self.connect()
    #     return self

    # def __exit__(self, exc_type, exc, tb):
    #     self.disconnect()

    def __enter__(self):
        self.debug(msg="__enter__")
        self._context = self.connect()
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        self.debug(msg="__exit__")
        try:
            return self._context.__exit__(exc_type, exc, tb)
        finally:
            self._context = None

    def __getattr__(self, name: str) -> Any:
        # if name in self.__slots__:
        #     return object.__getattribute__(self, name)
        try:
            if object.__getattribute__(self, name):
                return object.__getattribute__(self, name)

            if self.__getattribute__(name):
                return self.__getattribute__(name)

        except:  # noqa: E722
            if getattr(self, "_preset"):
                return getattr(self._preset, name)

        raise AttributeError(f"{self.name}.{name} not found!")

    def __repr__(self) -> str:
        return f"{self.name}:{self.state.name}"
