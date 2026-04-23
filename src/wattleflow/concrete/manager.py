# Module name: concrete/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from typing import Dict, Union
from wattleflow.core import (
    IObserver,
    IDriver,
    IProcessor,
)
from wattleflow.concrete.logger import AuditLogger
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.connection import Connection, ConnectionAction, ConnectionState
from wattleflow.concrete.processor import ProcessorState, ProcessorAction
from wattleflow.concrete.driver import DriverState, DriverAction
from wattleflow.constants import Event, Operation

# region Exceptions


class ConnectionManagerException(AuditException):
    pass


class DriverManagerException(AuditException):
    pass


class ProcessorManagerException(AuditException):
    pass


# endregion Exceptions


# region ConnectionManager


class ConnectionManager(IObserver, AuditLogger):
    __slots__ = ("_connections",)

    def __init__(self, **kwargs):
        level = kwargs.get("level", 0)
        handler = kwargs.get("handler", None)

        IObserver.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._connections: Dict[str, IObserver] = {}

    def __del__(self):
        errors = []
        for name, conn in list(self._connections.items()):
            try:
                if hasattr(conn, "connected") and conn.connected:
                    conn.request(action=Operation.Disconnect)
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            self.error(msg="__del__", error=f"Errors during cleanup: {errors}")
        else:
            self.debug(msg="__del__", step=Event.Completed.value)

        self._connections.clear()

    def __hash__(self) -> str:
        return abs(hash((self._random)))

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._connections)}]"

    def connect(self, name: str, **kwargs) -> object:
        self.debug(msg=Event.Connect.value, name=name, **kwargs)
        connected = self.operation(name, Operation.Connect, **kwargs)
        self.info(msg=Event.Connect.value, status=connected)
        return self._connections[name]

    def disconnect(self, name: str, **kwargs) -> bool:
        try:
            success = self.operation(name, Operation.Disconnect, **kwargs)
            self.info(msg=Event.Disconnected.value, name=name, **kwargs)
            # return self._connections[name]._connected if success else False
            return success
        except Exception as e:
            self.error(msg="Failed to disconnect!", name=name, error=str(e), **kwargs)
            return False

    def get_connection(self, name: str) -> Connection:
        if name not in self._connections:
            raise ConnectionManagerException(
                caller=self, error=f"Connection '{name}' is not registered!"
            )
        return self._connections[name]

    def register_connection(self, connection: Connection, **kwargs) -> None:
        self.debug(msg=Event.Register.value, connection=connection, **kwargs)

        connection_name: str = kwargs.pop("connection_name", connection.connection_name)

        if connection_name is None:
            raise ConnectionManagerException(
                caller=self,
                error="Connection name is required for registration!",
                connection=connection,
                **kwargs,
            )

        if connection_name in self._connections:
            self.warning(
                msg=Event.Register.value,
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
                msg=Event.Update.value,
                name=name,
                error="Trying to unregister a non-existent connection",
            )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg="operation", step=Event.Started.name, **kwargs)
        if name not in self._connections:
            raise ConnectionManagerException(
                caller=self,
                error=f"Connection '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        self.debug(msg="operation", step=Event.Completing.name, **kwargs)
        return self._connections[name].operation(action, **kwargs)

    def update(self, *args, **kwargs):
        self.debug(msg="update", step=Event.Started.name, **kwargs, note="Not implemented yet.")


# endregion ConnectionManager


# region DriverManager


class DriverManager(IObserver, AuditLogger):
    __slots__ = ("_drivers",)

    def __init__(self, **kwargs):
        level = kwargs.get("level", 0)
        handler = kwargs.get("handler", None)

        IObserver.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self.debug(msg=Event.Constructor.name, step=Event.Started.name)

        self._drivers: Dict[str, IDriver] = {}
        self.debug(msg=Event.Constructor.name, step=Event.Completed.name)

    def __del__(self):
        self.debug(msg="__del__", step=Event.Started.name)
        errors = []
        for name, driver in list(self._drivers.items()):
            try:
                driver.ensure_unloaded()
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            self.error(msg="__del__", error=f"Errors during cleanup: {errors}")
        else:
            self.debug(msg="__del__", step=Event.Completed.value)

        self._drivers.clear()
        self.debug(msg="__del__", step=Event.Completed.name)

    def __hash__(self) -> str:
        return abs(hash(id(self)))

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._drivers)}]"

    def load(self, name: str, **kwargs) -> object:
        self.debug(msg=Event.Load.name, name=name, **kwargs)
        loaded = self.operation(name, Operation.Connect, **kwargs)
        self.debug(msg=Event.Connect.name, added=name, status=loaded)
        return self._drivers[name]

    def get_driver(self, name: str) -> IDriver:
        self.debug(msg="get_driver", step=Event.Starting.name)
        if name not in self._drivers:
            raise DriverManagerException(caller=self, error=f"Driver {name!r} is not found!")
        self.debug(msg="get_driver", step=Event.Completed.name)
        return self._drivers.get(name)

    def register_driver(self, driver: IDriver, **kwargs) -> None:
        self.debug(msg="register_driver", step=Event.Starting.name, driver=driver, **kwargs)
        driver_name = kwargs.pop("name", driver.name)
        if driver_name in self._drivers:
            self.warning(
                msg=Event.Register.value,
                name=driver_name,
                error="Driver is already registered!",
            )
            return
        self._drivers[driver_name] = driver
        self.debug(msg="register_driver", step=Event.Completed.name, registered=driver_name)

    def unregister_driver(self, driver: Union[str, IDriver]) -> None:
        self.debug(msg="register_driver", step=Event.Starting.name, driver=driver)
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
                msg=Event.Update.value,
                name=name,
                error="Trying to unregister a non-existent connection",
            )
        self.debug(msg="register_driver", step=Event.Starting.name, driver=name)

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg="operation", step=Event.Started.name, action=action.name)
        if name not in self._drivers:
            raise DriverManagerException(
                caller=self,
                error=f"Driver '{name}' is not registered.",
                action=action.name,
            )
        result = self._drivers[name].operation(action, **kwargs)
        self.debug(msg="operation", step=Event.Completed.name, action=action.name, result=result)
        return result

    def update(self, *args, **kwargs):
        self.debug(msg="update", step=Event.Started.name)
        self.warning(msg="update", error="Not implemented yet.")
        self.debug(msg="update", step=Event.Completed.name)


# endregion DriverManager


# region ProcessorManager


class ProcessorManager(IObserver, AuditLogger):
    __slots__ = ("_processors",)

    def __init__(self, **kwargs):
        level = kwargs.get("level", 0)
        handler = kwargs.get("handler", None)

        IObserver.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._processorss: Dict[str, IProcessor] = {}

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.name,
            name=self,
        )

    def __del__(self):
        errors = []
        for processor in self._processorss:
            try:
                self.unregister_processor(processor)
            except Exception as e:
                errors.append(f"{processor}: {e}")

        if errors:
            self.error(msg="__del__", error=f"Errors during cleanup: {errors}")
        else:
            self.debug(msg="__del__", step=Event.Completed.value)

        self._processorss.clear()

    def __hash__(self) -> str:
        return abs(hash(id(self)))

    def __repr__(self) -> str:
        return f"{self.name}-{hash(id(self))}:[{len(self._processorss)}]"

    @property
    def all(self) -> Dict[str, IProcessor]:
        return self._processorss

    def load(self, name: str, **kwargs) -> IProcessor:
        self.debug(msg=Event.Connect.value, name=name, **kwargs)
        status = self.operation(name, Operation.Connect, **kwargs)
        self.info(msg=Event.Connect.value, status=status)
        return self._processorss[name]

    def get_processor(self, name: str) -> IProcessor:
        self.debug(msg="get_processor", step=Event.Starting.name)
        if name not in self._processorss:
            raise ProcessorManagerException(caller=self, error=f"Processor {name!r} is not found!")
        self.debug(msg="get_processor", step=Event.Completed.name)
        return self._processorss.get(name)

    def register_processor(self, processor: IProcessor, **kwargs) -> None:
        self.debug(msg="register_processor", processor=processor, **kwargs)
        processor_name = kwargs.get("name", processor.name)
        if processor_name in self._processorss:
            self.warning(
                msg=Event.Register.value,
                name=processor_name,
                class_name=processor.class_name(),
                error="Processor is already registered!",
            )
            return
        self._processorss[processor_name] = processor
        self.debug(msg="register_processor", added=processor)

    def unregister_processor(self, processor: Union[str, IProcessor]) -> None:
        if isinstance(processor, IProcessor):
            name = processor.name
        else:
            name = processor

        # if name in self._processors:
        #     self._processors[name].update(
        #         event=ProcessorState.UNLOADING,
        #         caller=self,
        #         msg="unregister_processor",
        #     )
        #     self._processorss[name].update(event=ProcessorState.UNLOADING)
        # else:
        #     self.warning(
        #         msg=Event.Update.value,
        #         name=name,
        #         error="Trying to unregister a non-existent processor",
        #     )

    def operation(self, name: str, action: Operation, **kwargs) -> bool:
        self.debug(msg="operation", step=Event.Started.name, **kwargs)
        if name not in self._processors:
            raise ProcessorManagerException(
                caller=self,
                error=f"Processor '{name}' is not registered.",
                action=action.name,
                **kwargs,
            )

        if not action == Operation.Start:
            self.warning(
                msg="operation",
                error="Action is not allowed!",
                action=action,
            )
            return False

        self.debug(msg="operation", step=Event.Completing.name, **kwargs)
        return self._processors[name].operation(action, **kwargs)

    def update(self, **kwargs):
        self.debug(msg="update", **kwargs)


# endregion ProcessorManager
