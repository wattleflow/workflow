# Module Name: core/concrete/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete manager classes.

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
        self._strategy_audit.write(caller=self, event=event, **kwargs)

    def register_connection(self, name: str, connection: GenericConnection) -> None:
        self.audit(event=Event.Registering, name=name)
        if not (name in self._connections):
            self._connections[name] = connection

    def unregister_connection(self, name: str) -> None:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not found.")
        del self._connections[name]

    def get_connection(self, name: str) -> GenericConnection:
        if name not in self._connections:
            raise Exception(f"Connection '{name}' is not regiestered.")
        return self._connections[name]

    def operation(self, name: str, action: Operation) -> bool:
        if name not in self._connections:
            raise Exception(f"Veza '{name}' nije registrirana.")

        return self._connections[name].operation(action)

    def connect(self, name: str) -> object:
        self.operation(name, Operation.Connect)
        return self._connections[name]

    def disconnect(self, name: str) -> bool:
        self.operation(name, Operation.Disconnect)
        return self._connections[name]._connected

    def update(self, *args, **kwargs):
        pass
