# Module Name: connection/sftp_paramiko.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete sftp connection class.


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This connection requires the paramiko library.
# The library is used for the connection with a SFTP server.
#   pip install paramiko
# --------------------------------------------------------------------------- #

from logging import Handler, NOTSET
import paramiko
from paramiko import AutoAddPolicy
from contextlib import contextmanager
from typing import Generator, Optional

from wattleflow.concrete import GenericConnection, SFTPConnectionError
from wattleflow.concrete.connection import Settings
from wattleflow.constants import Event, Operation
from wattleflow.constants.keys import (
    KEY_NAME,
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PASSPHRASE,
    KEY_PORT,
    KEY_USER,
    KEY_SSH_KEY_FILENAME,
    KEY_ALLOW_AGENT,
    KEY_LOOK_FOR_KEYS,
    KEY_COMPRESS,
)
from wattleflow.helpers import TextStream


class SFTParamiko(GenericConnection):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **configuration,
    ):
        GenericConnection.__init__(self, level=level, handler=handler, **configuration)
        self._client = paramiko.SSHClient()
        self.debug(msg=Event.Constructor.value)

    def create_connection(self, **settings):
        allowed = [
            KEY_NAME,
            KEY_ALLOW_AGENT,
            KEY_LOOK_FOR_KEYS,
            KEY_HOST,
            KEY_PASSPHRASE,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
            KEY_SSH_KEY_FILENAME,
            KEY_COMPRESS,
        ]
        self._config = Settings(allowed=allowed, **settings)
        self.debug(
            msg=Event.Configuring.value,
            connected=self._connected,
        )

    def clone(self) -> object:
        self.debug(msg="clone")
        return SFTParamiko(
            level=self._level,
            handler=self._handler,
            **self._config.todict(),
        )

    def operation(self, action: Operation) -> bool:
        self.debug(msg=action.value)
        if action == Operation.Connect:
            return self.connect()
        elif action == Operation.Disconnect:
            self.disconnect()
        else:
            error = "Unknown operation"
            self.warning(msg=error)
            raise UserWarning(error)

    @contextmanager
    def connect(self) -> Generator[GenericConnection, None, None]:
        self.debug(msg=Event.Connect)
        if self._connected:
            return self

        try:
            self.debug(
                msg=Event.Authenticate.value,
                status=Event.Authenticating.value,
            )

            self._client.set_missing_host_key_policy(AutoAddPolicy())
            self._client.connect(
                hostname=self._config.host,
                port=int(self._config.port),
                username=self._config.user,
                password=self._config.password,
                passphrase=self._config.passphrase,
                key_filename=self._config.key_filename,
                look_for_keys=self._config.look_for_keys,
            )
            self._connection = self._client.open_sftp()
            self._connected = True

            self.info(
                msg=Event.Connected.value,
                connected=self._connected,
            )
            yield self
        except paramiko.AuthenticationException as e:
            raise SFTPConnectionError(
                caller=self, error=f"Authentication failed: {e}", level=1
            )
        except paramiko.BadHostKeyException as e:
            raise SFTPConnectionError(
                caller=self, error=f"Bad host exception: {e}", level=1
            )
        except paramiko.SSHException as e:
            raise SFTPConnectionError(caller=self, error=f"SSH Exception: {e}", level=1)
        except Exception as e:
            raise SFTPConnectionError(
                caller=self, error=f"Connection error: {e}", level=1
            )
        finally:
            self.disconnect()

    def disconnect(self):
        if not self._connected:
            self.debug(
                msg=Event.Disconnected.value,
                connected=self._connected,
            )
            return

        if self._connection:
            self._connection.close()

        self._client.close()
        self._connected = False

        self.debug(
            msg=Event.Disconnected.value,
            connected=self._connected,
        )

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["password", "framework"]
        ]
        return f"{conn}"
