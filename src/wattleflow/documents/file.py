# Module Name: documents/file.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains FileDocument class.

from stat import filemode
from os import path, stat
from logging import NOTSET, Handler
from datetime import datetime
from typing import Optional
from wattleflow.concrete import Document, AuditLogger


# Document based on file, with automatic retrieval of metadata
class FileDocument(Document[str], AuditLogger):
    def __init__(self, file_path: str, level: int = NOTSET, handler: Optional[Handler] = None):
        Document.__init__(self, level=level, handler=handler)
        self._metadata = {}
        self.file_path = file_path
        self.update_metadata()

    @property
    def filename(self) -> str:
        return self.file_path

    @property
    def metadata(self) -> dict:
        return self._metadata

    def refresh_metadata(self):
        if path.exists(self.filename):
            self.update_metadata()
        else:
            self.warning(
                msg="Cannot refresh metadata.",
                filename=self.filename,
                error="File does not exist.",
            )

    def update_filename(self, file_path):
        self._file_path = file_path
        self.update_metadata()

    def update_metadata(self) -> None:
        if not path.exists(self.filename):
            self.warning(
                msg="File does not exist yet.",
                filename=self.file_path,
                error="Metadata will be empty.",
            )
            return

        try:
            stats = stat(self.file_path)
            self._metadata = {
                "size": stats.st_size,
                "mtime": datetime.fromtimestamp(stats.st_mtime),
                "atime": datetime.fromtimestamp(stats.st_atime),
                "ctime": datetime.fromtimestamp(stats.st_ctime),
                "file_permissions": filemode(stats.st_mode),
                "uid": stats.st_uid,
                "gid": stats.st_gid,
            }
        except FileNotFoundError:
            self.error(
                msg="File not found!",
                filename=self.file_path,
                error="Metadata will remain empty.",
            )
        except PermissionError:
            self.error(
                msg="Permission denied for file.",
                filename=self.file_path,
                error="Cannot retrieve metadata.",
            )
        except Exception as e:
            self.error(
                msg="Unexpected error while accessing file.",
                file=self.file_path,
                error=str(e),
            )
