# Module name: helpers/resources/cpu.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Processor time: the container's quota before affinity, then the host."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import os
from typing import ClassVar
from wattleflow.helpers.resources.base import Resource
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["ResourceCpu"]

# --------------------------------------------------------------------------- #
# region Resource                                                             #
# --------------------------------------------------------------------------- #


class ResourceCpu(Resource):
    """Processor time available to this process, and how much it has spent."""

    RESOURCE: ClassVar[str] = "cpu"

    def available(self) -> bool:
        return True

    def limit(self) -> tuple[float | None, str]:
        text = self.read(self.CGROUP / "cpu.max")
        if text:
            quota, _, period = text.partition(" ")
            if quota != "max" and period:
                return int(quota) / int(period), "cgroup cpu.max"
        # Affinity before `cpu_count`: a process pinned to two cores of a
        # sixty-core host is limited by the pinning, not by the machine.
        if hasattr(os, "sched_getaffinity"):
            return float(len(os.sched_getaffinity(0))), "affinity"
        count = os.cpu_count()
        return (float(count), "host") if count else (None, "unknown")

    def used(self) -> float:
        times = os.times()
        return times.user + times.system

    def throttled(self) -> int | None:
        """How often the container was held back, or None outside a cgroup."""
        text = self.read(self.CGROUP / "cpu.stat")
        for line in (text or "").splitlines():
            key, _, value = line.partition(" ")
            if key == "nr_throttled":
                return int(value)
        return None


# --------------------------------------------------------------------------- #
# endregion Resource                                                          #
# --------------------------------------------------------------------------- #
