# Module Name: connection/postgress_alchemy.py
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
from sqlalchemy.engine.base import Engine, Connection
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
    KEY_PUBLISHER,
    # KEY_SCHEMA,
)


class PostgresConnection(GenericConnection):
    _apilevel: str = "<apilevel>"
    _driver: str = "<driver>"
    _version: str = "<version>"
    _publisher: str = "<publisher>"
    _database: str = "<database>"
    _connection: Optional[Connection] = None

    def __init__(self, strategy_audit: IStrategy, **configuration):
        self._engine: Optional[Engine] = None
        super().__init__(strategy_audit, **configuration)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_connection(self, **configuration):
        allowed = [
            KEY_NAME,
            KEY_DATABASE,
            KEY_HOST,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
            KEY_PUBLISHER,
        ]

        self._config = Settings(allowed=allowed, **configuration)
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
        self._publisher = self._config.publisher

        self.audit(
            owner=self,
            event=Event.Authenticating,
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
                event=Event.Connecting,
                status=Event.Authenticating,
                level=4,
            )

            self._connection = self._engine.connect()
            self._connected = True

            result = self._connection.execute(text("SELECT version();"))
            self._version = result.scalar()
            self._driver = self._engine.driver
            self._apilevel = self._engine.dialect.dbapi.apilevel
            self._database = self._config.database
            self._privileges = self._config.user
            yield self
        except Exception as e:
            raise ConnectionException(
                caller=self, error=f"Connection error: {e}", level=1
            )
        finally:
            self.disconnect()

    def disconnect(self):
        if self._connection:
            self._connection.close()
            self._connection = None
            self._connected = False

            self.audit(
                owner=self,
                event=Event.Disconnected,
                connected=self._connected,
                level=3,
            )

    def __del__(self):
        if self._connection:
            self._connection.close()
            self._connection = None
            self._connected = False

        if self._engine:
            self._engine.dispose()
            self._engine = None

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "password", "framework"]
        ]
        return f"{conn}"
