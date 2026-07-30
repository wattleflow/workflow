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
from wattleflow.core.behavioural import IObserver
from wattleflow.core.transactional import IDriver
from wattleflow.concrete.wattleflow import Wattleflow
from wattleflow.concrete.exception import DriverException
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.constants.enums import Event
from wattleflow.decorators.preset import PresetDecorator


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Metadata                                                             #
# --------------------------------------------------------------------------- #


@dataclass
class DriverMetadata:
    name: str
    version: str
    protocol: str
    capabilities: list  # ["read", "write", "stream"]


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
TRANSITIONS = {
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


class GenericDriver(Wattleflow, IDriver, IObserver, ABC):
    __slots__ = ("_fsm", "_preset")

    def __init__(self, **kwargs):
        level = kwargs.pop("level", logging.WARNING)
        handler = kwargs.pop("handler", None)
        super().__init__(level=level, handler=handler)

        self._fsm: StateMachine = StateMachine(TRANSITIONS, DriverState.PENDING, label="DriverFSM")
        self._preset = PresetDecorator(parent=self, **kwargs)

    def __del__(self):
        self.debug(msg="__del__", step=Event.Started.name)
        self.ensure_unloaded()
        self.debug(msg="__del__", step=Event.Completed.name)

    def __getattr__(self, name: str) -> Any:
        all_slots: set = set()
        for cls in type(self).__mro__:
            all_slots.update(getattr(cls, "__slots__", ()))

        if name in all_slots:
            return object.__getattribute__(self, name)

        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        name = self.name or self.__class__.__name__
        state = self._fsm.state.name
        return f"{name}(state={state})"

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
            raise DriverException(caller=self, error=f"Cannot load from state {self._fsm.state}")

        self._fsm.apply(DriverAction.LOAD)

        try:
            self.load()
            self._fsm.apply(DriverAction.LOAD_OK)
        except Exception:
            self._fsm.apply(DriverAction.LOAD_FAIL)
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
        except Exception:
            self._fsm.apply(DriverAction.UNLOAD_FAIL)
            raise

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
        self.debug(msg="update", step=Event.Started.name, event=event.name, **kwargs)
        self.debug(msg="update", step=Event.Completed.name)

    # endregion implemention


class LazyDriverProxy(Wattleflow, IDriver, IObserver):
    __slots__ = ("_factory", "_driver", "_conn_mgr", "_conn_name")

    def __init__(self, factory, conn_mgr, conn_name: str, **kwargs):
        level = kwargs.pop("level", logging.WARNING)
        handler = kwargs.pop("handler", None)

        super().__init__(level=level, handler=handler)

        self._factory = factory  # callable → GenericDriver
        self._driver = None  # stvarni driver
        self._conn_mgr = conn_mgr
        self._conn_name = conn_name

    # region internal

    def _ensure_ready(self):
        conn = self._conn_mgr.get(self._conn_name)

        if not conn.connected:
            conn.request("connect")

        if self._driver is None:
            self._driver = self._factory()

        self._driver.ensure_live()

    def __del__(self) -> None:
        self.release()

    def __getattr__(self, name: str) -> Any:
        all_slots: set = set()
        for cls in type(self).__mro__:
            all_slots.update(getattr(cls, "__slots__", ()))

        if name in all_slots:
            return object.__getattribute__(self, name)

        self._ensure_ready()
        driver = object.__getattribute__(self, "_driver")
        return getattr(driver, name)

    def __repr__(self) -> str:
        state = "initialized" if self._driver else "lazy"
        return f"{self.__class__.__name__}({state}, conn='{self._conn_name}')"

    # def __getattr__(self, name: str):
    #     if name.startswith("_"):
    #         return object.__getattribute__(self, name)

    #     self._ensure_ready()
    #     return getattr(self._driver, name)

    # endregion internal

    # region API (delegation) ---

    def read(self, uri: str, **kwargs):
        self._ensure_ready()
        return self._driver.read(uri, **kwargs)

    def write(self, uri: str, **kwargs):
        self._ensure_ready()
        return self._driver.write(uri, **kwargs)

    def close(self) -> None:
        if self._driver is None:
            return

        self._driver.ensure_unloaded()

    def reset(self) -> None:
        if self._driver is None:
            return
        self._driver.reset()

    def unload(self):
        if self._driver is None:
            return

        self._driver.ensure_unloaded()

    def release(self):
        if self._driver:
            self._driver.ensure_unloaded()
            self._driver = None

    # endregion API


# --------------------------------------------------------------------------- #
# endregion Drivers                                                           #
# --------------------------------------------------------------------------- #
