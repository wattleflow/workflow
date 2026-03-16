# Module name: file_storage.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

import hashlib
import logging
import os

from abc import ABC
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from wattleflow.concrete import AuditLogger
from wattleflow.constants.enums import Event


class FileStorage(AuditLogger, ABC):
    def __init__(
        self,
        local_path: str,
        uri: str,
        create: bool,
        normalised: bool = False,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ):
        AuditLogger.__init__(self, level=level, handler=handler, **kwargs)
        self.debug(
            msg=Event.Constructor.value,
            local_path=local_path,
            uri=uri,
            create=create,
            normalised=normalised,
            level=level,
            handler=handler,
            **kwargs,
        )

        self._filename: Optional[Path] = None
        self._local_path: Path = Path(local_path).resolve()
        self._origin: Path = Path(uri)
        self._create: bool = create
        self._normalised: bool = normalised

        if not self._local_path.is_dir() and not create:
            raise FileNotFoundError(
                f"Path doesn't exist or is not a directory: {str(self._local_path)}"
            )

        if create and self._local_path.exists() is False:
            self._local_path.mkdir(parents=True, exist_ok=True)

        name = self.digest if normalised else self._origin.name

        _candidate = self._local_path / name
        if not _candidate.resolve().is_relative_to(self._local_path):
            reason = f"Filename escapes local_path: {uri!r}"
            self.error(msg=Event.Constructor.value, reason=reason, uri=uri)
            raise PermissionError(reason)

        self._filename = _candidate

    @property
    def digest(self) -> str:
        digest = hashlib.sha256(str(self.origin).encode()).hexdigest()[:16]
        suffix = Path(urlparse(str(self.origin)).path).suffix or ".bin"
        return f"{digest}{suffix}"

    @property
    def filename(self) -> Path:
        return self._filename

    @property
    def origin(self) -> Path:
        return self._origin

    @property
    def size(self) -> int:
        if self._filename.exists():
            return os.stat(self._filename.absolute()).st_size
        return 0

    @property
    def uri(self) -> str:
        return self.filename.as_uri()

    def with_suffix(self, suffix: str) -> Path:
        return self._filename.with_suffix(suffix)

    def with_dir(self, directory=None, mkdir=True) -> Path:
        subdir = directory if directory else self._filename.stem
        out_dir = self._local_path.joinpath(subdir)
        if mkdir:
            out_dir.mkdir(parents=True, exist_ok=True)

        return out_dir.joinpath(self._filename.name)
