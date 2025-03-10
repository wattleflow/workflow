# Module Name: core/concrete/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete manager classes.
"""
1. Connection Management
    - Stores registered connections in _connections: Dict[str, IObserver].
    - Supports registering (register_connection()) and unregistering
      (unregister_connection()) connections.

2. Connection Lookup & Lifecycle
    - get_connection(name): Retrieves a connection by name.
    - operation(name, action): Executes an operation (Connect, Disconnect, etc.) on a connection.
    - connect(name): Initiates a connection.
    - disconnect(name): Terminates a connection.

3. Auditing & Logging
    - Calls self.audit(event=Event.Registering, name=name) during registration.
    - Uses _strategy_audit.generate() for event logging.

4. Observer Pattern (update())
    - Defines update(*args, **kwargs), but currently does nothing.
    - Expected to allow the manager to react to external events in future extensions.
"""

from typing import Dict
from wattleflow.core import IObserver, IStrategy
from wattleflow.concrete.attribute import Attribute
from wattleflow.concrete.connection import (
    GenericConnection,
    Operation,
)
from wattleflow.constants.enums import Event


class ConnectionManager(IObserver, Attribute):
    def __init__(self, strategy_audit: IStrategy):
        super().__init__()
        self.evaluate(strategy_audit, IStrategy)
        self._strategy_audit = strategy_audit
        self._connections: Dict[str, IObserver] = {}

    def audit(self, event, **kwargs):
        self._strategy_audit.generate(owner=self, caller=self, event=event, **kwargs)

    def connect(self, name: str) -> object:
        self.operation(name, Operation.Connect)
        return self._connections[name]

    def disconnect(self, name: str) -> bool:
        try:
            success = self.operation(name, Operation.Disconnect)
            return self._connections[name]._connected if success else False
        except Exception as e:
            print(f"[ERROR] Failed to disconnect {name}: {e}")
            return False

    def get_connection(self, name: str) -> GenericConnection:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not registered.")
        return self._connections[name]

    def register_connection(self, name: str, connection: GenericConnection) -> None:
        self.audit(event=Event.Registering, name=name)

        if name in self._connections:
            print(
                f"[WARNING] Connection '{name}' is already registered. Skipping registration."
            )
            return

        self._connections[name] = connection

    def unregister_connection(self, name: str) -> None:
        if name in self._connections:
            del self._connections[name]
        else:
            print(
                f"[WARNING] Attempted to unregister a non-existent connection: {name}"
            )

    def operation(self, name: str, action: Operation) -> bool:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not registered.")
        return self._connections[name].operation(action)

    def update(self, *args, **kwargs):
        pass
