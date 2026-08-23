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

# --------------------------------------------------------------------------- #
# endregion imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class ConnectionManagerException(ManagerException):
    pass


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

        # The old form passed `formating={}` (the legacy spelling) when the
        # caller supplied none, which
        # only worked because Formatter falls back on a falsy fmt.
        super().__init__(**kwargs)

        if connection_name is None or connection_name.strip() == "":
            error = "`connection_name` must be provided in connection kwargs!"
            raise ConnectionException(caller=self, error=error, **kwargs)

        # Subclasses declare configurable kwargs via the ``ALLOWED`` class
        # attribute; PresetDecorator resolves it from the type (NFR-ORG-07), so
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
        self._version: str = None

        if not self._lazy_loading:
            self.ensure_created()

        self.debug(
            msg=Event.Constructor.name,
            step=Event.Completed.name,
            connection_name=self.connection_name,
            state=self._fsm.state.value,
            preset=repr(self._preset),
            level=self._level,
            handler=self._handler,
        )

    def _ensure_created(self) -> None:
        self.debug(
            msg=Event.Validating.name,
            step="ensure_created",
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
        self.debug(msg=Event.Context.name, step=Event.Started.name, fnc="context")
        with self.connect() as conn:
            yield conn
        self.debug(msg=Event.Context.name, step=Event.Completed.name, fnc="context")

    # endregion Context handling

    def __del__(self):
        # v0.0.0.98 (DR-WFL-014 t.4): a half-built instance carries neither FSM
        # nor logger, so reporting here would bury the real exception.
        try:
            object.__getattribute__(self, "_fsm")
        except AttributeError:
            return
        try:
            self.debug(msg=Event.Destructor.name, step=Event.Starting.value)
            self.ensure_closed()
            self.debug(msg=Event.Destructor.name, step=Event.Completed.name)
        except Exception:
            pass

    def __enter__(self):
        self.debug(msg=Event.Enter.name, step=Event.Starting.value, fnc="__enter__")
        self._context = self.connect()
        self.debug(msg=Event.Enter.name, step=Event.Completed.name, fnc="__enter__")
        return self._context.__enter__()

    def __exit__(self, exc_type, exc, tb):
        self.debug(msg=Event.Exit.name)
        try:
            return self._context.__exit__(exc_type, exc, tb)
        finally:
            self._context = None

    def __getattr__(self, name: str) -> Any:
        all_slots: set = set()
        for cls in type(self).__mro__:
            all_slots.update(getattr(cls, "__slots__", ()))

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

    @property
    def connection(self) -> Connection | None:
        return self._connection if self.connected else None

    @property
    def state(self) -> ConnectionState:
        return self._fsm.state

    @property
    def version(self) -> str:
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
            raise ConnectionManagerException(
                caller=self,
                error=f"Cannot create connection from state '{self._fsm.state.value}'",
            )
        self._fsm.apply(ConnectionAction.CREATE)
        try:
            self.create_connection()
            self._fsm.apply(ConnectionAction.CREATE_OK)
        except Exception:
            self._fsm.apply(ConnectionAction.CREATE_FAIL)
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
        except Exception:
            self._fsm.apply(ConnectionAction.CLOSE_FAIL)
            raise

    def reset(self) -> None:
        if self._fsm.can(ConnectionAction.RESET):
            self._fsm.apply(ConnectionAction.RESET)

    # endregion FSM lifecycle

    def hot_swap(self, name: str, new_connection: "GenericConnection") -> None:
        if name not in self._connections:
            raise ConnectionManagerException(
                caller=self, error=f"Connection '{name}' nije registrirana."
            )

        old_conn = self._connections[name]

        try:
            new_connection.request(action=Operation.Connect)
        except Exception as e:
            raise ConnectionManagerException(
                caller=self,
                error=f"Hot-swap failao, stara konekcija ostaje aktivna: {e}",
            ) from e

        self._connections[name] = new_connection
        self.notify_observers(name, new_connection=new_connection)

        try:
            old_conn.request(action=Operation.Disconnect)
        except Exception as e:
            self.warning(msg=Event.Swap.name, error=f"Old connection was not closed properly: {e}")

    def request(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        self.debug(msg=Event.Operation.name, step=Event.Started.name, action=action)

        if action is Operation.Connect:
            result = self.ensure_created()
            self.debug(msg=Event.Operation.name, step=Event.Completed.name, action=action)
            return result

        if action is Operation.Disconnect:
            result = self.ensure_closed()
            self.debug(msg=Event.Operation.name, step=Event.Completed.name, action=action)
            return result

        raise RuntimeError(f"Unknown action: {action}")

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
