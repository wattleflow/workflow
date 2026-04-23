# Module name: postgres.py
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
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.engine.url import URL
from wattleflow.core import T
from wattleflow.concrete.connection import (
    ConnectionAction,
    GenericConnection,
    ConnectionState,
)
from wattleflow.concrete.exception import AuditException
from wattleflow.constants.enums import Event


ALLOWED_KWARGS = (
    "connection_name",
    "lazy_loading",
    "database_name",
    "host",
    "name",
    "port",
    "password",
    "user",
    "log_connection",
)


class PostgresError(AuditException):
    pass


class PostgresConnection(GenericConnection[Connection]):
    def __init__(self, **kwargs):
        kwargs.pop("allowed", None)
        super().__init__(allowed=ALLOWED_KWARGS, **kwargs)

    def create_connection(self) -> None:
        self.debug(
            msg=Event.Create.value,
            step=Event.Started.value,
            state=self.state.value,
        )

        if self.state in (
            ConnectionState.CREATED,
            ConnectionState.CONNECTED,
            ConnectionState.CONNECTING,
        ):
            self.warning(
                msg=Event.Create.value,
                step="connection already created",
                state=self.state.value,
            )
            return

        if self.state is ConnectionState.FAILED:
            raise PostgresError(
                caller=self,
                error=f"Cannot create connection in state '{self.state.value}'",
            )

        try:
            uri = URL.create(
                "postgresql",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database_name,
            )

            self._engine: Engine = create_engine(
                uri,
                pool_pre_ping=True,
                pool_recycle=1800,
                future=True,
            )
        except Exception as e:
            self.notify(
                self,
                error=f"Failed to create PostgreSQL engine: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise PostgresError(
                caller=self,
                error=f"Failed to create PostgreSQL engine: {e}",
            ) from e

        self._connection: T = None

        self.debug(
            msg=Event.Create.value,
            step=Event.Completed.value,
            state=self.state.value,
        )

    @contextmanager
    def connect(self) -> Generator[T, None, None]:
        self._ensure_created()

        self.debug(
            msg=Event.Connect.value,
            connection_name=self.connection_name,
            state=self.state.value,
        )

        if self.state is not ConnectionState.CREATED:
            self.notify(
                self,
                error=f"Cannot connect in state '{self.state.value}'",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise PostgresError(
                caller=self,
                error=f"Cannot connect in state '{self.state.value}'",
            )

        if self._engine is None:
            self.notify(
                self,
                error="Engine is not initialised",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise PostgresError(
                caller=self,
                error=f"{self.name}.connect: engine is None",
            )

        self._fsm.apply(ConnectionAction.CONNECT)

        try:
            self._connection: T = self._engine.connect()
            self._fsm.apply(ConnectionAction.CONNECT_OK)
        except Exception as e:
            self._fsm.apply(ConnectionAction.CONNECT_FAIL)
            self.notify(
                self,
                error=f"connect error: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise PostgresError(
                caller=self,
                error=f"connect error: {e}",
            ) from e

        self.debug(
            msg=Event.Connected.value,
            connection_name=self.connection_name,
            state=self.state.value,
        )

        try:
            yield self._connection
        except Exception as e:
            self.notify(
                self,
                error=f"Error during connection use: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise
        finally:
            if self._connection:
                try:
                    self._connection.close()
                except Exception as e:
                    self.notify(
                        self,
                        error=f"Error closing connection: {e}",
                        connection_name=self.connection_name,
                        state=self.state.value,
                    )
                finally:
                    self._connection = None
            self._fsm.apply(ConnectionAction.DISCONNECT)
            self.debug(
                msg=Event.Disconnected.value,
                connection_name=self.connection_name,
                note="engine still alive; call ensure_closed() to dispose",
            )

    def disconnect(self) -> None:
        self.debug(
            msg=Event.Disconnect.value,
            connection_name=self.connection_name,
            state=self.state.value,
        )

        try:
            if self._connection:
                try:
                    self._connection.close()
                except Exception as e:
                    self.notify(
                        self,
                        error=f"Error closing connection: {e}",
                        connection_name=self.connection_name,
                        state=self.state.value,
                    )
                finally:
                    self._connection = None
            if self._engine:
                try:
                    self._engine.dispose()
                except Exception as e:
                    self.notify(
                        self,
                        error=f"Error disposing engine: {e}",
                        connection_name=self.connection_name,
                        state=self.state.value,
                    )
                finally:
                    self._engine = None
        finally:
            self.debug(
                msg=Event.Disconnected.value,
                connection_name=self.connection_name,
                state=self.state.value,
            )

    def __repr__(self) -> str:
        return (
            f"{self.name}:{self.state.value}"
            f"[host={getattr(self, 'host', '?')} db={getattr(self, 'database_name', '?')}]"
        )
