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
from paramiko import (
    AuthenticationException,
    BadHostKeyException,
    RejectPolicy,
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
        # FIX: State.Creating is a transient state for the setup phase; the method
        # must advance to State.Created on completion to satisfy the GenericConnection
        # API contract and ensure the `connected` property behaves correctly.
        self._state = State.Created

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

            # FIX: AutoAddPolicy unconditionally trusts any server host key, making
            # every connection vulnerable to Man-in-the-Middle attacks.  Load the
            # system-wide and per-user known_hosts files so that Paramiko can verify
            # the server's identity, then switch to RejectPolicy so that connections
            # to unrecognised hosts are refused rather than silently accepted.
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
            self._connected = True
            # FIX: _state was never advanced to State.Connected after a successful
            # connection; the `connected` property (which checks `_state is
            # State.Connected`) therefore always returned False during an active session.
            self._state = State.Connected

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
            # FIX: disconnect() is called before re-raising so that the underlying
            # SSHClient is always closed when setup fails before the inner try/finally
            # (which wraps the yield) has had a chance to run, preventing a resource leak.
            self.disconnect()
            raise SFTPConnectionError(
                caller=self, error=f"Authentication failed: {e}"
            ) from e
        except BadHostKeyException as e:
            self.disconnect()
            raise SFTPConnectionError(caller=self, error=f"Bad host key: {e}") from e
        except SSHException as e:
            self.disconnect()
            raise SFTPConnectionError(caller=self, error=f"SSH error: {e}") from e
        except Exception as e:
            self.disconnect()
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
            # FIX: _state was never reset after closing the connection; callers
            # relying on the `connected` property or inspecting `state` after
            # disconnect would observe a stale State.Connected value.
            self._state = State.Closed
            self.debug(msg=Event.Disconnected.value, state=self.state.name)
