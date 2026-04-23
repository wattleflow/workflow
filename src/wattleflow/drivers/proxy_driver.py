# Module name: drivers/proxy_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations

import ipaddress
import logging
import os
import pandas as pd
import requests
import tempfile as tmp

from logging import Handler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from wattleflow.concrete.driver import GenericDriver, DriverMetadata
from wattleflow.concrete.exception import AuditException, DriverException
from wattleflow.connections.proxy import ProxyConnection
from wattleflow.constants.enums import Event
from wattleflow.constants.filetype import FileType
from wattleflow.drivers.file_storage import FileStorage

_DEFAULT_CACHE_DIR: str = os.environ.get(
    "WATTLEFLOW_CACHE",
    str(Path(tmp.gettempdir()).joinpath("wattleflow_cache").absolute()),
)

_MAX_DOWNLOAD_BYTES: int = int(
    os.environ.get("WATTLEFLOW_MAX_DOWNLOAD_BYTES", 100 * 1024 * 1024)
)

_SENSITIVE_KWARGS: frozenset = frozenset({"api_key", "token", "basic_auth", "password"})


class ProxyDriverError(DriverException):
    pass


class ProxyDriver(GenericDriver):
    ALLOWED_KWARGS = [
        "local_path",
        "create",
        "normalised",
        "timeout",
        "verify_ssl",
        "connection_name",
    ]

    def __init__(
        self,
        local_path: str = _DEFAULT_CACHE_DIR,
        create: bool = True,
        normalised: bool = True,
        timeout: int = 30,
        verify_ssl: bool = True,
        connection_name: Optional[ProxyConnection] = None,
        level: int = logging.WARNING,
        handler: Optional[Handler] = None,
        **kwargs,
    ) -> None:
        kwargs.pop("allowed", None)
        GenericDriver.__init__(
            self,
            level=level,
            handler=handler,
            allowed=self.ALLOWED_KWARGS,
            local_path=local_path,
            create=create,
            normalised=normalised,
            timeout=timeout,
            verify_ssl=verify_ssl,
            connection_name=connection_name,
            **kwargs,
        )
        self._current_path: Optional[Path] = None

    # region GenericDriver lifecycle

    def load(self) -> None:
        verify_ssl: bool = getattr(self, "verify_ssl", True)
        if not verify_ssl:
            self.warning(
                msg=Event.Constructor.value,
                reason="SSL verification disabled (verify_ssl=False) — vulnerable to MITM attacks.",
            )

        local_path = Path(getattr(self, "local_path", _DEFAULT_CACHE_DIR))
        if not local_path.is_dir():
            if not getattr(self, "create", True):
                reason = f"local_path must be a directory: {local_path!r}"
                self.error(
                    msg=Event.Constructor.value,
                    reason=reason,
                    local_path=str(local_path),
                )
                raise RuntimeError(reason)
            local_path.mkdir(parents=True, exist_ok=True)

        self._current_path = local_path
        self.debug(msg="load", step=Event.Completed.name, path=str(self._current_path))

    def close(self) -> None:
        self.debug(msg="close", step=Event.Started.name)
        self._current_path = None
        self.debug(msg="close", step=Event.Completed.name)

    # endregion

    # region Public API

    def read(self, uri: str, **kwargs) -> Any:
        self.ensure_live()
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            uri=uri,
            **self._safe_log_kwargs(**kwargs),
        )
        try:
            self._validate_uri(uri)
            storage = FileStorage(
                local_path=str(self._current_path),
                uri=uri,
                create=True,
                normalised=True,
            )
            response = self._download(uri, **kwargs)
            storage.filename.write_bytes(response.content)

            if not storage.filename.exists():
                reason = f"Failed to save file to local cache: {storage.filename}"
                self.error(msg=Event.Read.value, uri=uri, reason=reason)
                raise IOError(reason)

            file_type = FileType.detect_content(response.content)
            self.debug(
                msg=Event.Read.value,
                step=Event.Completed.value,
                origin=storage.origin,
                filename=storage.filename,
                size=storage.size,
                file_type=file_type.name,
            )

            if file_type == FileType.CSV:
                return pd.read_csv(storage.filename)
            if file_type == FileType.JSON:
                return pd.read_json(storage.filename)
            if file_type == FileType.XLS:
                return pd.read_excel(storage.filename)
            if file_type == FileType.TXT:
                return storage.filename.read_text()
            return storage.filename.read_bytes()

        except AuditException as e:
            self.error(msg=Event.Read.value, uri=uri, error=e.reason)
            raise
        except Exception as e:
            self.error(msg=Event.Read.value, uri=uri, error=str(e))
            raise ProxyDriverError(caller=self, error=str(e)) from e

    def write(self, uri: str, **kwargs) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__}.write() is not implemented. "
            "HTTP write operations are not supported by this driver."
        )

    def metadata(self) -> DriverMetadata:
        return DriverMetadata(
            name=self.__class__.__name__,
            version="1.0",
            protocol="https",
            capabilities=["read"],
        )

    # endregion

    # region Private helpers

    def _validate_uri(self, uri: str) -> None:
        self.debug(msg=Event.Validate.value, uri=uri)
        parsed = urlparse(uri)

        if parsed.scheme not in ("http", "https"):
            reason = (
                f"Unsupported URI scheme '{parsed.scheme}'. "
                f"{self.__class__.__name__} supports http and https only."
            )
            self.error(msg=Event.Read.value, uri=uri, reason=reason)
            raise ValueError(reason)

        host = parsed.hostname or ""
        if host.lower() in ("localhost", "0.0.0.0"):
            reason = f"Access to localhost is not allowed: {host!r}"
            self.error(msg=Event.Read.value, uri=uri, reason=reason)
            raise PermissionError(reason)

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                reason = (
                    f"Access to private/internal addresses is not allowed: {host!r}"
                )
                self.error(msg=Event.Read.value, uri=uri, reason=reason)
                raise PermissionError(reason)
        except ValueError:
            pass  # hostname, not an IP literal — allowed

    def _safe_log_kwargs(self, **kwargs) -> dict:
        return {k: ("***" if k in _SENSITIVE_KWARGS else v) for k, v in kwargs.items()}

    def _build_request_kwargs(self, **kwargs) -> dict:
        request_kwargs: dict = {
            "timeout": getattr(self, "timeout", 30),
            "verify": getattr(self, "verify_ssl", True),
        }
        merged_headers: dict = {}

        api_key = kwargs.get("api_key")
        if api_key:
            merged_headers["X-API-Key"] = api_key

        token = kwargs.get("token")
        if token:
            merged_headers["Authorization"] = f"Bearer {token}"

        basic_auth = kwargs.get("basic_auth")
        if basic_auth:
            request_kwargs["auth"] = tuple(basic_auth)

        merged_headers.update(kwargs.get("headers") or {})
        if merged_headers:
            request_kwargs["headers"] = merged_headers

        return request_kwargs

    def _download(self, uri: str, **kwargs) -> requests.Response:
        self.debug(
            msg=Event.Downloading.value, uri=uri, **self._safe_log_kwargs(**kwargs)
        )

        _uri = str(uri)
        _parsed = urlparse(_uri)
        _safe_uri = _parsed._replace(query="", fragment="").geturl()

        request_kwargs = self._build_request_kwargs(**kwargs)
        request_kwargs["stream"] = True

        self.debug(msg=Event.Downloading.value, step=Event.Started.value, uri=_safe_uri)

        connection: Optional[ProxyConnection] = getattr(self, "connection_name", None)
        if connection is not None:
            with connection.connect() as session:
                response = session.get(_uri, **request_kwargs)
        else:
            response = requests.get(_uri, **request_kwargs)

        response.raise_for_status()

        chunks: list[bytes] = []
        received: int = 0
        for chunk in response.iter_content(chunk_size=65536):
            received += len(chunk)
            if received > _MAX_DOWNLOAD_BYTES:
                response.close()
                reason = (
                    f"Download exceeds {_MAX_DOWNLOAD_BYTES} bytes limit: {_safe_uri}"
                )
                self.error(msg=Event.Read.value, uri=_safe_uri, reason=reason)
                raise ValueError(reason)
            chunks.append(chunk)

        response._content = b"".join(chunks)
        return response

    # endregion

    def __repr__(self) -> str:
        path = self._current_path or Path(
            getattr(self, "local_path", _DEFAULT_CACHE_DIR)
        )
        return f"{self.__class__.__name__}(state={self._fsm.state.value}, path={path.resolve()})"
