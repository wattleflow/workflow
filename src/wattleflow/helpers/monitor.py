# Module name: helpers/monitor.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Central measurement — `FRQ-MET-01` (time, volume) and `FRQ-PTN-18.1` (resources).

The audit record is the event (v0.0.1.14, DR-WFL-031 v3). Every component already
writes `step=Started` / `step=Completed|Failed` around its operations and the
processor writes one `Processed` record per document; `Audit._log_msg` hands
those records to the monitor BEFORE the level gate, so measurement works at
`INFO` and a component carries no measurement code at all. Nothing is wrapped.

Hot path: one dict lookup per record without a monitor, one method call with
one. Spans are aggregated on close — no object per call, memory does not grow
with the volume of work. Resources are sampled by time, never per item.

Standard library only (`NFRQ-SEC-03`); a fault in the measurement never
reaches the work being measured (`HLRQ-18` BR-07).
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import os
import shutil
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from time import perf_counter_ns
from typing import Any, ClassVar, Iterable, Mapping
from wattleflow.core import IBlackboard, IDriver, IPipeline, IProcessor, IRepository, IStrategy
from wattleflow.enums.event import Event
from wattleflow.enums.metric import Measure, MetricKind
from wattleflow.helpers.audit import Audit
from wattleflow.helpers.metrics import MetricSample

try:
    import resource
except ImportError:  # Windows: the peak RSS is then reported as unmeasured
    resource = None  # type: ignore[assignment]
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["Monitor", "MonitorLevel", "ResourceExtension", "ResourceProbe", "ResourceSnapshot"]

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


class ResourceProbe:
    """Reads limits and usage from the narrowest source the platform offers."""

    CGROUP: ClassVar[Path] = Path("/sys/fs/cgroup")
    STATM: ClassVar[Path] = Path("/proc/self/statm")

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text().strip()
        except OSError:
            return None

    @classmethod
    def rss(cls) -> int | None:
        text = cls._read(cls.STATM)
        if not text:
            return None
        return int(text.split()[1]) * os.sysconf("SC_PAGE_SIZE")

    @staticmethod
    def peak_rss() -> int | None:
        if resource is None:
            return None
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB, macOS bytes.
        return peak if sys.platform == "darwin" else peak * 1024

    @classmethod
    def throttled(cls) -> int | None:
        text = cls._read(cls.CGROUP / "cpu.stat")
        for line in (text or "").splitlines():
            key, _, value = line.partition(" ")
            if key == "nr_throttled":
                return int(value)
        return None

    @classmethod
    def memory_limit(cls) -> tuple[int | None, str]:
        text = cls._read(cls.CGROUP / "memory.max")
        if text and text != "max":
            return int(text), "cgroup memory.max"
        try:
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"), "host"
        except (ValueError, OSError, AttributeError):
            return None, "unknown"

    @classmethod
    def cpu_limit(cls) -> tuple[float | None, str]:
        text = cls._read(cls.CGROUP / "cpu.max")
        if text:
            quota, _, period = text.partition(" ")
            if quota != "max" and period:
                return int(quota) / int(period), "cgroup cpu.max"
        if hasattr(os, "sched_getaffinity"):
            return float(len(os.sched_getaffinity(0))), "affinity"
        count = os.cpu_count()
        return (float(count), "host") if count else (None, "unknown")

    @staticmethod
    def storage(path: str) -> tuple[int, int] | None:
        """(free, total) bytes on the file system holding `path`."""
        probe = Path(path)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            usage = shutil.disk_usage(probe)
        except OSError:
            return None
        return usage.free, usage.total

    @classmethod
    def snapshot(cls) -> ResourceSnapshot:
        times = os.times()
        return ResourceSnapshot(
            at=time.perf_counter(),
            cpu_user=times.user,
            cpu_system=times.system,
            rss=cls.rss(),
            peak_rss=cls.peak_rss(),
            throttled=cls.throttled(),
        )


class ResourceExtension(ABC):
    """A resource the standard library cannot see (`HLRQ-18` BR-08), e.g. a GPU.

    Lives in the distribution that may import the library; `available` is False
    when that library is absent, and the resource is then reported unmeasured.
    """

    RESOURCE: ClassVar[str] = "gpu"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def limit(self) -> tuple[int | None, str]: ...

    @abstractmethod
    def used(self) -> int | None: ...


# --------------------------------------------------------------------------- #
# endregion Resources                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Monitor                                                              #
# --------------------------------------------------------------------------- #


class MonitorLevel:
    """What is measured, per role; the same idea as a logger level."""

    OFF: ClassVar[int] = 0  # no monitor at all: zero cost
    SUMMARY: ClassVar[int] = 1  # cycles and resources only
    OPERATIONS: ClassVar[int] = 2  # every Started/Completed pair, aggregated
    TRACE: ClassVar[int] = 3  # plus individual spans, bounded
    NAMES: ClassVar[dict[str, int]] = {"OFF": 0, "SUMMARY": 1, "OPERATIONS": 2, "TRACE": 3}

    @classmethod
    def resolve(cls, value: Any) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3:
            return value
        level = cls.NAMES.get(str(value or "").strip().upper())
        if level is None:
            raise ValueError(
                f"unknown monitoring level {value!r}; expected one of {list(cls.NAMES)}"
            )
        return level


_OPENING: frozenset[str] = frozenset({Event.Started, Event.Starting})
_CLOSING: frozenset[str] = frozenset({Event.Completed, Event.Failed})
_FAILED: str = Event.Failed
_BY_FIELD: Mapping[str, Measure] = Measure.by_field()

# Aggregated row per (component, operation): calls, failed, ns, exclusive ns, max ns, units.
_CALLS, _FAILS, _NS, _EXCLUSIVE, _MAX, _UNITS = range(6)


class Monitor(Audit):
    """Observer of audit records: spans, units, cycles, resource samples, one report per pass."""

    ROLES: ClassVar[tuple[tuple[str, type], ...]] = (
        ("processor", IProcessor),
        ("pipeline", IPipeline),
        ("blackboard", IBlackboard),
        ("repository", IRepository),
        ("strategy", IStrategy),
        ("driver", IDriver),
    )
    OTHER: ClassVar[str] = "other"  # documents, formatters, managers, connections
    #: Resources a threshold may name; a share of the limit, 0 < t <= 1 (BR-03).
    THRESHOLDS: ClassVar[frozenset[str]] = frozenset({"memory", "storage", "gpu"})
    DEFAULT_INTERVAL: ClassVar[float] = 1.0  # seconds between resource samples
    TRACE_LIMIT: ClassVar[int] = 10_000
    CYCLE_LIMIT: ClassVar[int] = 10_000
    HOTSPOTS: ClassVar[int] = 5

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._lock = threading.Lock()
        self._level: int = MonitorLevel.SUMMARY
        self._roles: dict[str, int] = {}
        self._thresholds: dict[str, float] = {}
        self._extensions: list[ResourceExtension] = []
        self._limits: dict[str, tuple[Any, str]] = {}
        self._interval: float = self.DEFAULT_INTERVAL
        self._sinks: list[Any] = []
        self._labels: dict[str, str] = {}
        self.reset()

    # region Configuration

    def configure(
        self,
        level: Any = None,
        roles: Mapping[str, Any] | None = None,
        thresholds: Mapping[str, Any] | None = None,
        extensions: Iterable[ResourceExtension] = (),
        interval: Any = None,
        sinks: Iterable[Any] = (),
        labels: Mapping[str, Any] | None = None,
    ) -> None:
        """Declared levels, thresholds, extensions and sinks; an undeclared key is reported."""
        if level is not None:
            self._level = MonitorLevel.resolve(level)
        self._roles = {}
        known = {role for role, _ in self.ROLES} | {self.OTHER}
        for role, value in dict(roles or {}).items():
            if role not in known:
                self.warning(
                    msg=Event.Configure, target="role", role=str(role), reason="unknown"
                )
                continue
            self._roles[role] = MonitorLevel.resolve(value)
        self._thresholds = {}
        for resource_name, value in dict(thresholds or {}).items():
            try:
                share = float(value)
            except (TypeError, ValueError):
                share = -1.0
            if resource_name not in self.THRESHOLDS or not 0 < share <= 1:
                self.warning(
                    msg=Event.Configure,
                    target="threshold",
                    resource=str(resource_name),
                    value=str(value),
                    reason="not a declared resource or not a share in (0, 1]",
                )
                continue
            self._thresholds[resource_name] = share
        self._extensions = list(extensions)
        self._limits = {}
        if interval is not None:
            self._interval = max(float(interval), 0.0)
        # A sink formats for one destination and a driver ships it (FRQ-MET-01 A5);
        # the monitor only hands over the samples, once, after the report.
        self._sinks = list(sinks)
        # Constant labels on every exported series: the workflow this pass belongs to.
        self._labels = {str(k): str(v) for k, v in (labels or {}).items() if v not in (None, "")}
        self._levels = {}

    @property
    def level(self) -> int:
        return self._level

    @property
    def hook(self) -> Any:
        """What `Audit.observe` installs: the summary observer only looks at unit boundaries."""
        wants_operations = self._level >= MonitorLevel.OPERATIONS or any(
            value >= MonitorLevel.OPERATIONS for value in self._roles.values()
        )
        return self.observe if wants_operations else self.observe_summary

    def _level_for(self, cls: type) -> tuple[int, str]:
        role = next((name for name, interface in self.ROLES if issubclass(cls, interface)), None)
        if role is None:
            # Everything else is summary-only unless the configuration says so.
            return self._roles.get(self.OTHER, min(self._level, MonitorLevel.SUMMARY)), self.OTHER
        return self._roles.get(role, self._level), role

    def _limit(self, resource_name: str) -> tuple[Any, str]:
        if resource_name not in self._limits:
            if resource_name == "memory":
                self._limits[resource_name] = ResourceProbe.memory_limit()
            elif resource_name == "cpu":
                self._limits[resource_name] = ResourceProbe.cpu_limit()
            else:
                extension = self._extension(resource_name)
                measured = extension is not None and extension.available()
                self._limits[resource_name] = (
                    extension.limit() if measured else (None, "unmeasured")
                )
        return self._limits[resource_name]

    def _extension(self, resource_name: str) -> ResourceExtension | None:
        return next((e for e in self._extensions if e.RESOURCE == resource_name), None)

    def announce(self, paths: Iterable[str] = ()) -> None:
        """EV01: each limit and its source, once, when the workflow is built (BR-01)."""
        try:
            for resource_name in ("memory", "cpu", "gpu"):
                limit, source = self._limit(resource_name)
                self.debug(
                    msg=Event.Configure,
                    target="limit",
                    resource=resource_name,
                    limit=limit,
                    limit_source=source,
                    threshold=self._thresholds.get(resource_name),
                )
                if limit is None and resource_name in self._thresholds:
                    self.warning(
                        msg=Event.Configure,
                        target="limit",
                        resource=resource_name,
                        reason="limit unknown; the relative threshold is not applied",
                    )
            for path in sorted({str(p) for p in paths if p}):
                usage = ResourceProbe.storage(path)
                self.debug(
                    msg=Event.Configure,
                    target="limit",
                    resource="storage",
                    path=path,
                    limit=usage[1] if usage else None,
                    limit_source="file system" if usage else "unknown",
                    threshold=self._thresholds.get("storage"),
                )
        except Exception:
            self._faults += 1

    # endregion Configuration

    # region Observation (hot path)

    def observe_summary(
        self, owner: object, msg: str, step: str | None, fields: Mapping[str, Any]
    ) -> None:
        """SUMMARY: only the processor's `Processed` record matters."""
        if step is None:
            try:
                cls = type(owner)
                entry = self._levels.get(cls)
                if entry is None:
                    entry = self._levels[cls] = self._level_for(cls)
                if entry[0] and entry[1] == "processor":
                    self._cycle()
            except Exception:
                self._faults += 1

    def observe(self, owner: object, msg: str, step: str | None, fields: Mapping[str, Any]) -> None:
        """One audit record, before its level gate. Called by `Audit._log_msg`."""
        try:
            cls = type(owner)
            entry = self._levels.get(cls)
            if entry is None:
                entry = self._levels[cls] = self._level_for(cls)
            level, role = entry
            if step is None:
                # A `Processed` record: the processor closed a unit of work.
                if level and role == "processor":
                    self._cycle()
                return
            if level < MonitorLevel.OPERATIONS:
                return
            tid = get_ident()
            stack = self._stacks.get(tid)
            if stack is None:
                stack = self._stacks[tid] = []
            if step in _OPENING:
                # [component, operation, started ns, child ns]
                stack.append([cls.__name__, msg, perf_counter_ns(), 0])
            elif step in _CLOSING:
                self._close(stack, cls.__name__, msg, step == _FAILED, fields, level)
        except Exception:
            self._faults += 1

    def _close(
        self,
        stack: list,
        component: str,
        msg: str,
        failed: bool,
        fields: Mapping[str, Any],
        level: int,
    ) -> None:
        end = perf_counter_ns()
        if stack and stack[-1][0] == component and stack[-1][1] == msg:
            frame = stack.pop()
        else:
            index = next(
                (
                    i
                    for i in range(len(stack) - 1, -1, -1)
                    if stack[i][0] == component and stack[i][1] == msg
                ),
                -1,
            )
            if index < 0:
                self._unpaired += 1
                self._defects[(component, msg, "close without open")] += 1
                return
            frame = stack[index]
            # The frames above never closed: the code's defect, counted and named, not hidden.
            for above in stack[index + 1 :]:
                self._defects[(above[0], above[1], "open without close")] += 1
            self._dropped += len(stack) - index - 1
            del stack[index:]
        elapsed = end - frame[2]
        exclusive = elapsed - frame[3]
        if stack:
            stack[-1][3] += elapsed
        key = (component, msg)
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                row = self._rows[key] = [0, 0, 0, 0, 0, {}]
            row[_CALLS] += 1
            row[_FAILS] += failed
            row[_NS] += elapsed
            row[_EXCLUSIVE] += exclusive if exclusive > 0 else 0
            if elapsed > row[_MAX]:
                row[_MAX] = elapsed
            units = row[_UNITS]
            for name, value in fields.items():
                measure = _BY_FIELD.get(name)
                if measure is not None and type(value) is int:
                    units[measure] = units.get(measure, 0) + value
        if level >= MonitorLevel.TRACE:
            self._trace.append((component, msg, frame[2], elapsed, exclusive, failed))

    def _cycle(self) -> None:
        now = time.perf_counter()
        self._documents += 1
        if self._cycle_at is not None:
            elapsed = now - self._cycle_at
            self._cycle_ns += elapsed
            if len(self._cycles) < self.CYCLE_LIMIT:
                self._cycles.append(elapsed)
        self._cycle_at = now
        if now - self._sampled_at >= self._interval:
            self._sample("cycle")

    # endregion Observation

    # region Thresholds

    def _place(self) -> str | None:
        stack = self._stacks.get(get_ident())
        return f"{stack[-1][0]}.{stack[-1][1]}" if stack else None

    def _cross(
        self,
        key: str,
        share: float | None,
        boundary: str,
        used: int,
        limit: int,
        limit_source: str,
        path: str | None = None,
    ) -> None:
        """WARNING once per crossing; re-armed when the share falls back (BR-04)."""
        resource_name = key.split(":", 1)[0]
        threshold = self._thresholds.get(resource_name)
        if share is None or threshold is None:
            return
        if share >= threshold and key not in self._above:
            self._above.add(key)
            self._alerts += 1
            self.warning(
                msg=Event.Check,
                target="resource",
                share=round(share, 4),
                threshold=threshold,
                boundary=boundary,
                cycle=self._documents,
                place=self._place(),
                resource=resource_name,
                path=path,
                used=used,
                limit=limit,
                limit_source=limit_source,
            )
        elif share < threshold:
            self._above.discard(key)

    def _check(self, boundary: str, previous: ResourceSnapshot | None) -> None:
        current = self._last
        if current is None:
            return
        limit, source = self._limit("memory")
        if limit and current.rss is not None:
            self._cross("memory", current.rss / limit, boundary, current.rss, limit, source)
        for path in self._storage:
            usage = ResourceProbe.storage(path)
            if usage:
                free, total = usage
                self._cross(
                    f"storage:{path}", (total - free) / total, boundary,
                    total - free, total, "file system", path=path,
                )
        extension = self._extension("gpu")
        if extension and extension.available():
            used = extension.used()
            gpu_limit, gpu_source = self._limit("gpu")
            if used is not None and gpu_limit:
                self._cross("gpu", used / gpu_limit, boundary, used, gpu_limit, gpu_source)
        if (
            previous is not None
            and previous.throttled is not None
            and current.throttled is not None
            and current.throttled > previous.throttled
        ):
            # A signal, not a threshold: throttling is the bottleneck itself (BR-04).
            self._alerts += 1
            self.warning(
                msg=Event.Check,
                target="resource",
                resource="cpu",
                throttled=current.throttled - previous.throttled,
                boundary=boundary,
                cycle=self._documents,
                place=self._place(),
            )

    # endregion Thresholds

    # region Pass

    @property
    def running(self) -> bool:
        return self._baseline is not None

    def begin(self, paths: Iterable[str] = ()) -> None:
        self.reset()
        try:
            self._baseline = self._last = ResourceProbe.snapshot()
            self._sampled_at = time.perf_counter()
            self._peak_rss = self._baseline.rss
            for path in {str(p) for p in paths if p}:
                usage = ResourceProbe.storage(path)
                if usage is not None:
                    self._storage[path] = usage
        except Exception:
            self._baseline = None
            self._faults += 1

    def boundary(self, name: str) -> None:
        """Sample resources now, whatever the interval (tests, explicit boundaries)."""
        self._sample(name)

    def _sample(self, boundary: str) -> None:
        try:
            previous, self._last = self._last, ResourceProbe.snapshot()
            self._sampled_at = self._last.at
            self._samples += 1
            if self._last.rss is not None:
                self._peak_rss = max(self._peak_rss or 0, self._last.rss)
                self._rss_track.append((self._documents, self._last.rss))
            self._check(boundary, previous)
        except Exception:
            self._faults += 1

    def end(self) -> None:
        """Close the pass and write its report."""
        try:
            if self._baseline is None:
                return
            self._sample("pass")
            self._report(self._baseline, self._last)
            self._publish()
        except Exception as e:
            self.warning(msg=Event.Completed, target="measure", error=str(e))

    def _publish(self) -> None:
        """Every sink is visited; a failing destination is reported, never raised (BR-07)."""
        if not self._sinks:
            return
        samples = self.samples()
        for sink in self._sinks:
            name = type(sink).__name__
            try:
                published = bool(sink.publish(samples))
            except Exception as e:
                self.warning(msg=Event.Completed, target="export", sink=name, error=str(e))
                continue
            self.info(msg=Event.Completed, target="export", sink=name, published=published,
                      samples=len(samples))

    def reset(self) -> None:
        self._levels: dict[type, tuple[int, str]] = {}
        self._stacks: dict[int, list] = {}
        self._rows: dict[tuple[str, str], list] = {}
        self._trace: deque = deque(maxlen=self.TRACE_LIMIT)
        self._storage: dict[str, tuple[int, int]] = {}
        self._rss_track: list[tuple[int, int]] = []
        self._cycles: list[float] = []
        self._cycle_ns = 0.0
        self._cycle_at: float | None = None
        self._sampled_at = 0.0
        self._baseline: ResourceSnapshot | None = None
        self._last: ResourceSnapshot | None = None
        self._peak_rss: int | None = None
        self._documents = 0
        self._samples = 0
        self._unpaired = 0
        self._dropped = 0
        self._faults = 0
        self._alerts = 0
        self._above: set[str] = set()
        self._defects: dict[tuple[str, str, str], int] = defaultdict(int)

    # endregion Pass

    # region Report

    @staticmethod
    def _units(units: Mapping[Measure, int]) -> str | None:
        merged: dict[str, int] = defaultdict(int)
        for measure, amount in units.items():
            merged[measure.unit] += amount
        return ", ".join(f"{unit}={amount}" for unit, amount in sorted(merged.items())) or None

    def rows(self) -> dict[tuple[str, str], list]:
        """Aggregated operations of the current pass (read-only view for reports and sinks)."""
        with self._lock:
            return {key: list(row) for key, row in self._rows.items()}

    @staticmethod
    def _percentile(values: list[float], share: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        return ordered[min(int(share * (len(ordered) - 1)), len(ordered) - 1)]

    def _memory_growth_per_document(self) -> int | None:
        """Slope of RSS over documents (bytes/document) — an indicator, not proof of a leak."""
        track = self._rss_track
        if len(track) < 3 or track[-1][0] == track[0][0]:
            return None
        n = len(track)
        mean_x = sum(x for x, _ in track) / n
        mean_y = sum(y for _, y in track) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in track)
        den = sum((x - mean_x) ** 2 for x, _ in track)
        return int(num / den) if den else None

    def _report(self, start: ResourceSnapshot, end: ResourceSnapshot) -> None:
        wall = end.at - start.at
        documents = self._documents
        cycles = self._cycles
        self.info(
            msg=Event.Completed,
            target="run",
            wall_seconds=round(wall, 3),
            documents=documents,
            documents_per_minute=round(documents / wall * 60, 2) if wall > 0 else None,
            cycle_min=round(min(cycles), 4) if cycles else None,
            cycle_median=round(self._percentile(cycles, 0.5), 4) if cycles else None,
            cycle_p95=round(self._percentile(cycles, 0.95), 4) if cycles else None,
            cycle_max=round(max(cycles), 4) if cycles else None,
        )

        memory_limit, memory_source = self._limit("memory")
        self.info(
            msg=Event.Completed,
            target="resource",
            resource="memory",
            rss_start=start.rss,
            rss_end=end.rss,
            rss_peak=self._peak_rss,
            process_peak=end.peak_rss,
            growth=(end.rss - start.rss) if end.rss is not None and start.rss is not None else None,
            growth_per_document=self._memory_growth_per_document(),
            share_of_limit=(
                round(self._peak_rss / memory_limit, 4) if memory_limit and self._peak_rss else None
            ),
            limit=memory_limit,
            limit_source=memory_source,
        )

        cpu_limit, cpu_source = self._limit("cpu")
        cpu = end.cpu - start.cpu
        throttled = (
            end.throttled - start.throttled
            if end.throttled is not None and start.throttled is not None
            else None
        )
        self.info(
            msg=Event.Completed,
            target="resource",
            resource="cpu",
            user_seconds=round(end.cpu_user - start.cpu_user, 3),
            system_seconds=round(end.cpu_system - start.cpu_system, 3),
            utilisation=round(cpu / wall, 4) if wall > 0 else None,
            cpu_per_document=round(cpu / documents, 4) if documents else None,
            throttled=throttled,
            limit=cpu_limit,
            limit_source=cpu_source,
        )

        for path, (free_start, total) in sorted(self._storage.items()):
            now = ResourceProbe.storage(path)
            self.info(
                msg=Event.Completed,
                target="resource",
                resource="storage",
                path=path,
                free_start=free_start,
                free_end=now[0] if now else None,
                change=(now[0] - free_start) if now else None,
                used_share=round((total - now[0]) / total, 4) if now and total else None,
                total=total,
            )

        extension = self._extension("gpu")
        if extension is not None and extension.available():
            gpu_limit, gpu_source = self._limit("gpu")
            self.info(
                msg=Event.Completed,
                target="resource",
                resource="gpu",
                measured=True,
                used=extension.used(),
                limit=gpu_limit,
                limit_source=gpu_source,
            )
        else:
            # BR-08: without an extension nothing in the standard library sees a GPU.
            self.info(msg=Event.Completed, target="resource", resource="gpu", measured=False)

        rows = self.rows()
        if rows:
            totals: dict[str, int] = defaultdict(int)
            for row in rows.values():
                for measure, amount in row[_UNITS].items():
                    totals[measure.unit] += amount
            # Named, never splatted (NFRQ-SEC-06 k.5): the units are the `Measure` vocabulary.
            self.info(
                msg=Event.Completed,
                target="volume",
                documents=totals.get("documents"),
                files=totals.get("files"),
                bytes=totals.get("bytes"),
                characters=totals.get("characters"),
                pages=totals.get("pages"),
                records=totals.get("records"),
            )
            exclusive_total = sum(row[_EXCLUSIVE] for row in rows.values()) or 1
            ranked = sorted(rows.items(), key=lambda item: -item[1][_EXCLUSIVE])
            for rank, ((component, operation), row) in enumerate(ranked[: self.HOTSPOTS], 1):
                self.info(
                    msg=Event.Completed,
                    target="hotspot",
                    rank=rank,
                    component=component,
                    operation=operation,
                    calls=row[_CALLS],
                    failed=row[_FAILS],
                    exclusive_seconds=round(row[_EXCLUSIVE] / 1e9, 4),
                    share=round(row[_EXCLUSIVE] / exclusive_total, 4),
                    max_seconds=round(row[_MAX] / 1e9, 4),
                )
            for (component, operation), row in sorted(rows.items()):
                self.debug(
                    msg=Event.Completed,
                    target="operation",
                    component=component,
                    operation=operation,
                    calls=row[_CALLS],
                    failed=row[_FAILS],
                    seconds=round(row[_NS] / 1e9, 4),
                    exclusive=round(row[_EXCLUSIVE] / 1e9, 4),
                    max_seconds=round(row[_MAX] / 1e9, 4),
                    units=self._units(row[_UNITS]),
                )

        for stack in self._stacks.values():
            for frame in stack:
                self._defects[(frame[0], frame[1], "open at end of pass")] += 1
        for (component, operation, defect), count in sorted(self._defects.items()):
            # FRQ-MET-01 §12 t.1: an incomplete pair is a finding against the code (D-11).
            self.warning(
                msg=Event.Check,
                target="pair",
                component=component,
                operation=operation,
                defect=defect,
                count=count,
            )
        self.info(
            msg=Event.Completed,
            target="measure",
            level=self._level,
            operations=len(rows),
            samples=self._samples,
            alerts=self._alerts,
            unpaired=self._unpaired,
            dropped=self._dropped,
            faults=self._faults,
            trace=len(self._trace),
        )

    def samples(self) -> list[MetricSample]:
        """Series for a sink: operations, units and the resource gauges of the pass."""
        out: list[MetricSample] = []
        for (component, operation), row in sorted(self.rows().items()):
            labels = {"component": component, "operation": operation}
            counter = MetricKind.COUNTER
            out.append(
                MetricSample(
                    "wf_operations_total",
                    counter,
                    {**labels, "outcome": "completed"},
                    float(row[_CALLS] - row[_FAILS]),
                    unit="operations",
                )
            )
            if row[_FAILS]:
                out.append(
                    MetricSample(
                        "wf_operations_total",
                        counter,
                        {**labels, "outcome": "failed"},
                        float(row[_FAILS]),
                        unit="operations",
                    )
                )
            for scope, index in (("inclusive", _NS), ("exclusive", _EXCLUSIVE)):
                out.append(
                    MetricSample(
                        "wf_operation_seconds_total",
                        counter,
                        {**labels, "scope": scope},
                        row[index] / 1e9,
                        unit="seconds",
                    )
                )
            for measure, amount in row[_UNITS].items():
                out.append(
                    MetricSample(measure.series, MetricKind.COUNTER, {"component": component},
                                 float(amount), unit=measure.unit)
                )
        # The pass total is a gauge of the run; `wf_documents_total{component}` stays the
        # per-component counter read off the closing records.
        out.append(
            MetricSample(
                "wf_run_documents", MetricKind.GAUGE, {}, float(self._documents), unit="documents"
            )
        )
        if self._peak_rss is not None:
            out.append(
                MetricSample(
                    "wf_process_rss_bytes",
                    MetricKind.GAUGE,
                    {},
                    float(self._peak_rss),
                    unit="bytes",
                )
            )
        out.append(MetricSample("wf_unpaired_spans_total", MetricKind.COUNTER, {},
                                float(self._unpaired + self._dropped), unit="spans"))
        out.extend(self._run_samples())
        if not self._labels:
            return out
        return [
            MetricSample(s.name, s.kind, {**self._labels, **s.labels}, s.value, s.buckets, s.unit)
            for s in out
        ]

    def _run_samples(self) -> list[MetricSample]:
        """The cost of the pass as gauges — what a job that ends leaves on a Pushgateway."""
        start, end = self._baseline, self._last
        if start is None or end is None:
            return []
        gauge = MetricKind.GAUGE
        out: list[MetricSample] = []

        def add(name: str, value: Any, unit: str, **labels: str) -> None:
            if value is not None:
                out.append(MetricSample(name, gauge, labels, float(value), unit=unit))

        wall = end.at - start.at
        documents = self._documents
        add("wf_run_seconds", wall, "seconds")
        add("wf_documents_per_minute", documents / wall * 60 if wall > 0 else None, "documents")
        add("wf_cpu_seconds", end.cpu_user - start.cpu_user, "seconds", mode="user")
        add("wf_cpu_seconds", end.cpu_system - start.cpu_system, "seconds", mode="system")
        add("wf_cpu_utilisation", (end.cpu - start.cpu) / wall if wall > 0 else None, "ratio")
        add("wf_cpu_seconds_per_document",
            (end.cpu - start.cpu) / documents if documents else None, "seconds")
        add("wf_rss_bytes", start.rss, "bytes", stat="start")
        add("wf_rss_bytes", end.rss, "bytes", stat="end")
        add("wf_rss_bytes", self._peak_rss, "bytes", stat="peak")
        add("wf_memory_growth_bytes_per_document", self._memory_growth_per_document(), "bytes")
        memory_limit, _ = self._limit("memory")
        add("wf_memory_limit_bytes", memory_limit, "bytes")
        cycles = self._cycles
        if cycles:
            add("wf_cycle_seconds", min(cycles), "seconds", stat="min")
            add("wf_cycle_seconds", self._percentile(cycles, 0.5), "seconds", stat="median")
            add("wf_cycle_seconds", self._percentile(cycles, 0.95), "seconds", stat="p95")
            add("wf_cycle_seconds", max(cycles), "seconds", stat="max")
        for path, (_, total) in sorted(self._storage.items()):
            now = ResourceProbe.storage(path)
            if now:
                add("wf_storage_free_bytes", now[0], "bytes", path=path)
                add("wf_storage_total_bytes", total, "bytes", path=path)
        add("wf_alerts_total", self._alerts, "alerts")
        for (component, operation), row in sorted(self.rows().items()):
            add("wf_operation_seconds_max", row[_MAX] / 1e9, "seconds",
                component=component, operation=operation)
        return out

    # endregion Report


# --------------------------------------------------------------------------- #
# endregion Monitor                                                           #
# --------------------------------------------------------------------------- #
