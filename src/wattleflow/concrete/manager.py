# Module name: concrete/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from wattleflow.core import (
    IObserver,
    IDriver,
    IProcessor,
)
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.connection import Connection
from wattleflow.concrete.driver import DriverState
from wattleflow.enums.event import Event
from wattleflow.enums.operation import Operation


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class ConnectionManagerException(AuditException):
    pass


class DriverManagerException(AuditException):
    pass


class ProcessorManagerException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class ConnectionManager(Wattleflow, IObserver):
    __slots__ = ("_connections",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connections: dict[str, IObserver] = {}

    def __del__(self):
        errors = []
        for name, conn in list(self._connections.items()):
            try:
                if hasattr(conn, "connected") and conn.connected:
                    conn.request(action=Operation.Disconnect)
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            reason = "%s.__del__ errors: %s" % (self.__class__.__name__, errors)
            self.error(msg=Event.Delete, step=Event.Failed, reason=reason)
        else:
            self.debug(msg=Event.Delete, step=Event.Completed)

        self._connections.clear()

    def __hash__(self) -> str:
        return abs(hash((self._random)))

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._connections)}]"

    def __len__(self) -> int:
        return len(self._connections)

    def connect(self, name: str, **kwargs) -> object:
        self.debug(msg=Event.Connect, name=name, kwargs=kwargs)
        connected = self.operation(name, Operation.Connect, **kwargs)
        # v0.0.1.10 (DR-WFL-018 t.5): opening a connection is a step in someone
        # else's unit of work, so the owner of that unit keeps the INFO.
        self.debug(msg=Event.Connect, step=Event.Completed, status=connected)
        return self._connections[name]

    def disconnect(self, name: str, **kwargs) -> bool:
        try:
            success = self.operation(name, Operation.Disconnect, **kwargs)
            self.debug(
                msg=Event.Disconnected,
                step=Event.Completed,
                name=name,
                kwargs=kwargs,
            )
            return success
        except Exception as e:
            self.error(
                msg=Event.Disconnect,
                reason="Failed to disconnect!",
                name=name,
                error=str(e),
            )
            return False

    def get_connection(self, name: str) -> Connection:
        if name not in self._connections:
            error = (
                "%s.get_connection error: Connection name not registered!" % self.__class__.__name__
            )
            raise ConnectionManagerException(
                caller=self,
                name=name,
                error=error,
            )
        return self._connections[name]

    def register_connection(self, connection: Connection, **kwargs) -> None:
        self.debug(msg=Event.Register, connection=connection, kwargs=kwargs)

        connection_name: str = kwargs.pop("connection_name", connection.connection_name)

        if connection_name is None:
            error = (
                "%s.register_connection error: Connection name is required!"
                % self.__class__.__name__
            )
            raise ConnectionManagerException(
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
        if name in self._connections:
            del self._connections[name]
        else:
            self.warning(
                msg=Event.Update,
                name=name,
                error="Trying to unregister a non-existent connection",
            )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation, step=Event.Started, kwargs=kwargs)
        if name not in self._connections:
            raise ConnectionManagerException(
                caller=self,
                error=f"Connection '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        self.debug(msg=Event.Operation, step=Event.Completing, kwargs=kwargs)
        return self._connections[name].operation(action, **kwargs)

    def update(self, *args, **kwargs):
        self.debug(
            msg=Event.Update,
            step=Event.Started,
            kwargs=kwargs,
            note="Not implemented yet.",
        )


class DriverManager(Wattleflow, IObserver):
    __slots__ = ("_drivers",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.debug(msg=Event.Constructor, step=Event.Started)

        self._drivers: dict[str, IDriver] = {}
        self.debug(msg=Event.Constructor, step=Event.Completed)

    def __del__(self):
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
        else:
            self.debug(msg=Event.Delete, step=Event.Completed)

        self._drivers.clear()
        self.debug(msg=Event.Delete, step=Event.Completed)

    def __hash__(self) -> str:
        return abs(hash(id(self)))

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
            raise DriverManagerException(caller=self, error=f"Driver {name!r} is not found!")
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
        self.debug(
            msg=Event.Register,
            target="driver",
            step=Event.Starting,
            driver=driver,
        )
        name = driver.name if isinstance(driver, IDriver) else driver
        if name in self._drivers:
            self._drivers[name].update(
                event=DriverState.UNLOADING,
                caller=self,
                msg="unregister_driver",
            )
            self._drivers[name].update(event=DriverState.UNLOADING)
        else:
            self.warning(
                msg=Event.Update,
                name=name,
                error="Trying to unregister a non-existent connection",
            )
        self.debug(
            msg=Event.Register,
            target="driver",
            step=Event.Starting,
            driver=name,
        )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation, step=Event.Started, action=action.name)
        if name not in self._drivers:
            raise DriverManagerException(
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
        self.debug(msg=Event.Update, step=Event.Started)
        self.warning(msg=Event.Update, error="Not implemented yet.")
        self.debug(msg=Event.Update, step=Event.Completed)


class ProcessorManager(Wattleflow, IObserver):
    __slots__ = ("_processors",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processors: dict[str, IProcessor] = {}

    def __del__(self):
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

    def __hash__(self) -> str:
        return abs(hash(id(self)))

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
            raise ProcessorManagerException(caller=self, error=f"Processor {name!r} is not found!")
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
            raise ProcessorManagerException(
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

    def update(self, **kwargs):
        self.debug(msg=Event.Update, step=Event.Starting)
        self.warning(msg=Event.Update, error="NOT IMPLEMENTED")
        self.debug(msg=Event.Update, step=Event.Completed)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


__all__ = [
    "ConnectionManager",
    "ConnectionManagerException",
    "DriverManager",
    "DriverManagerException",
    "ProcessorManager",
    "ProcessorManagerException",
]
