# Module name: file.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from stat import filemode
from pathlib import Path


@dataclass
class FileClass:
    filename: Path

    @property
    def path(self) -> str:
        return str(self.filename.absolute())

    @property
    def size(self) -> int:
        if not self.filename.exists():
            return 0
        return self.filename.stat().st_size

    @property
    def mtime(self) -> datetime:
        if self.filename.exists():
            raise FileNotFoundError(str(self.filename))
        return datetime.fromtimestamp(self.filename.stat().st_mtime)

    @property
    def atime(self) -> datetime:
        return datetime.fromtimestamp(self.filename.stat().st_atime)

    @property
    def ctime(self) -> datetime:
        return datetime.fromtimestamp(self.filename.stat().st_ctime)

    @property
    def permissions(self) -> str:
        return filemode(self.filename.stat().st_mode)

    @property
    def uid(self) -> int:
        return self.filename.stat().st_uid

    @property
    def guid(self) -> int:
        return self.filename.stat().st_gid
