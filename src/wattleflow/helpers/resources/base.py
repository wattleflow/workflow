# Module name: helpers/resources/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
What a resource is, and a moment of them — `HLRQ-18`, `FRQ-PTN-18.1`.

Three questions answer for every resource alike: is it measurable, what is its
limit and where did that come from, and how much is in use. A resource the
standard library cannot see (`BR-08`) answers the first with False and is then
reported unmeasured — never as free.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["Resource", "ResourceSnapshot"]

# --------------------------------------------------------------------------- #
# region Resources                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Process resources at one instant; `None` means unmeasured, never zero."""

    at: float
    cpu_user: float
    cpu_system: float
    rss: int | None
    peak_rss: int | None
    throttled: int | None

    @property
    def cpu(self) -> float:
        return self.cpu_user + self.cpu_system


class Resource(ABC):
    """One resource, asked the same three questions as every other.

    Memory and CPU answer from the platform, a GPU from a library that may be
    absent, and storage per path — but the manager does not need to know which,
    which is what keeps the resolution free of a branch per resource.
    """

    RESOURCE: ClassVar[str] = ""

    #: Read once here rather than per resource: the narrowest source the
    #: platform offers is the same file tree for all of them.
    CGROUP: ClassVar[Path] = Path("/sys/fs/cgroup")

    @classmethod
    def read(cls, path: Path) -> str | None:
        """File contents, or None when the platform does not offer that file."""
        try:
            return path.read_text().strip()
        except OSError:
            return None

    @abstractmethod
    def available(self) -> bool:
        """False when this resource cannot be measured here at all."""

    @abstractmethod
    def limit(self) -> tuple[Any, str]:
        """(value, source). An unknown limit is `(None, "unknown")`, never a guess."""

    @abstractmethod
    def used(self) -> Any | None:
        """Current usage, or None when unmeasured."""


# --------------------------------------------------------------------------- #
# endregion Resources                                                         #
# --------------------------------------------------------------------------- #
