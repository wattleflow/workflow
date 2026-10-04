# Module name: concrete/connection.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from enum import Enum
from contextlib import contextmanager
from typing import Any, Generic, TypeVar
from collections.abc import Generator
from wattleflow.core import IObservable, IObserver
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import ConnectionException, ManagerException
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation
from wattleflow.decorators.preset import PresetDecorator
# from wattleflow.decorators.measure import measured  # retired

# --------------------------------------------------------------------------- #
# endregion imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

Connection = TypeVar("Connection", bound=object)


# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region State Machine                                                        #
# --------------------------------------------------------------------------- #


class ConnectionAction(str, Enum):
    CREATE = "create"
    CREATE_OK = "create_ok"
    CREATE_FAIL = "create_fail"
    CONNECT = "connect"
    CONNECT_OK = "connect_ok"
    CONNECT_FAIL = "connect_fail"
    DISCONNECT = "disconnect"
    CLOSE = "close"
    CLOSE_OK = "close_ok"
    CLOSE_FAIL = "close_fail"
    RESET = "reset"


class ConnectionState(str, Enum):
    NEW = "new"
    CREATING = "creating"
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


# (current_state, action) -> next_state
TRANSITIONS = {
    # create lifecycle
    (ConnectionState.NEW, ConnectionAction.CREATE): ConnectionState.CREATING,
    (ConnectionState.CLOSED, ConnectionAction.CREATE): ConnectionState.CREATING,
    (ConnectionState.CREATING, ConnectionAction.CREATE_OK): ConnectionState.CREATED,
    (ConnectionState.CREATING, ConnectionAction.CREATE_FAIL): ConnectionState.FAILED,
    # session lifecycle (within connect() context manager)
    (ConnectionState.CREATED, ConnectionAction.CONNECT): ConnectionState.CONNECTING,
    (
        ConnectionState.CONNECTING,
        ConnectionAction.CONNECT_OK,
    ): ConnectionState.CONNECTED,
    (
        ConnectionState.CONNECTING,
        ConnectionAction.CONNECT_FAIL,
    ): ConnectionState.CREATED,
    (ConnectionState.CONNECTED, ConnectionAction.DISCONNECT): ConnectionState.CREATED,
    # close lifecycle (engine teardown)
    (ConnectionState.CREATING, ConnectionAction.CLOSE): ConnectionState.CLOSING,
    (ConnectionState.CREATED, ConnectionAction.CLOSE): ConnectionState.CLOSING,
    (ConnectionState.CONNECTING, ConnectionAction.CLOSE): ConnectionState.CLOSING,
    (ConnectionState.CONNECTED, ConnectionAction.CLOSE): ConnectionState.CLOSING,
    (ConnectionState.FAILED, ConnectionAction.CLOSE): ConnectionState.CLOSING,
    (ConnectionState.CLOSING, ConnectionAction.CLOSE_OK): ConnectionState.CLOSED,
    (ConnectionState.CLOSING, ConnectionAction.CLOSE_FAIL): ConnectionState.FAILED,
    # reset
    (ConnectionState.CLOSED, ConnectionAction.RESET): ConnectionState.NEW,
    (ConnectionState.FAILED, ConnectionAction.RESET): ConnectionState.NEW,
}

# --------------------------------------------------------------------------- #
# endregion State Machine                                                     #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Interfaces                                                           #
# --------------------------------------------------------------------------- #


class ConnectionObserverInterface(Wattleflow, IObservable, ABC):
    __slots__ = ("_observers",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._observers: dict[str, IObserver] = {}

    def subscribe(self, observer: IObserver) -> None:
        if not isinstance(observer, IObserver):
            raise TypeError(f"Expected IObserver, got {type(observer).__name__}")
        if observer.name not in self._observers:
            self._observers[observer.name] = observer

    def subscribe_observer(self, observer: IObserver) -> None:
        self.subscribe(observer)

    def transfer_observers(self, target: IObservable) -> None:
        """Subscribe every observer of this connection to `target`.

        Used by `ConnectionManager.hot_swap`.
        """
        for observer in list(self._observers.values()):
            target.subscribe(observer)

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


# --------------------------------------------------------------------------- #
# endregion Interfaces                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class GenericConnection(ConnectionObserverInterface, Generic[Connection], ABC):
    # v0.0.1.23: DEF-CON-04, the generic class declares its own argument once; the preset unions
    # `ALLOWED` across the MRO, so a specialisation lists only what it adds
    ALLOWED = ["lazy_loading"]

    __slots__ = (
        "_connection_name",
        "_connection",
        "_context",
        "_engine",
        "_lazy_loading",
        "_preset",
        "_fsm",
        "_version",
    )

    def __init__(self, **kwargs) -> None:
        connection_name = kwargs.pop("connection_name", None)

        super().__init__(**kwargs)

        if connection_name is None or connection_name.strip() == "":
            error = "`connection_name` must be provided in connection kwargs!"
            raise ConnectionException(caller=self, error=error, **kwargs)

        # Subclasses declare configurable kwargs via the ``ALLOWED`` class
        # attribute; PresetDecorator resolves it from the type (NFRQ-ORG-07), so
        # this no longer needs its own copy of that resolution.
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)
        self._connection_name = connection_name
        self._lazy_loading = kwargs.pop("lazy_loading", False)
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            ConnectionState.NEW,
            name="ConnectionFSM",
        )
        self._engine: object = None
        self._connection: Connection = None
        self._context = None
        self._version: str | None = None

        if not self._lazy_loading:
            self.ensure_created()

        self.debug(
            msg=Event.Constructor,
            step=Event.Completed,
            connection_name=self.connection_name,
            state=self._fsm.state.value,
            preset=repr(self._preset),
            level=self._level,
            handler=self._handler,
        )

    def _ensure_created(self) -> None:
        self.debug(
            msg=Event.Validating,
            step=Event.Check,
            state=self._fsm.state.value,
        )
        if self._fsm.state is ConnectionState.FAILED:
            return
        if self._fsm.state in (
            ConnectionState.CREATED,
            ConnectionState.CONNECTED,
            ConnectionState.CONNECTING,
        ):
            return
        self.ensure_created()

    # region Context handling

    @contextmanager
    def context(self) -> Generator[Connection, None, None]:
        self.debug(msg=Event.Context, step=Event.Started, fnc="context")
        with self.connect() as conn:
            yield conn
        self.debug(msg=Event.Context, step=Event.Completed, fnc="context")

    # endregion Context handling

    def __del__(self):
        try:
            object.__getattribute__(self, "_fsm")
        except AttributeError:
            return
        try:
            self.debug(msg=Event.Destructor, step=Event.Starting)
            self.ensure_closed()
            self.debug(msg=Event.Destructor, step=Event.Completed)
        except Exception:
            pass

    def __enter__(self):
        self.debug(msg=Event.Enter, step=Event.Starting, fnc="__enter__")
        self._context = self.connect()
        self.debug(msg=Event.Enter, step=Event.Completed, fnc="__enter__")
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        self.debug(msg=Event.Exit)
        try:
            return self._context.__exit__(exc_type, exc, tb)
        finally:
            self._context = None

    def __getattr__(self, name: str) -> Any:
        cls = type(self)
        # v0.0.1.23: DEF-CON-03, the slot set is constant per type; read from `__dict__` so a
        # subclass never inherits its parent's set
        all_slots = cls.__dict__.get("_slot_names")
        if all_slots is None:
            all_slots = frozenset(s for base in cls.__mro__ for s in getattr(base, "__slots__", ()))
            cls._slot_names = all_slots

        if name in all_slots:
            return object.__getattribute__(self, name)

        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}:{self._fsm.state.value}"

    @property
    def connection_name(self) -> str:
        return self._connection_name

    @property
    def connected(self) -> bool:
        return self._fsm.state is ConnectionState.CONNECTED

    # v0.0.1.23: DEF-DRV-06, true exactly where `ensure_created` returns without acting, so a
    # caller can skip a connect request that would only be audited (any other state acts or raises)
    @property
    def created(self) -> bool:
        return self._fsm.state in (
            ConnectionState.CREATING,
            ConnectionState.CREATED,
            ConnectionState.CONNECTED,
        )

    @property
    def connection(self) -> Connection | None:
        return self._connection if self.connected else None

    @property
    def state(self) -> ConnectionState:
        return self._fsm.state

    @property
    def version(self) -> str | None:
        """Version of the remote system as it reports it; `None` when unknown or not applicable."""
        # v0.0.1.23: DEF-CON-02, a specialisation fills it only from the remote system's own answer
        return self._version

    # region FSM lifecycle

    def can(self, action: ConnectionAction) -> bool:
        return self._fsm.can(action)

    def ensure_created(self) -> None:
        if self._fsm.state in (
            ConnectionState.CREATED,
            ConnectionState.CONNECTED,
            ConnectionState.CREATING,
        ):
            return
        if not self._fsm.can(ConnectionAction.CREATE):
            raise ManagerException(
                caller=self,
                error=f"Cannot create connection from state '{self._fsm.state.value}'",
            )
        self._fsm.apply(ConnectionAction.CREATE)
        try:
            self.create_connection()
            self._fsm.apply(ConnectionAction.CREATE_OK)
        except Exception as e:
            self._fsm.apply(ConnectionAction.CREATE_FAIL)
            self.debug(msg=Event.Create, step=Event.Failed, error=str(e))
            raise

    def ensure_closed(self) -> None:
        if self._fsm.state in (ConnectionState.CLOSED, ConnectionState.NEW):
            return
        if not self._fsm.can(ConnectionAction.CLOSE):
            return
        self._fsm.apply(ConnectionAction.CLOSE)
        try:
            self.disconnect()
            self._fsm.apply(ConnectionAction.CLOSE_OK)
        except Exception as e:
            self._fsm.apply(ConnectionAction.CLOSE_FAIL)
            self.debug(msg=Event.Close, step=Event.Failed, error=str(e))
            raise

    def reset(self) -> None:
        if self._fsm.can(ConnectionAction.RESET):
            self._fsm.apply(ConnectionAction.RESET)

    # endregion FSM lifecycle

    def operation(self, action: Operation, **kwargs: Any) -> bool:
        """Entry point of a managed object (`ConnectionManager.operation`).

        `Connect` and `Disconnect` are carried out through `request`; any other
        action is reported and answered with `False`.
        """
        if action not in (Operation.Connect, Operation.Disconnect):
            self.warning(
                msg=Event.Operation,
                step=Event.Failed,
                action=getattr(action, "name", action),
                reason="unsupported action",
            )
            return False
        self.request(action=action, **kwargs)
        return True

    def request(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        self.debug(msg=Event.Operation, step=Event.Started, action=action)

        if action is Operation.Connect:
            result = self.ensure_created()
            self.debug(msg=Event.Operation, step=Event.Completed, action=action)
            return result

        if action is Operation.Disconnect:
            result = self.ensure_closed()
            self.debug(msg=Event.Operation, step=Event.Completed, action=action)
            return result

        # v0.0.1.23: DEF-CON-01, every failure of this module is a ConnectionException (BR-PTN-05)
        raise ConnectionException(caller=self, error=f"Unknown action: {action}")

    # region Abstract methods

    @abstractmethod
    def create_connection(self) -> None:
        """
        Create the connection engine or pool.
        Called by ensure_created() — do not manage FSM state here.
        """
        ...

    @contextmanager
    @abstractmethod
    def connect(self) -> Generator[Connection, None, None]:
        """
        Context manager that yields an active connection session.
        Use self._fsm.apply(ConnectionAction.XXX) for state transitions:
            CONNECT before opening, CONNECT_OK on success, CONNECT_FAIL on error,
            DISCONNECT in finally to return to CREATED.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """
        Tear down the engine or pool.
        Called by ensure_closed() — do not manage FSM state here.
        """
        ...

    # endregion Abstract methods


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


__all__ = [
    "ConnectionAction",
    "ConnectionState",
    "GenericConnection",
    "ConnectionObserverInterface",
]
