# Module Name: connection/teradata.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete taradata databse connection class.

from logging import Handler, NOTSET
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from wattleflow.concrete import GenericConnection, Settings, ConnectionException
from wattleflow.constants import Event
from wattleflow.helpers import TextStream
from wattleflow.constants.keys import (
    KEY_NAME,
    KEY_DATABASE,
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PORT,
    KEY_USER,
    KEY_PUBLISHER,
)


class TeradataConnection(GenericConnection):
    _engine: Optional[Engine] = None
    _apilevel: str = "<apilevel>"
    _driver: str = "<driver>"
    _version: str = "<version>"
    _publisher: str = "<publisher>"
    _database: str = "<database>"

    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **configuration,
    ):
        GenericConnection.__init__(self, level=level, handler=handler, **configuration)

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
        self.debug(msg="create_connection", allowed=allowed)
        self._config = Settings(allowed=allowed, **configuration)
        uri = "teradata://{}:{}@{}:{}/{}".format(
            self._config.user,
            self._config.password,
            self._config.host,
            self._config.port,
            self._config.database,
        )
        self.debug(msg=Event.Authenticating.value, allowed=allowed)
        self._engine = create_engine(uri)
        self._driver = self._engine.driver
        self._apilevel = self._engine.dialect.dbapi.apilevel
        self._publisher = self._config.publisher
        self.debug(
            msg=Event.Authenticated.value,
            engine=str(self._engine),
            apilevel=str(self._apilevel),
            driver=self._driver,
        )

    def clone(self) -> GenericConnection:
        return TeradataConnection(
            level=self._level, handler=self._handler, **self._settings
        )

    @contextmanager
    def connect(self) -> Generator[GenericConnection, None, None]:
        if self._connected:
            return self

        try:
            self.debug(
                msg=Event.Connecting.value,
                status=Event.Authenticating.value,
            )

            self._connection = self._engine.connect()
            self._connected = True
            result = self._connection.execute(str("SELECT * FROM dbc.dbcinfo;"))
            self._version = result.scalar()
            self._driver = self._engine.driver
            self._apilevel = self._engine.dialect.dbapi.apilevel
            self._database = self._config.database
            self._privileges = self._config.user

            self.info(
                msg=Event.Connected.value,
                db=self._database,
                privilages=self._privileges,
                api=self._apilevel,
                driver=self._driver,
                ver=self._version,
            )

            yield self
        except Exception as e:
            raise ConnectionException(
                caller=self, error=f"Connection error: {e}", level=1
            )
        finally:
            self.disconnect()

    def disconnect(self):
        self.debug(msg=Event.Disconnecting.value, connected=self._connected)
        if self._connection:
            self._connection.close()
            self._connection = None
            self._connected = False
            self.debug(msg=Event.Disconnected.value, connected=self._connected)

    def __del__(self):
        self.debug(msg="__del__")
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
            if k.lower() not in ["password", "framework"]
        ]
        return f"{conn}"
