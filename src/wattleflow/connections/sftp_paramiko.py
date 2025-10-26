# Module name: sftp_paramiko.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This connection requires the paramiko library.
# The library is used for the connection with a SFTP server.
#   pip install paramiko
# --------------------------------------------------------------------------- #


from __future__ import annotations
from contextlib import contextmanager
from paramiko import (
    AutoAddPolicy,
    AuthenticationException,
    BadHostKeyException,
    SSHClient,
    SFTPClient,
    SSHException,
)
from typing import Generator
from wattleflow.core import T
from wattleflow.concrete import AuditException
from wattleflow.concrete.connection import GenericConnection, State
from wattleflow.constants import Event


class SFTPConnectionError(AuditException):
    pass


class SFTPParamiko(GenericConnection[SFTPClient]):
    def create_connection(self) -> None:
        self._engine = None
        self._connection = None  # type: ignore
        self._state = State.Creating

    @contextmanager
    def connect(self) -> Generator[T, None, None]:
        self.debug(
            msg=Event.Connecting.value,
            connection=self._connection_name,
            status=Event.Authenticating.value,
            state=self.state.name,
        )

        try:
            self._engine = SSHClient()
            self._engine.set_missing_host_key_policy(AutoAddPolicy())
            self._engine.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                passphrase=self.passphrase,
                key_filename=self.key_filename,
                look_for_keys=self.look_for_keys,
                allow_agent=self.allow_agent,
                timeout=self.timeout,
                compress=self.compress,
            )

            self._connection = self._engine.open_sftp()
            self._connected = True

            self.info(
                msg=Event.Connected.value,
                connected=self._connected,
                host=self.host,
                port=self.port,
                user=self.username,
                state=self.state.name,
            )

            try:
                yield self._connection  # type: ignore
            finally:
                self.disconnect()

        except AuthenticationException as e:
            raise SFTPConnectionError(
                caller=self, error=f"Authentication failed: {e}"
            ) from e
        except BadHostKeyException as e:
            raise SFTPConnectionError(caller=self, error=f"Bad host key: {e}") from e
        except SSHException as e:
            raise SFTPConnectionError(caller=self, error=f"SSH error: {e}") from e
        except Exception as e:
            raise SFTPConnectionError(
                caller=self, error=f"Connection error: {e}"
            ) from e

    def disconnect(self) -> None:
        self.debug(msg=Event.Disconnecting.value, state=self.state.name)

        try:
            if getattr(self, "_connection", None):
                try:
                    self._connection.close()
                except Exception:
                    pass
                finally:
                    self._connection = None  # type: ignore

            if getattr(self, "_engine", None):
                try:
                    self._engine.close()  # type: ignore
                except Exception:
                    pass
                finally:
                    self._engine = None
        finally:
            self._connected = False
            self.debug(msg=Event.Disconnected.value, state=self.state.name)
