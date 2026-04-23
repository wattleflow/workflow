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
import os
from contextlib import contextmanager

try:
    from paramiko import (
        AuthenticationException,
        BadHostKeyException,
        RejectPolicy,
        SSHClient,
        SFTPClient,
        SSHException,
        __version__,
    )
except Exception as e:
    raise ModuleNotFoundError(
        f"Missing required package  to run this code.[{str(e)}]\n"
        "Please install it with `pip install paramiko`"
    ) from e

from typing import Generator
from wattleflow.core import T
from wattleflow.concrete.connection import (
    ConnectionAction,
    GenericConnection,
    ConnectionState,
)
from wattleflow.concrete.exception import AuditException
from wattleflow.constants import Event


class SFTPConnectionError(AuditException):
    pass


class SFTPParamiko(GenericConnection[SFTPClient]):
    def create_connection(self) -> None:
        self._engine = None
        self._connection = None
        self._version = str(__version__)

    @contextmanager
    def connect(self) -> Generator[T, None, None]:
        self._ensure_created()

        self.debug(
            msg=Event.Connecting.value,
            connection=self._connection_name,
            status=Event.Authenticating.value,
            state=self.state.value,
        )

        self._fsm.apply(ConnectionAction.CONNECT)

        try:
            self._engine = SSHClient()

            self._engine.load_system_host_keys()

            known_hosts = os.path.expanduser("~/.ssh/known_hosts")

            if os.path.isfile(known_hosts):
                self._engine.load_host_keys(known_hosts)

            self._engine.set_missing_host_key_policy(RejectPolicy())

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
            self._fsm.apply(ConnectionAction.CONNECT_OK)

            self.info(
                msg=Event.Connected.value,
                host=self.host,
                port=self.port,
                user=self.username,
                state=self.state.value,
            )

            try:
                yield self._connection  # type: ignore
            finally:
                if self._connection:
                    try:
                        self._connection.close()
                    except Exception:
                        pass
                    finally:
                        self._connection = None  # type: ignore
                if self._engine:
                    try:
                        self._engine.close()  # type: ignore
                    except Exception:
                        pass
                    finally:
                        self._engine = None
                self._fsm.apply(ConnectionAction.DISCONNECT)
                self.debug(msg=Event.Disconnected.value, state=self.state.value)

        except AuthenticationException as e:
            self._fsm.apply(ConnectionAction.CONNECT_FAIL)
            self.notify(
                self,
                error=f"Authentication failed: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise SFTPConnectionError(
                caller=self, error=f"Authentication failed: {e}"
            ) from e
        except BadHostKeyException as e:
            self._fsm.apply(ConnectionAction.CONNECT_FAIL)
            self.notify(
                self,
                error=f"Bad host key: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise SFTPConnectionError(caller=self, error=f"Bad host key: {e}") from e
        except SSHException as e:
            self._fsm.apply(ConnectionAction.CONNECT_FAIL)
            self.notify(
                self,
                error=f"SSH error: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise SFTPConnectionError(caller=self, error=f"SSH error: {e}") from e
        except Exception as e:
            if self._fsm.state is ConnectionState.CONNECTING:
                self._fsm.apply(ConnectionAction.CONNECT_FAIL)
            self.notify(
                self,
                error=f"Connection error: {e}",
                connection_name=self.connection_name,
                state=self.state.value,
            )
            raise SFTPConnectionError(
                caller=self, error=f"Connection error: {e}"
            ) from e

    def disconnect(self) -> None:
        self.debug(msg=Event.Disconnecting.value, state=self.state.value)

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
            self.debug(msg=Event.Disconnected.value, state=self.state.value)
