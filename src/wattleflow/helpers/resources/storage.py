# Module name: helpers/resources/storage.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Storage behind one write path — the only resource that is not process-wide."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import shutil
from pathlib import Path
from typing import ClassVar
from wattleflow.helpers.resources.base import Resource
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["ResourceStorage"]

# --------------------------------------------------------------------------- #
# region Resource                                                             #
# --------------------------------------------------------------------------- #


class ResourceStorage(Resource):
    """The file system holding one path; bound to that path, unlike the others."""

    RESOURCE: ClassVar[str] = "storage"

    def __init__(self, path: str) -> None:
        self.path = path

    def usage(self) -> tuple[int, int] | None:
        """(free, total) bytes, or None when the path cannot be reached."""
        # A run may declare a write path before anything creates it, so walk up
        # to the nearest parent that exists: the file system is the same one.
        probe = Path(self.path)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            usage = shutil.disk_usage(probe)
        except OSError:
            return None
        return usage.free, usage.total

    def available(self) -> bool:
        return self.usage() is not None

    def limit(self) -> tuple[int | None, str]:
        usage = self.usage()
        return (usage[1], "filesystem") if usage else (None, "unknown")

    def used(self) -> int | None:
        usage = self.usage()
        return (usage[1] - usage[0]) if usage else None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path!r})"


# --------------------------------------------------------------------------- #
# endregion Resource                                                          #
# --------------------------------------------------------------------------- #
