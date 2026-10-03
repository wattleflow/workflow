# Module name: concrete/driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import logging
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any
from collections.abc import Callable
from wattleflow.core.behavioural import IObserver
from wattleflow.core.transactional import IDriver
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import DriverException
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation
from wattleflow.decorators.preset import PresetDecorator
# from wattleflow.decorators.measure import measured  # retired


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Metadata                                                             #
# --------------------------------------------------------------------------- #


__all__ = [
    "DriverAction",
    "DriverMetadata",
    "DriverState",
    "GenericDriver",
    "LazyDriverProxy",
]


@dataclass
class DriverMetadata:
    name: str
    version: str
    protocol: str
    capabilities: list[str]  # ["read", "write", "stream"]


# --------------------------------------------------------------------------- #
# endregion Metadata                                                          #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region State machine                                                        #
# --------------------------------------------------------------------------- #


class DriverAction(str, Enum):
    LOAD = "load"
    LOAD_OK = "load_ok"
    LOAD_FAIL = "load_fail"

    UNLOAD = "unload"
    UNLOAD_OK = "unload_ok"
    UNLOAD_FAIL = "unload_fail"

    PAUSE = "pause"
    RESET = "reset"


class DriverState(str, Enum):
    PENDING = "pending"
    LOADING = "loading"
    LIVE = "live"
    PAUSED = "paused"
    DEGRADED = "degraded"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"


# (current_state, action) -> next_state
TRANSITIONS: dict[tuple[DriverState, DriverAction], DriverState] = {
    # --- load lifecycle ---
    (DriverState.PENDING, DriverAction.LOAD): DriverState.LOADING,
    (DriverState.UNLOADED, DriverAction.LOAD): DriverState.LOADING,
    (DriverState.PAUSED, DriverAction.LOAD): DriverState.LOADING,
    (DriverState.DEGRADED, DriverAction.LOAD): DriverState.LOADING,
    (DriverState.LOADING, DriverAction.LOAD_OK): DriverState.LIVE,
    (DriverState.LOADING, DriverAction.LOAD_FAIL): DriverState.DEGRADED,
    # --- pause ---
    (DriverState.LIVE, DriverAction.PAUSE): DriverState.PAUSED,
    # --- unload lifecycle ---
    (DriverState.LIVE, DriverAction.UNLOAD): DriverState.UNLOADING,
    (DriverState.PAUSED, DriverAction.UNLOAD): DriverState.UNLOADING,
    (DriverState.DEGRADED, DriverAction.UNLOAD): DriverState.UNLOADING,
    (DriverState.UNLOADING, DriverAction.UNLOAD_OK): DriverState.UNLOADED,
    (DriverState.UNLOADING, DriverAction.UNLOAD_FAIL): DriverState.DEGRADED,
    # --- reset ---
    (DriverState.UNLOADED, DriverAction.RESET): DriverState.PENDING,
}


# --------------------------------------------------------------------------- #
# endregion State machine                                                     #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Drivers                                                              #
# --------------------------------------------------------------------------- #


# @measured()
class GenericDriver(Wattleflow, IDriver, IObserver, ABC):
    __slots__ = ("_fsm", "_preset")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            DriverState.PENDING,
            name="DriverFSM",
        )
        self._preset = PresetDecorator(parent=self, **kwargs)

    def __del__(self):
        # A failed __init__ still triggers __del__, and the interpreter may
        # already be tearing down its logging machinery. Bail out quietly
        # rather than emit "Exception ignored in __del__" noise.
        try:
            object.__getattribute__(self, "_fsm")
        except AttributeError:
            return
        try:
            self.debug(msg=Event.Destructor, step=Event.Started)
            self.ensure_unloaded()
            self.debug(msg=Event.Destructor, step=Event.Completed)
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        # PresetDecorator resolves real attributes on the parent first, so the
        # slot lookup needs no separate branch here. During partial
        # construction _preset is missing: raise a plain AttributeError so
        # callers (and Python itself) treat the attribute as absent.
        try:
            preset: PresetDecorator | None = object.__getattribute__(self, "_preset")
        except AttributeError:
            preset = None
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}(state={self._fsm.state.name})"

    @property
    def state(self) -> DriverState:
        return self._fsm.state

    # region lifecycle orchestration (FSM) ---

    def can(self, action: DriverAction) -> bool:
        return self._fsm.can(action)

    def ensure_live(self) -> None:
        if self._fsm.state == DriverState.LIVE:
            return

        if self._fsm.state == DriverState.LOADING:
            return

        if not self._fsm.can(DriverAction.LOAD):
            raise DriverException(
                caller=self,
                error=f"Cannot load from state {self._fsm.state}",
            )

        self._fsm.apply(DriverAction.LOAD)

        try:
            self.load()
            self._fsm.apply(DriverAction.LOAD_OK)
        except Exception as e:
            if self._fsm.can(DriverAction.LOAD_FAIL):
                self._fsm.apply(DriverAction.LOAD_FAIL)
            self.debug(msg=Event.Load, step=Event.Failed, error=str(e))
            raise

    def ensure_unloaded(self) -> None:
        if self._fsm.state == DriverState.UNLOADED:
            return

        if not self._fsm.can(DriverAction.UNLOAD):
            return

        self._fsm.apply(DriverAction.UNLOAD)

        try:
            self.close()
            self._fsm.apply(DriverAction.UNLOAD_OK)
        except Exception as e:
            # Same guard as ensure_live: never let bookkeeping mask the error.
            if self._fsm.can(DriverAction.UNLOAD_FAIL):
                self._fsm.apply(DriverAction.UNLOAD_FAIL)
            self.debug(msg=Event.Close, step=Event.Failed, error=str(e))
            raise

    def operation(self, action: Operation, **kwargs) -> bool:
        """Entry point of a managed object (`DriverManager.operation`).

        `Connect` loads the resource and `Disconnect` unloads it; any other
        action is reported and answered with `False`.
        """
        if action is Operation.Connect:
            self.ensure_live()
            return True
        if action is Operation.Disconnect:
            self.ensure_unloaded()
            return True
        self.warning(
            msg=Event.Operation,
            step=Event.Failed,
            action=getattr(action, "name", action),
            reason="unsupported action",
        )
        return False

    def pause(self) -> None:
        if self._fsm.can(DriverAction.PAUSE):
            self._fsm.apply(DriverAction.PAUSE)

    def reset(self) -> None:
        if self._fsm.can(DriverAction.RESET):
            self._fsm.apply(DriverAction.RESET)

    # endregion lifecycle

    # region implementation methods
    # Subclass hooks, intentionally not abstract: load, close, read, write.

    def update(self, event: Any, **kwargs) -> None:
        self.debug(
            msg=Event.Update,
            step=Event.Started,
            event=getattr(event, "name", event),
            kwargs=kwargs,
        )
        if event == Event.Swap and kwargs.get("name") == getattr(self, "connection_name", None):
            # The connection behind this driver was replaced: unload, so the next
            # ensure_live() runs load(), which resolves the swapped connection.
            self.ensure_unloaded()
        self.debug(msg=Event.Update, step=Event.Completed)

    # endregion implementation


class LazyDriverProxy(Wattleflow, IDriver, IObserver, ABC):
    """Defer driver construction (and the connection behind it) until first use."""

    __slots__ = ("_factory", "_driver", "_conn_mgr", "_conn_name")

    def __init__(
        self,
        factory: Callable[[], GenericDriver],
        conn_mgr: Any,
        conn_name: str,
        **kwargs,
    ):
        # A proxy is chatty by nature; quieter than the framework default.
        kwargs.setdefault("level", logging.WARNING)
        super().__init__(**kwargs)

        self._factory = factory  # callable → GenericDriver
        self._driver: GenericDriver | None = None  # stvarni driver
        self._conn_mgr = conn_mgr
        self._conn_name = conn_name

    # region internal

    def _ensure_ready(self) -> GenericDriver:
        conn = self._conn_mgr.get_connection(self._conn_name)

        if not conn.connected:
            conn.request(action=Operation.Connect)

        if self._driver is None:
            self._driver = self._factory()

        self._driver.ensure_live()
        return self._driver

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        return getattr(self._ensure_ready(), name)

    def __repr__(self) -> str:
        state = "initialized" if self._driver else "lazy"
        return f"{self.name}({state}, conn='{self._conn_name}')"

    # endregion internal

    # region API (delegation) ---

    @property
    def driver(self) -> GenericDriver | None:
        """The wrapped driver, or None while still lazy. Never forces a load."""
        return self._driver

    def load(self) -> None:
        self._ensure_ready()

    def metadata(self) -> Any:
        return self._ensure_ready().metadata()

    def read(self, uri: str, **kwargs):
        return self._ensure_ready().read(uri, **kwargs)

    def write(self, uri: str, **kwargs):
        return self._ensure_ready().write(uri, **kwargs)

    def update(self, event: Any, **kwargs) -> None:
        if event == Event.Swap and kwargs.get("name") == self._conn_name:
            self.release()
            return
        if self._driver is not None:
            self._driver.update(event, **kwargs)

    def close(self) -> None:
        if self._driver is None:
            return

        self._driver.ensure_unloaded()

    def reset(self) -> None:
        if self._driver is None:
            return
        self._driver.reset()

    def unload(self) -> None:
        """Alias of close(): unload the driver but keep the proxy reusable."""
        self.close()

    def release(self) -> None:
        """Unload and drop the driver; the next call rebuilds it from scratch."""
        if self._driver is None:
            return

        try:
            self._driver.ensure_unloaded()
        finally:
            self._driver = None

    # endregion API


# --------------------------------------------------------------------------- #
# endregion Drivers                                                           #
# --------------------------------------------------------------------------- #
