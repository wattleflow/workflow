# Module name: http_file_system_driver.py
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

from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from wattleflow.concrete import AuditException, GenericDriverClass
from wattleflow.constants.enums import Event
from wattleflow.drivers import FileStorage
from wattleflow.helpers.filetypes import FileType

_DEFAULT_CACHE_DIR: str = os.environ.get(
    "WATTLEFLOW_CACHE",
    str(Path(tmp.gettempdir()).joinpath("wattleflow_cache").absolute()),
)

_MAX_DOWNLOAD_BYTES: int = int(
    os.environ.get("WATTLEFLOW_MAX_DOWNLOAD_BYTES", 100 * 1024 * 1024)  # 100 MB
)

_SENSITIVE_KWARGS: frozenset = frozenset({"api_key", "token", "basic_auth", "password"})


class HttpFileSystemDriver(GenericDriverClass):
    def __init__(
        self,
        local_path: str = _DEFAULT_CACHE_DIR,
        create: bool = False,
        normalised: bool = True,
        timeout: int = 30,
        verify_ssl: bool = True,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
    ) -> None:
        __allowed__ = [
            "local_path",
            "current_path",
            "create",
            "normalised",
            "timeout",
            "verify_ssl",
        ]

        GenericDriverClass.__init__(
            self,
            level=level,
            handler=handler,
            lazy_load=False,
            allowed=__allowed__,
            local_path=local_path,
            create=create,
            normalised=normalised,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        if not verify_ssl:
            self.warning(
                msg=Event.Constructor.value,
                reason="SSL certificate verification is disabled (verify_ssl=False). "
                "This makes connections vulnerable to MITM attacks.",
            )
        if not Path(local_path).is_dir():
            if not create:
                reason = f"local_path should be a directory: {local_path!r}"
                self.error(
                    msg=Event.Constructor.value, reason=reason, local_path=local_path
                )
                raise RuntimeError(reason)
            Path(local_path).mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        self.current_path: Path = Path(self.local_path)

    def read(self, uri: str, **kwargs) -> Any:
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            uri=uri,
            **self._safe_log_kwargs(**kwargs),
        )
        try:
            self._validate_uri(uri)
            storage = FileStorage(
                local_path=str(self.local_path),
                uri=uri,
                create=True,
                normalised=True,
            )

            response = self._download(uri, **kwargs)
            storage.filename.write_bytes(response.content)

            if storage.filename.exists() is False:
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

            match file_type:
                case FileType.CSV:
                    return pd.read_csv(storage.filename)
                case FileType.JSON:
                    return pd.read_json(storage.filename)
                case FileType.XLS:
                    return pd.read_excel(storage.filename)
                case FileType.TXT:
                    return storage.filename.read_text()
                case _:
                    return storage.filename.read_bytes()

        except AuditException as e:
            self.error(msg=Event.Read.value, uri=uri, error=e.reason)
            raise e
        except Exception as e:
            self.error(msg=Event.Read.value, uri=uri, error=str(e))
            raise AuditException(
                caller=self,
                error=str(e),
                uri=uri,
            )

    def write(
        self, uri: str, filename: str, ftype: FileType, data: object, **kwargs
    ) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__}.write() is not implemented. "
            "HTTP write operations are not supported by this driver. "
            "Use LocalFileSystemDriver for local persistence, or implement "
            "a dedicated upload driver for your target endpoint."
        )

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
            pass  # host is a hostname, not an IP literal — allow through

    def _safe_log_kwargs(self, **kwargs) -> dict:
        return {k: ("***" if k in _SENSITIVE_KWARGS else v) for k, v in kwargs.items()}

    def _build_request_kwargs(self, **kwargs) -> dict:
        """
        Assemble ``requests``-compatible kwargs from driver config and
        caller-supplied auth options.

        Supported auth kwargs
        ---------------------
        api_key    : str          → X-API-Key header
        token      : str          → Authorization: Bearer <token> header
        basic_auth : (str, str)   → requests auth tuple
        headers    : dict         → merged into request headers
        """
        request_kwargs: dict = {
            "timeout": self.timeout,
            "verify": self.verify_ssl,
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

        extra_headers = kwargs.get("headers", {})
        merged_headers.update(extra_headers)

        if merged_headers:
            request_kwargs["headers"] = merged_headers

        return request_kwargs

    def _download(self, uri: str, **kwargs) -> requests.Response:
        self.debug(
            msg=Event.Downloading.value,
            uri=uri,
            **self._safe_log_kwargs(**kwargs),
        )
        _uri = str(uri)
        request_kwargs = self._build_request_kwargs(**kwargs)
        _parsed = urlparse(_uri)
        _safe_uri = _parsed._replace(query="", fragment="").geturl()
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            uri=_safe_uri,
        )

        request_kwargs["stream"] = True
        response = requests.get(_uri, **request_kwargs)
        response.raise_for_status()

        chunks: list[bytes] = []
        received: int = 0
        for chunk in response.iter_content(chunk_size=65536):
            received += len(chunk)
            if received > _MAX_DOWNLOAD_BYTES:
                response.close()
                reason = f"Download exceeds limit of {_MAX_DOWNLOAD_BYTES} bytes: {_safe_uri}"
                self.error(msg=Event.Read.value, uri=_safe_uri, reason=reason)
                raise ValueError(reason)
            chunks.append(chunk)

        response._content = b"".join(chunks)
        return response

    def __repr__(self) -> str:
        path = getattr(self, "current_path", Path(self.local_path))
        return f"{self.__class__.__name__}:{str(path.resolve())}"
