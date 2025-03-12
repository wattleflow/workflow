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

import paramiko
from paramiko import AutoAddPolicy
from contextlib import contextmanager
from typing import Generator

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
    def __init__(self, strategy_audit, **settings):
        super().__init__(strategy_audit, **settings)
        self._client = paramiko.SSHClient()

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
        self.audit(
            owner=self,
            event=Event.Configuring,
            connected=self._connected,
            level=4,
        )

    def clone(self) -> object:
        return SFTParamiko(self._strategy_audit, **self._config.todict())

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            return self.connect()
        elif action == Operation.Disconnect:
            self.disconnect()
        else:
            raise UserWarning("Unknown operation")

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

            self.audit(
                owner=self,
                event=Event.Connected,
                connected=self._connected,
                level=3,
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
            self.audit(
                owner=self,
                event=Event.Disconnected,
                connected=self._connected,
                level=3,
            )
            return

        if self._connection:
            self._connection.close()

        self._client.close()
        self._connected = False

        self.audit(
            owner=self,
            event=Event.Disconnected,
            connected=self._connected,
            level=3,
        )

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "password", "framework"]
        ]
        return f"{conn}"
