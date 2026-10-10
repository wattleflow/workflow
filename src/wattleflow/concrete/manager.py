# Module name: concrete/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "ConnectionManager",
    "DriverManager",
    "ProcessorManager",
]

from typing import Any
from wattleflow.core import (
    IObserver,
    IDriver,
    IProcessor,
)
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import ManagerException
from wattleflow.concrete.connection import Connection
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class ConnectionManager(Wattleflow, IObserver):
    __slots__ = ("_connections",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connections: dict[str, IObserver] = {}

    @staticmethod
    def _release(conn: object) -> None:
        """What a connection owes when it leaves the manager: a disconnect, if it is connected."""
        if hasattr(conn, "connected") and conn.connected:
            conn.request(action=Operation.Disconnect)

    def __del__(self):
        # A construction that failed before `_connections` was set has nothing to release.
        try:
            object.__getattribute__(self, "_connections")
        except AttributeError:
            return
        errors = []
        for name, conn in list(self._connections.items()):
            try:
                self._release(conn)
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            reason = "%s.__del__ errors: %s" % (self.__class__.__name__, errors)
            self.error(msg=Event.Delete, step=Event.Failed, reason=reason)
        else:
            self.debug(msg=Event.Delete, step=Event.Completed)

        self._connections.clear()

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._connections)}]"

    def __len__(self) -> int:
        return len(self._connections)

    def connect(self, name: str, **kwargs) -> object:
        return self.operation(name, Operation.Connect, **kwargs)

    def disconnect(self, name: str, **kwargs) -> bool:
        return self.operation(name, Operation.Disconnect, **kwargs)

    def get_connection(self, name: str) -> Connection:
        if name not in self._connections:
            error = (
                "%s.get_connection error: Connection name not registered!"
                % self.__class__.__name__
            )
            raise ManagerException(
                caller=self,
                name=name,
                error=error,
            )
        return self._connections[name]

    def register_connection(self, connection: Connection, **kwargs) -> None:
        self.debug(msg=Event.Register, connection=connection, kwargs=kwargs)

        connection_name: str | None = kwargs.pop("connection_name", None) or getattr(
            connection, "connection_name", None
        )

        if connection_name is None:
            error = (
                "%s.register_connection error: Connection name is required!"
                % self.__class__.__name__
            )
            raise ManagerException(
                caller=self,
                connection=connection,
                error=error,
            )

        if connection_name in self._connections:
            self.warning(
                msg=Event.Register,
                connection_name=connection_name,
                error="Connection is already registered!",
            )
            return

        self._connections[connection_name] = connection

    def unregister_connection(self, name: str) -> None:
        """Remove the connection and release it as `__del__` would: disconnect if connected.
        A failing disconnect is reported, and the entry is gone either way."""
        if name in self._connections:
            conn = self._connections.pop(name)
            try:
                self._release(conn)
            except Exception as e:
                self.error(
                    msg=Event.Disconnect,
                    reason="Failed to disconnect on unregister!",
                    name=name,
                    error=str(e),
                )
        else:
            self.warning(
                msg=Event.Update,
                name=name,
                error="Trying to unregister a non-existent connection",
            )

    def hot_swap(self, name: str, new_connection: Connection) -> None:
        """Replace the registered connection `name` without losing its observers.

        The new connection is connected first; if that fails the old one stays
        registered and active. Observers move to the new connection and are
        notified with `Event.Swap`; the old connection is disconnected last.
        """
        self.debug(msg=Event.Swap, step=Event.Started, name=name)
        if name not in self._connections:
            raise ManagerException(
                caller=self, error=f"Connection '{name}' is not registered.", name=name
            )

        old_connection = self._connections[name]
        try:
            connected = new_connection.operation(Operation.Connect)
        except Exception as e:
            self.debug(msg=Event.Swap, step=Event.Failed, name=name, error=str(e))
            raise ManagerException(
                caller=self,
                error=f"Hot swap failed, the old connection '{name}' stays active: {e}",
                name=name,
            ) from e
        if not connected:
            self.debug(msg=Event.Swap, step=Event.Failed, name=name)
            raise ManagerException(
                caller=self,
                error=f"Hot swap failed, the old connection '{name}' stays active: new connection did not connect.",
                name=name,
            )

        old_connection.transfer_observers(new_connection)
        self._connections[name] = new_connection
        new_connection.notify(Event.Swap, name=name, connection=new_connection)

        try:
            old_connection.operation(Operation.Disconnect)
        except Exception as e:
            self.warning(
                msg=Event.Swap,
                name=name,
                error=f"Old connection was not closed properly: {e}",
            )
        self.debug(msg=Event.Swap, step=Event.Completed, name=name)

    def operation(self, name: str, action: Operation, **kwargs) -> Any:
        self.debug(msg=Event.Operation, step=Event.Started, action=action.name)
        if name not in self._connections:
            raise ManagerException(
                caller=self,
                error=f"Connection '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        self.debug(msg=Event.Operation, step=Event.Completing, action=action.name)
        return self._connections[name].operation(action, **kwargs)

    def update(self, *args, **kwargs):
        # The manager observes nothing yet: the hook exists for the IObserver contract.
        self.debug(msg=Event.Update, kwargs=kwargs, note="Not implemented yet.")


class DriverManager(Wattleflow, IObserver):
    __slots__ = ("_drivers",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.debug(msg=Event.Constructor, step=Event.Started)

        self._drivers: dict[str, IDriver] = {}
        self.debug(msg=Event.Constructor, step=Event.Completed)

    def __del__(self):
        try:
            object.__getattribute__(self, "_drivers")
        except AttributeError:
            return
        self.debug(msg=Event.Destructor, step=Event.Started)
        errors = []
        for name, driver in list(self._drivers.items()):
            try:
                driver.ensure_unloaded()
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            reason = "%s.__del__ error: %s" % (self.__class__.__name__, errors)
            self.error(msg=Event.Delete, step=Event.Failed, reason=reason)

        self._drivers.clear()
        if not errors:
            self.debug(msg=Event.Delete, step=Event.Completed)

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._drivers)}]"

    def __len__(self) -> int:
        return len(self._drivers)

    @property
    def all(self) -> dict[str, IDriver]:
        """Every registered driver by name — as `ProcessorManager.all` does, so
        a caller that reports over managers does not need a special case."""
        return self._drivers

    def load(self, name: str, **kwargs) -> object:
        self.debug(msg=Event.Load, name=name, kwargs=kwargs)
        loaded = self.operation(name, Operation.Connect, **kwargs)
        self.debug(msg=Event.Connect, added=name, status=loaded)
        return self._drivers[name]

    def get_driver(self, name: str) -> IDriver:
        self.debug(msg=Event.Get, target="driver", step=Event.Starting)
        if name not in self._drivers:
            raise ManagerException(caller=self, error=f"Driver {name!r} is not found!")
        self.debug(msg=Event.Get, target="driver", step=Event.Completed)
        return self._drivers.get(name)

    def register_driver(self, driver: IDriver, **kwargs) -> None:
        self.debug(
            msg=Event.Register,
            target="driver",
            step=Event.Starting,
            driver=driver,
            kwargs=kwargs,
        )
        driver_name = kwargs.pop("name", driver.name)
        if driver_name in self._drivers:
            self.warning(
                msg=Event.Register,
                name=driver_name,
                error="Driver is already registered!",
            )
            return
        self._drivers[driver_name] = driver
        self.debug(
            msg=Event.Register,
            target="driver",
            step=Event.Completed,
            registered=driver_name,
        )

    def unregister_driver(self, driver: str | IDriver) -> None:
        """Remove the driver and release it as `__del__` would: unload it. A failing unload is
        reported, and the entry is gone either way."""
        self.debug(
            msg=Event.Unregister,
            target="driver",
            step=Event.Starting,
            driver=driver,
        )
        name = driver.name if isinstance(driver, IDriver) else driver
        if name in self._drivers:
            registered = self._drivers.pop(name)
            try:
                registered.ensure_unloaded()
            except Exception as e:
                self.error(
                    msg=Event.Unregister,
                    step=Event.Failed,
                    name=name,
                    error=str(e),
                )
        else:
            self.warning(
                msg=Event.Unregister,
                name=name,
                error="Trying to unregister a driver that is not registered",
            )
        self.debug(
            msg=Event.Unregister,
            target="driver",
            step=Event.Completed,
            driver=name,
        )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation, step=Event.Started, action=action.name)
        if name not in self._drivers:
            raise ManagerException(
                caller=self,
                error=f"Driver '{name}' is not registered.",
                action=action.name,
            )
        result = self._drivers[name].operation(action, **kwargs)
        self.debug(
            msg=Event.Operation,
            step=Event.Completed,
            action=action.name,
            result=result,
        )
        return result

    def update(self, *args, **kwargs):
        # The manager observes nothing yet: the hook exists for the IObserver contract.
        self.debug(msg=Event.Update, kwargs=kwargs, note="Not implemented yet.")


class ProcessorManager(Wattleflow, IObserver):
    __slots__ = ("_processors",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processors: dict[str, IProcessor] = {}

    def __del__(self):
        try:
            object.__getattribute__(self, "_processors")
        except AttributeError:
            return
        self.debug(msg=Event.Delete, step=Event.Starting)
        errors = []
        while self._processors:
            name = next(iter(self._processors))
            try:
                self.unregister_processor(name)
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue

        if errors:
            self.error(msg=Event.Destructor, error=f"Errors during cleanup: {errors}")
        else:
            self.debug(msg=Event.Destructor, step=Event.Completed)

        self._processors.clear()
        self.debug(msg=Event.Delete, step=Event.Completed)

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._processors)}]"

    def __len__(self) -> int:
        return len(self._processors)

    @property
    def all(self) -> dict[str, IProcessor]:
        return self._processors

    def load(self, name: str, **kwargs) -> IProcessor:
        self.debug(msg=Event.Start, name=name, kwargs=kwargs)
        status = self.operation(name, Operation.Start, **kwargs)
        self.info(msg=Event.Start, status=status)
        return self._processors[name]

    def get_processor(self, name: str) -> IProcessor:
        self.debug(msg=Event.Get, target="processor", step=Event.Starting)
        if name not in self._processors:
            raise ManagerException(caller=self, error=f"Processor {name!r} is not found!")
        self.debug(msg=Event.Get, target="processor", step=Event.Completed)
        return self._processors.get(name)

    def register_processor(self, processor: IProcessor, **kwargs) -> None:
        self.debug(
            msg=Event.Register,
            step=Event.Starting,
            processor=processor,
            kwargs=kwargs,
        )
        processor_name = kwargs.get("name", processor.name)
        if processor_name in self._processors:
            self.warning(
                msg=Event.Register,
                name=processor_name,
                class_name=processor.__class__.__name__,
                error="Processor is already registered!",
            )
            return
        self._processors[processor_name] = processor
        self.debug(msg=Event.Register, step=Event.Completed)

    def unregister_processor(self, processor: str | IProcessor) -> None:
        self.debug(msg=Event.Unregister, step=Event.Starting, proc=processor)
        name = processor.name if isinstance(processor, IProcessor) else processor
        if name in self._processors:
            p = self._processors.pop(name)
            del p
        self.debug(msg=Event.Unregister, step=Event.Completed)

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation, step=Event.Started, kwargs=kwargs)
        if name not in self._processors:
            raise ManagerException(
                caller=self,
                error=f"Processor '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        if not action == Operation.Start:
            self.warning(
                msg=Event.Operation,
                error="Action is not allowed!",
                action=action,
            )
            return False

        self.debug(msg=Event.Operation, step=Event.Completing, kwargs=kwargs)
        return self._processors[name].operation(action, **kwargs)

    def update(self, *args, **kwargs):
        # The manager observes nothing yet: the hook exists for the IObserver contract.
        self.debug(msg=Event.Update, kwargs=kwargs, note="Not implemented yet.")


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
