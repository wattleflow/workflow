# Module Name: documents/file.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains FileDocument class.

from stat import filemode
from os import path, stat
from logging import WARNING
from datetime import datetime
from wattleflow.concrete import Document, AuditLogger


# Document based on file, with automatic retrieval of metadata
class FileDocument(Document[str], AuditLogger):
    def __init__(self, filename: str):
        Document.__init__(self=self)
        AuditLogger.__init__(self, level=WARNING)
        self._metadata = {}
        self._filename = filename
        self.update_metadata()

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def metadata(self) -> dict:
        return self._metadata

    def refresh_metadata(self):
        if path.exists(self.filename):
            self.update_metadata()
        else:
            self.warning(f"Cannot refresh metadata: {self.filename} does not exist.")
            # print(f"[WARNING] Cannot refresh metadata: {self.filename} does not exist.")

    def update_filename(self, filename):
        self._filename = filename
        self.update_metadata()

    def update_metadata(self) -> None:
        if not path.exists(self.filename):
            self.warning(f"File does not exist yet: {self.filename}. Metadata will be empty.")
            # print(
            #     f"[WARNING] File does not exist yet: {self.filename}. Metadata will be empty."
            # )
            return

        try:
            stats = stat(self.filename)
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
            self.error(f"File not found: {self.filename}. Metadata will remain empty.")
            # print(
            #     f"[ERROR] File not found: {self.filename}. Metadata will remain empty."
            # )
        except PermissionError:
            self.error(f"[ERROR] Permission denied for file: {self.filename}. Cannot retrieve metadata.")
            # print(
            #     f"[ERROR] Permission denied for file: {self.filename}. Cannot retrieve metadata."
            # )
        except Exception as e:
            self.error("Unexpected error while accessing {self.filename}: {e}")
            # print(f"[ERROR] Unexpected error while accessing {self.filename}: {e}")
