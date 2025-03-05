# Module Name: core/connection/postgress_alchemy.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete sftp connection class.

from wattleflow.core import IObserver, IStrategy
from wattleflow.concrete.connection import (
    ConnectionException,
    GenericConnection,
    Operation,
    Settings,
)
from wattleflow.helpers.streams import TextStream
from wattleflow.constants.enums import Events
from wattleflow.constants.keys import (
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PORT,
    KEY_USER,
)


class SFTPConnection(GenericConnection):
    def __init__(self, strategy_audit: IStrategy, manager: IObserver, **settings):
        super().__init__(strategy_audit, manager, **settings)

    def create_conenction(self, **settings):
        allowed = [
            KEY_HOST,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
        ]

        self.audit(event=Events.Configuring)

        self._settings = Settings(allowed, allowed, **settings)

        self._connected = True

        self.audit(
            event=Events.Connected, version=self._version, connected=self._connected
        )

    def clone(self) -> GenericConnection:
        return ConnectionException(self._strategy_audit, self._manager, self._settings)

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            self.connect()
        else:
            self.disconnect()

    def connect(self) -> bool:
        if self._connected:
            self.audit(event=Events.Connected, version=self._version)
            return True

        try:
            self._connection = self._engine.connect()
            self._connected = True
            self.audit(event=Events.Connected)
            return True
        except Exception:
            return False

    def disconnect(self):
        if not self._connection:
            self.audit(event=Events.Disconnected)
            return

        self._connection = None
        self._engine.dispose()
        self._connected = False
        self.audit(event=Events.Disconnected)

    def settings(self, name):
        return self._settings.get(name)

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "_manager", "password", "framework"]
        ]
        return f"{conn}"
