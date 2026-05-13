# Module name: documents/file.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC
from datetime import datetime
from logging import NOTSET, Handler
from os import path, stat
from stat import filemode
from typing import Optional
from wattleflow.concrete import Document
from wattleflow.constants import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Documents                                                            #
# --------------------------------------------------------------------------- #


class FileDocument(Document[str], ABC):
    def __init__(self, filename: str, level: int = NOTSET, handler: Optional[Handler] = None):
        Document.__init__(self, content="", level=level, handler=handler)
        self.update_metadata(key="filename", value=filename)
        self.update_file_metadata()

    @property
    def filename(self) -> str:
        return str(self.metadata.get("filename", ""))

    @property
    def size(self) -> int:
        size: int = len(self.content)  # type: ignore
        if int(size) > 0:
            return size
        return len(str(self.content))

    def refresh_metadata(self):
        if path.exists(self.filename):
            self.update_file_metadata()
        else:
            self.warning(
                msg="Cannot refresh metadata.",
                filename=self.filename,
                error="File does not exist.",
            )

    def update_filename(self, filename: str) -> None:
        self.update_metadata(key="filename", value=filename)

    def update_file_metadata(self) -> None:
        if not path.exists(self.filename):
            self.warning(
                msg="File does not exist yet.",
                filename=self.filename,
                error="Metadata will be empty.",
            )
            return

        try:
            stats = stat(self.filename)
            self.update_metadata("size", stats.st_size)
            self.update_metadata("mtime", datetime.fromtimestamp(stats.st_mtime))
            self.update_metadata("atime", datetime.fromtimestamp(stats.st_atime))
            self.update_metadata("ctime", datetime.fromtimestamp(stats.st_ctime))
            self.update_metadata("file_permissions", filemode(stats.st_mode))
            self.update_metadata("uid", stats.st_uid)
            self.update_metadata("gid", stats.st_gid)
        except FileNotFoundError:
            self.error(
                msg="File not found!",
                filename=self.filename,
                error="Metadata will remain empty.",
            )
        except PermissionError:
            self.error(
                msg="Permission denied for file.",
                filename=self.filename,
                error="Cannot retrieve metadata.",
            )
        except Exception as e:
            self.error(
                msg="Unexpected error while accessing file.",
                file=self.filename,
                error=str(e),
            )

    def clean(self) -> None:
        self.debug(
            msg=Event.Clean.value,
            step=Event.Started.value,
            filename=self.filename,
        )
        self._metadata.clear()
        self._content = None
        self.debug(msg=Event.Clean.value, step=Event.Completed.value)

    def __del__(self) -> None:
        try:
            self.clean()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# endregion Documents                                                         #
# --------------------------------------------------------------------------- #
