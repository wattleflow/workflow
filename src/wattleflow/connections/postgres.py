# Module Name: core/connection/postgress_alchemy.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete postgres connection class.


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This connection requires the SQLAlchemy library.
# The library is used for the connection with a postgres server.
#   pip install SQLAlchemy
# --------------------------------------------------------------------------- #

from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Engine  # Connection
from wattleflow.core import IStrategy
from wattleflow.concrete.connection import (
    GenericConnection,
    Operation,
    Settings,
)
from wattleflow.concrete.exception import ConnectionException
from wattleflow.helpers.streams import TextStream
from wattleflow.constants.enums import Event
from wattleflow.constants.keys import (
    KEY_NAME,
    KEY_DATABASE,
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PORT,
    KEY_USER,
    # KEY_SCHEMA,
)


class PostgresConnection(GenericConnection):
    _apilevel: str = "<apilevel>"
    _driver: str = "<driver>"
    _version: str = "<version>"
    _publisher: str = "<publisher>"
    _database: str = "<database>"

    def __init__(self, strategy_audit: IStrategy, **settings):
        self._engine: Optional[Engine] = None
        self._connection: Engine = None
        super().__init__(strategy_audit, **settings)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_connection(self, **settings):
        allowed = [
            KEY_NAME,
            KEY_DATABASE,
            KEY_HOST,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
        ]

        self._config = Settings(allowed=allowed, **settings)
        uri = "postgresql://{}:{}@{}:{}/{}".format(
            self._config.user,
            self._config.password,
            self._config.host,
            self._config.port,
            self._config.database,
        )
        self._engine = create_engine(uri)
        self._driver = self._engine.driver
        self._apilevel = self._engine.dialect.dbapi.apilevel

        self.audit(
            owner=self,
            event=Event.Connected,
            engine=str(self._engine),
            apilevel=str(self._apilevel),
            driver=self._driver,
            level=4,
        )

    def clone(self) -> GenericConnection:
        return PostgresConnection(self._strategy_audit, self._settings)

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            self.connect()
        else:
            self.disconnect()

    @contextmanager
    def connect(self) -> Generator[GenericConnection, None, None]:
        if self._connected:
            return self

        try:
            self.audit(
                owner=self,
                event=Event.Authenticate,
                status=Event.Authenticating,
                level=4,
            )

            self._connection = self._engine.connect()
            result = self._connection.execute(text("SELECT version();"))
            self._version = result.scalar()
            self._driver = self._engine.driver
            self._apilevel = self._engine.dialect.dbapi.apilevel
            self._database = self._settings.database
            self._privileges = self._settings.user
            self._publisher = "unknown"
            self._connected = True
            yield self
        except Exception as e:
            raise ConnectionException(
                caller=self, error=f"Connection error: {e}", level=1
            )
        finally:
            self.disconnect()

    def disconnect(self):
        if not self._connected:
            self.audit(
                owner=self,
                event=Event.Disconnected,
                connected=self._connected,
                level=3,
            )
            return

        if self._engine:
            self._engine.dispose()
            self._engine = None

        self._connected = False

        self.audit(
            owner=self,
            event=Event.Disconnected,
            connected=self._connected,
            level=3,
        )

    def __del__(self):
        if self._connection:
            self._connection.dispose()
            self._connection = None
            self._connected = False

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "password", "framework"]
        ]
        return f"{conn}"
