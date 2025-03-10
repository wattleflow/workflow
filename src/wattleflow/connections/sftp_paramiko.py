# Module Name: core/connection/sftp_paramiko.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete sftp connection class.

import paramiko
import paramiko._version
from paramiko import AutoAddPolicy
from contextlib import contextmanager

from wattleflow.concrete import GenericConnection, SFTPConnectionError
from wattleflow.concrete.connection import Settings
from wattleflow.constants import Event, Operation
from wattleflow.constants.keys import (
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PASSPHRASE,
    KEY_PORT,
    KEY_USER,
    KEY_SSH_KEY_FILENAME,
    KEY_ALLOW_AGENT,
    KEY_LOOK_FOR_KEYS,
)
from wattleflow.helpers import TextStream


class SFTParamiko(GenericConnection):
    def __init__(self, strategy_audit, **settings):
        super().__init__(strategy_audit, **settings)
        self._client = paramiko.SSHClient()
        self._version = paramiko._version

    def create_connection(self, **settings):
        allowed = [
            KEY_ALLOW_AGENT,
            KEY_LOOK_FOR_KEYS,
            KEY_HOST,
            KEY_PASSPHRASE,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
            KEY_SSH_KEY_FILENAME,
        ]
        self._config = Settings(allowed=allowed, **settings)
        self.audit(
            owner=self,
            event=Event.Configuring,
            version=paramiko._version,
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
    def connect(self):
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
                hostname=self._config.get(KEY_HOST),
                port=int(self._config.get(KEY_PORT)),
                username=self._config.get(KEY_USER),
                password=self._config.get(KEY_PASSWORD),
                passphrase=self._config.get(KEY_PASSPHRASE),
                key_filename=self._config.get(KEY_SSH_KEY_FILENAME),
                look_for_keys=self._config.get(KEY_LOOK_FOR_KEYS),
            )
            self._connection = self._client.open_sftp()
            self._connected = True

            self.audit(
                owner=self,
                event=Event.Connected,
                version=self._version,
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
                version=self._version,
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
            version=self._version,
            connected=self._connected,
            level=3,
        )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "password", "framework"]
        ]
        return f"{conn}"

    # def getcwd(self) -> bool:
    #     if not self.connect():
    #         raise ConnectionError("SFTP connection is not established.")

    #     try:
    #         result = self.connection.getcwd()
    #     except Exception as e:
    #         self.audit(event=Event.Failed, status=f"Upload failed: {e}")
    #     finally:
    #         self.disconnect()
    #     return result

    # def listdir(self, path:str) -> bool:
    #     if not self.connect():
    #         raise ConnectionError("SFTP connection is not established.")

    #     try:
    #         result = self.connection.listdir(path)
    #     except Exception as e:
    #         self.audit(event=Event.Failed, status=f"Upload failed: {e}")
    #     finally:
    #         self.disconnect()
    #     return result

    # def upload(self, local_path: str, remote_path: str):
    #     if not self.connect():
    #         raise ConnectionError("SFTP connection is not established.")

    #     try:
    #         self.connection.put(local_path, remote_path)
    #         self.audit(
    #             event=Event.Completed, status=f"Uploaded {local_path} to {remote_path}"
    #         )
    #     except Exception as e:
    #         self.audit(event=Event.Failed, status=f"Upload failed: {e}")
    #     finally:
    #         self.disconnect()

    # def download(self, remote_path: str, local_path: str):
    #     if not self.connection:
    #         raise ConnectionError("SFTP connection is not established.")

    #     try:
    #         self.connection.get(remote_path, local_path)
    #         self.audit(
    #             event=Event.Completed,
    #             status=f"Downloaded {remote_path} to {local_path}",
    #         )
    #     except Exception as e:
    #         self.audit(event=Event.Failed, status=f"Download failed: {e}")
    #     finally:
    #         self.disconnect()
