# Module name: postgress_alchemy.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This connection requires the SQLAlchemy library.
# The library is used for the connection with a postgres server.
#   pip install SQLAlchemy
# --------------------------------------------------------------------------- #


from __future__ import annotations
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.engine.url import URL
from wattleflow.core import T
from wattleflow.concrete.connection import GenericConnection, State
from wattleflow.concrete.exception import ConnectionException
from wattleflow.constants.enums import Event


class PostgresConnection(GenericConnection[Connection]):
    @property
    def apilevel(self) -> str:
        if not self._engine:
            return "uninitialised"
        return str(getattr(self._engine.dialect.dbapi, "apilevel", "unknown"))

    @property
    def driver(self) -> str:
        if not self._connection:
            return "unknown"
        return getattr(self._engine.dialect, "driver", "unknown")

    @property
    def version(self) -> str:
        if not self.connected or not self._connection:
            return "unknown"

        try:
            with self.connect() as conn:
                result = conn.execute(text("SELECT version();"))
                return str(result.scalar())
        except Exception:
            return "unknown"

    def create_connection(self) -> None:
        self.debug(
            msg=Event.Create.value,
            step="create_connection",
            name=self.connection_name,
            state=self.state.name,
        )

        self._state = State.Creating

        uri = URL.create(
            "postgresql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

        self._engine: Engine = create_engine(
            uri,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
        self._state = State.Created
        self._connection: T = None  # type: ignore

        self.debug(
            msg=Event.Authenticated.value,
            call="create_connection",
            engine=self._engine,
            apilevel=self.apilevel,
            driver=self.driver,
            state=self.state.name,
        )

    def clone(self) -> "PostgresConnection":
        raise NotImplementedError(f"{self.name}.clone is not implemented.")

    @contextmanager
    def connect(self) -> Generator[T, None, None]:
        self.debug(
            msg=Event.Connect.value,
            connection_name=self.connection_name,
            state=self.state.name,
        )

        if not self._engine:
            raise ConnectionError(f"{self.name}.connect: engine is None")

        try:
            self._state = State.Connecting
            self._connection: T = self._engine.connect()  # type: ignore
            self._state = State.Connected
            self.debug(
                msg=Event.Connect.value,
                connection_name=self.connection_name,
                state=self.state.name,
            )

            yield self._connection
        except AttributeError as e:
            raise ConnectionException(
                caller=self,
                call="AttributeError in connect()",
                error=str(e),
            ) from e
        except Exception as e:
            raise ConnectionException(caller=self, call="connect", error=str(e)) from e
        finally:
            self.disconnect()

    def disconnect(self) -> None:
        self.debug(
            msg=Event.Disconnect.value,
            connection_name=self._connection_name,
            state=self.state.name,
        )

        try:
            if self._connection:
                self._connection.close()
                self._connection = None
            if self._engine:
                self._engine.dispose()
        finally:
            self._state = State.Closed
