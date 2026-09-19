# Module name: schedulers/cron_job.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
SchedulerCronJob — run a workflow repeatedly on a fixed heartbeat.

The wrapper owns the whole cycle: it registers the classes the configuration
names, builds the workflow through ``WorkflowFactory`` and executes it, then
sleeps. A failed pass is logged and emitted as an event; it never stops the
loop, because a cron job that dies on one bad pass stops being a cron job.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import time
from typing import Any, Mapping
from wattleflow.concrete.scheduler import Scheduler
from wattleflow.concrete.workflow import WorkflowFactory
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["SchedulerCronJob"]

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class SchedulerCronJob(Scheduler):
    """Build and run a workflow every ``heartbeat`` seconds."""

    # The adapter is injected rather than read from a path: the YAML adapter
    # lives in a downstream distribution, and this package must not import it
    # (NFRQ-SEC-03, the dependency arrow points one way only).
    def __init__(
        self,
        adapter: Any,
        heartbeat: int = 300,
        sections: tuple[str, ...] = ("infrastructure", "dev"),
        registrations: Mapping[str, type] | None = None,
        **kwargs,
    ):
        sections = tuple(sections)

        # Level, handler and format are configuration, not arguments of this
        # class: they live in `infrastructure.<env>.logging`, the same keys the
        # factory reads for every other component.
        for key, entry in (("level", "level"), ("handler", "handler"), ("formatting", "format")):
            if kwargs.get(key) is None:
                declared = adapter.find(*sections, "logging", entry, default=None)
                if declared is not None:
                    kwargs[key] = declared

        super().__init__(level=kwargs.pop("level", None), **kwargs)
        self._adapter = adapter
        self._heartbeat = heartbeat
        self._sections = sections
        self._passes = 0
        self._failures = 0
        for name, cls in dict(registrations or {}).items():
            WorkflowFactory.register(name, cls)

    @property
    def heartbeat(self) -> int:
        return self._heartbeat

    @property
    def passes(self) -> int:
        return self._passes

    @property
    def failures(self) -> int:
        return self._failures

    def register(self, name: str, cls: type) -> None:
        """Register a class the configuration refers to by name."""
        WorkflowFactory.register(name, cls)

    def run_once(self) -> bool:
        """Build and execute the workflow once; report whether the pass ran."""
        self._passes += 1
        try:
            WorkflowFactory.build(adapter=self._adapter, sections=self._sections).run()
            self.info(msg=Event.Completed, cycle=self._passes)
            return True
        except Exception as e:
            self._failures += 1
            self.exception(msg=Event.Failed, cycle=self._passes, error=str(e))
            self.emit_event(event=Event.CronJobSchedulerError, error=str(e))
            return False

    # `cycles` exists so the loop is testable: an unbounded loop cannot be
    # asserted on. Left at None it runs forever, which is the cron job case.
    def run(self, cycles: int | None = None) -> None:
        """Run the workflow every ``heartbeat`` seconds, ``cycles`` times or forever."""
        # Not `cycles=`: that field name is a Measure, and the collector would
        # add this limit into the cycle counter as if it were a count.
        self.info(msg=Event.Started, heartbeat=self._heartbeat, limit=cycles)
        while cycles is None or self._passes < cycles:
            self.run_once()
            if cycles is not None and self._passes >= cycles:
                break
            self.emit_event(event=Event.Sleeping, duration=self._heartbeat)
            time.sleep(self._heartbeat)
        self.info(msg=Event.Stopped, passes=self._passes, failures=self._failures)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
