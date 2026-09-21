# Module name: helpers/resources/manager.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
ResourceManager — what each resource's limit is, and where it came from.

The construction-time half of `FRQ-PTN-18.1`: this settles the boundaries once,
when the workflow is built, and the Monitor watches against them for the rest of
the pass. Separating them is what lets a limit be DECLARED at all — a monitor
that discovers its own limits has nowhere to receive one.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import os
import time
from typing import Any, Iterable, Mapping
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
from wattleflow.helpers.resources.base import Resource, ResourceSnapshot
from wattleflow.helpers.resources.cpu import ResourceCpu
from wattleflow.helpers.resources.memory import ResourceMemory
from wattleflow.helpers.resources.storage import ResourceStorage
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["ResourceManager"]

# --------------------------------------------------------------------------- #
# region Manager                                                              #
# --------------------------------------------------------------------------- #


class ResourceManager(Wattleflow):
    """Resolve and announce the limits a pass will be measured against."""

    def __init__(
        self,
        limits: Mapping[str, Any] | None = None,
        thresholds: Mapping[str, Any] | None = None,
        extensions: Iterable[Resource] = (),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._declared = dict(limits or {})
        self._thresholds = dict(thresholds or {})
        self.memory = ResourceMemory()
        self.cpu = ResourceCpu()
        # A resource the standard library cannot see arrives from the
        # distribution allowed to import its library (`BR-08`).
        self._resources: dict[str, Resource] = {
            self.memory.RESOURCE: self.memory,
            self.cpu.RESOURCE: self.cpu,
            **{extension.RESOURCE: extension for extension in extensions},
        }
        self._resolved: dict[str, tuple[Any, str]] = {}

    @property
    def resources(self) -> tuple[str, ...]:
        return tuple(self._resources)

    def limit(self, name: str) -> tuple[Any, str]:
        """(value, source) for one resource, resolved once and remembered."""
        if name not in self._resolved:
            self._resolved[name] = self._resolve(name)
        return self._resolved[name]

    def limits(self) -> dict[str, tuple[Any, str]]:
        return {name: self.limit(name) for name in self._resources}

    def _resolve(self, name: str) -> tuple[Any, str]:
        # Declared beats discovered: an operator who states a ceiling knows
        # something the platform does not, such as a quota enforced elsewhere.
        if name in self._declared:
            return self._declared[name], "declared"
        resource = self._resources.get(name)
        if resource is None or not resource.available():
            return None, "unmeasured"
        return resource.limit()

    def snapshot(self) -> ResourceSnapshot:
        """Process resources at one instant, for the Monitor to difference."""
        times = os.times()
        return ResourceSnapshot(
            at=time.perf_counter(),
            cpu_user=times.user,
            cpu_system=times.system,
            rss=self.memory.used(),
            peak_rss=self.memory.peak(),
            throttled=self.cpu.throttled(),
        )

    def storage(self, path: str) -> ResourceStorage:
        return ResourceStorage(path)

    def announce(self, paths: Iterable[str] = ()) -> None:
        """EV01: each limit and its source, once, when the workflow is built (BR-01)."""
        try:
            for name in self._resources:
                limit, source = self.limit(name)
                self.debug(
                    msg=Event.Configure,
                    target="limit",
                    resource=name,
                    limit=limit,
                    limit_source=source,
                    threshold=self._thresholds.get(name),
                )
                if limit is None and name in self._thresholds:
                    self.warning(
                        msg=Event.Configure,
                        target="limit",
                        resource=name,
                        reason="limit unknown; the relative threshold is not applied",
                    )
            for path in sorted({str(p) for p in paths if p}):
                limit, source = self.storage(path).limit()
                self.debug(
                    msg=Event.Configure,
                    target="limit",
                    resource="storage",
                    path=path,
                    limit=limit,
                    limit_source=source,
                    threshold=self._thresholds.get("storage"),
                )
        except Exception as e:
            # Measuring must not be what stops a workflow (`BR-07`).
            self.warning(msg=Event.Configure, target="limit", error=str(e))


# --------------------------------------------------------------------------- #
# endregion Manager                                                           #
# --------------------------------------------------------------------------- #
