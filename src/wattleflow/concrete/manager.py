# Module name: manager.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from logging import Handler
from typing import Dict, Optional
from wattleflow.core import IObserver
from wattleflow.concrete import (
    AuditLogger,
    GenericConnection,
)
from wattleflow.constants import Event, Operation


class ConnectionManager(IObserver, AuditLogger):
    def __init__(self, level: int, handler: Optional[Handler] = None):
        IObserver.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self.debug(
            msg=Event.Constructor.value,
            level=level,
            handler=handler,
        )

        self._connections: Dict[str, IObserver] = {}

    def connect(self, name: str) -> object:
        self.debug(msg=Event.Connect.value, name=name)
        self.operation(name, Operation.Connect)
        self.info(
            msg=Event.Connect.value,
            status=Event.Connected.value,
            name=name,
        )
        return self._connections[name]

    def disconnect(self, name: str) -> bool:
        try:
            success = self.operation(name, Operation.Disconnect)
            self.info(msg=Event.Disconnected.value, name=name)
            # return self._connections[name]._connected if success else False
            return success
        except Exception as e:
            self.error(msg="Failed to disconnect!", name=name, error=str(e))
            return False

    def get_connection(self, name: str) -> GenericConnection:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not registered.")
        return self._connections[name]

    def register_connection(self, name: str, connection: GenericConnection) -> None:
        self.debug(
            msg=Event.Register.value,
            name=name,
            connection=connection,
        )

        if name in self._connections:
            self.warning(
                msg=Event.Register.value,
                name=name,
                error="Connection is already registered!",
            )
            return

        self._connections[name] = connection

    def unregister_connection(self, name: str) -> None:
        if name in self._connections:
            del self._connections[name]
        else:
            self.warning(
                msg=Event.Update.value,
                name=name,
                error="Trying to unregister a non-existent connection",
            )

    def operation(self, name: str, action: Operation) -> bool:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not registered.")
        return self._connections[name].operation(action)

    def update(self, *args, **kwargs):
        pass

    def __repr__(self) -> str:
        return f"{self.name}:{len(self._connections)}"
