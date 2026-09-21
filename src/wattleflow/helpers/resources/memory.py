# Module name: helpers/resources/memory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Working memory: the container's limit before the host's, usage as RSS."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import ClassVar
from wattleflow.helpers.resources.base import Resource

# Absent on Windows, where the peak is then reported unmeasured. The name is the
# standard library's, not this package: an absolute import reaches past us.
try:
    import resource as rusage
except ImportError:
    rusage = None  # type: ignore[assignment]
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["ResourceMemory"]

# --------------------------------------------------------------------------- #
# region Resource                                                             #
# --------------------------------------------------------------------------- #


class ResourceMemory(Resource):
    """Working memory of this process, against the narrowest declared ceiling."""

    RESOURCE: ClassVar[str] = "memory"
    STATM: ClassVar[Path] = Path("/proc/self/statm")

    def available(self) -> bool:
        return self.used() is not None

    def limit(self) -> tuple[int | None, str]:
        text = self.read(self.CGROUP / "memory.max")
        if text and text != "max":
            return int(text), "cgroup memory.max"
        try:
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"), "host"
        except (ValueError, OSError, AttributeError):
            return None, "unknown"

    def used(self) -> int | None:
        text = self.read(self.STATM)
        if not text:
            return None
        return int(text.split()[1]) * os.sysconf("SC_PAGE_SIZE")

    def peak(self) -> int | None:
        """Highest RSS this process reached, as the platform reports it."""
        if rusage is None:
            return None
        highest = rusage.getrusage(rusage.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB, macOS bytes.
        return highest if sys.platform == "darwin" else highest * 1024


# --------------------------------------------------------------------------- #
# endregion Resource                                                          #
# --------------------------------------------------------------------------- #
