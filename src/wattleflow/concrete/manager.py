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
            self.error(msg=Event.Delete.name, step=Event.Failed.name, reason=reason)
        else:
            self.debug(msg=Event.Delete.name, step=Event.Completed.name)

        self._connections.clear()

    def __hash__(self) -> str:
        return abs(hash((self._random)))

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._connections)}]"

    def __len__(self) -> int:
        return len(self._connections)

    def connect(self, name: str, **kwargs) -> object:
        self.debug(msg=Event.Connect.name, name=name, kwargs=kwargs)
        connected = self.operation(name, Operation.Connect, **kwargs)
        # v0.0.1.10 (DR-WFL-018 t.5): opening a connection is a step in someone
        # else's unit of work, so the owner of that unit keeps the INFO.
        self.debug(msg=Event.Connect.name, step=Event.Completed.name, status=connected)
        return self._connections[name]

    def disconnect(self, name: str, **kwargs) -> bool:
        try:
            success = self.operation(name, Operation.Disconnect, **kwargs)
            self.debug(
                msg=Event.Disconnected.name,
                step=Event.Completed.name,
                name=name,
                kwargs=kwargs,
            )
            return success
        except Exception as e:
            self.error(
                msg=Event.Disconnect.name,
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
        self.debug(msg=Event.Register.name, connection=connection, kwargs=kwargs)

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
                msg=Event.Register.name,
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
                msg=Event.Update.name,
                name=name,
                error="Trying to unregister a non-existent connection",
            )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation.name, step=Event.Started.name, kwargs=kwargs)
        if name not in self._connections:
            raise ConnectionManagerException(
                caller=self,
                error=f"Connection '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        self.debug(msg=Event.Operation.name, step=Event.Completing.name, kwargs=kwargs)
        return self._connections[name].operation(action, **kwargs)

    def update(self, *args, **kwargs):
        self.debug(
            msg=Event.Update.name,
            step=Event.Started.name,
            kwargs=kwargs,
            note="Not implemented yet.",
        )


class DriverManager(Wattleflow, IObserver):
    __slots__ = ("_drivers",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.debug(msg=Event.Constructor.name, step=Event.Started.name)

        self._drivers: dict[str, IDriver] = {}
        self.debug(msg=Event.Constructor.name, step=Event.Completed.name)

    def __del__(self):
        self.debug(msg=Event.Destructor.name, step=Event.Started.name)
        errors = []
        for name, driver in list(self._drivers.items()):
            try:
                driver.ensure_unloaded()
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            reason = "%s.__del__ error: %s" % (self.__class__.__name__, errors)
            self.error(msg=Event.Delete.name, step=Event.Failed.name, reason=reason)
        else:
            self.debug(msg=Event.Delete.name, step=Event.Completed.name)

        self._drivers.clear()
        self.debug(msg=Event.Delete.name, step=Event.Completed.name)

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
        self.debug(msg=Event.Load.name, name=name, kwargs=kwargs)
        loaded = self.operation(name, Operation.Connect, **kwargs)
        self.debug(msg=Event.Connect.name, added=name, status=loaded)
        return self._drivers[name]

    def get_driver(self, name: str) -> IDriver:
        self.debug(msg=Event.Get.name, target="driver", step=Event.Starting.name)
        if name not in self._drivers:
            raise DriverManagerException(caller=self, error=f"Driver {name!r} is not found!")
        self.debug(msg=Event.Get.name, target="driver", step=Event.Completed.name)
        return self._drivers.get(name)

    def register_driver(self, driver: IDriver, **kwargs) -> None:
        self.debug(
            msg=Event.Register.name,
            target="driver",
            step=Event.Starting.name,
            driver=driver,
            kwargs=kwargs,
        )
        driver_name = kwargs.pop("name", driver.name)
        if driver_name in self._drivers:
            self.warning(
                msg=Event.Register.name,
                name=driver_name,
                error="Driver is already registered!",
            )
            return
        self._drivers[driver_name] = driver
        self.debug(
            msg=Event.Register.name,
            target="driver",
            step=Event.Completed.name,
            registered=driver_name,
        )

    def unregister_driver(self, driver: str | IDriver) -> None:
        self.debug(
            msg=Event.Register.name,
            target="driver",
            step=Event.Starting.name,
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
                msg=Event.Update.name,
                name=name,
                error="Trying to unregister a non-existent connection",
            )
        self.debug(
            msg=Event.Register.name,
            target="driver",
            step=Event.Starting.name,
            driver=name,
        )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation.name, step=Event.Started.name, action=action.name)
        if name not in self._drivers:
            raise DriverManagerException(
                caller=self,
                error=f"Driver '{name}' is not registered.",
                action=action.name,
            )
        result = self._drivers[name].operation(action, **kwargs)
        self.debug(
            msg=Event.Operation.name,
            step=Event.Completed.name,
            action=action.name,
            result=result,
        )
        return result

    def update(self, *args, **kwargs):
        self.debug(msg=Event.Update.name, step=Event.Started.name)
        self.warning(msg=Event.Update.name, error="Not implemented yet.")
        self.debug(msg=Event.Update.name, step=Event.Completed.name)


class ProcessorManager(Wattleflow, IObserver):
    __slots__ = ("_processors",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processors: dict[str, IProcessor] = {}

    def __del__(self):
        self.debug(msg=Event.Delete.name, step=Event.Starting.name)
        errors = []
        while self._processors:
            name = next(iter(self._processors))
            try:
                self.unregister_processor(name)
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue

        if errors:
            self.error(msg=Event.Destructor.name, error=f"Errors during cleanup: {errors}")
        else:
            self.debug(msg=Event.Destructor.name, step=Event.Completed.name)

        self._processors.clear()
        self.debug(msg=Event.Delete.name, step=Event.Completed.name)

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
        self.debug(msg=Event.Start.name, name=name, kwargs=kwargs)
        status = self.operation(name, Operation.Start, **kwargs)
        self.info(msg=Event.Start.name, status=status)
        return self._processors[name]

    def get_processor(self, name: str) -> IProcessor:
        self.debug(msg=Event.Get.name, target="processor", step=Event.Starting.name)
        if name not in self._processors:
            raise ProcessorManagerException(caller=self, error=f"Processor {name!r} is not found!")
        self.debug(msg=Event.Get.name, target="processor", step=Event.Completed.name)
        return self._processors.get(name)

    def register_processor(self, processor: IProcessor, **kwargs) -> None:
        self.debug(
            msg=Event.Register.name,
            step=Event.Starting.name,
            processor=processor,
            kwargs=kwargs,
        )
        processor_name = kwargs.get("name", processor.name)
        if processor_name in self._processors:
            self.warning(
                msg=Event.Register.name,
                name=processor_name,
                class_name=processor.__class__.__name__,
                error="Processor is already registered!",
            )
            return
        self._processors[processor_name] = processor
        self.debug(msg=Event.Register.name, step=Event.Completed.name)

    def unregister_processor(self, processor: str | IProcessor) -> None:
        self.debug(msg=Event.Unregister.name, step=Event.Starting.name, proc=processor)
        name = processor.name if isinstance(processor, IProcessor) else processor
        if name in self._processors:
            p = self._processors.pop(name)
            del p
        self.debug(msg=Event.Unregister.name, step=Event.Completed.name)

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg=Event.Operation.name, step=Event.Started.name, kwargs=kwargs)
        if name not in self._processors:
            raise ProcessorManagerException(
                caller=self,
                error=f"Processor '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        if not action == Operation.Start:
            self.warning(
                msg=Event.Operation.name,
                error="Action is not allowed!",
                action=action,
            )
            return False

        self.debug(msg=Event.Operation.name, step=Event.Completing.name, kwargs=kwargs)
        return self._processors[name].operation(action, **kwargs)

    def update(self, **kwargs):
        self.debug(msg=Event.Update.name, step=Event.Starting.name)
        self.warning(msg=Event.Update.name, error="NOT IMPLEMENTED")
        self.debug(msg=Event.Update.name, step=Event.Completed.name)


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
