# Module name: concrete/workflow.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "Workflow",
    "WorkflowException",
]

from abc import ABC
from typing import Any
from wattleflow.core import IConfig, IOriginator
from wattleflow.enums.event import Event
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.memento_store import (
    FileMementoStore,
    MementoStore,
    MementoStoreException,
    MemoryMementoStore,
)
from wattleflow.helpers.audit import Audit
from wattleflow.helpers.monitor import Monitor
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.driver import LazyDriverProxy
from wattleflow.concrete.manager import (
    ConnectionManager,
    DriverManager,
    ProcessorManager,
)


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class WorkflowException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Workflow Classes                                                     #
# --------------------------------------------------------------------------- #


class Workflow(Wattleflow, IOriginator, ABC):
    __slots__ = (
        "_connections",
        "_drivers",
        "_processors",
        "_monitor",
    )

    def __init__(
        self,
        adapter: IConfig,
        connections: ConnectionManager,
        drivers: DriverManager,
        processors: ProcessorManager,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)
        self.debug(
            msg=Event.Constructor,
            step=Event.Started,
            connections=connections,
            drivers=drivers,
            processors=processors,
        )

        from wattleflow.concrete.helper import Attribute

        Attribute.evaluate(self, adapter, IConfig)
        Attribute.evaluate(self, connections, ConnectionManager)
        Attribute.evaluate(self, drivers, DriverManager)
        Attribute.evaluate(self, processors, ProcessorManager)

        self._connections: ConnectionManager = connections
        self._drivers: DriverManager = drivers
        self._processors: ProcessorManager = processors
        self._monitor: Monitor | None = None

        self.debug(
            msg=Event.Constructor,
            step=Event.Completed,
            connections=self._connections,
            drivers=self._drivers,
            processor=self._processors,
        )

    def __repr__(self) -> str:
        return f"{self.name}[{self._connections!r}, {self._drivers!r}, {self._processors!r}]"

    @property
    def connections(self) -> ConnectionManager:
        return self._connections

    @property
    def drivers(self) -> DriverManager:
        return self._drivers

    @property
    def processors(self) -> ProcessorManager:
        return self._processors

    @property
    def monitor(self) -> Monitor | None:
        return self._monitor

    def attach_monitor(self, monitor: Monitor | None) -> None:
        """The factory hands over the monitor the configuration asked for (`monitoring:`)."""
        self._monitor = monitor

    def run(self, **kwargs: Any) -> Any:
        monitor = self._monitor
        if monitor is None:
            return self.execute(**kwargs)
        monitor.begin(self.measured_paths())
        previous = Audit.observe(monitor.hook)
        try:
            return self.execute(**kwargs)
        finally:
            Audit.observe(previous)
            monitor.end()

    def measured_paths(self) -> list[str]:
        """Write paths of the drivers already built; a lazy driver is not woken."""
        paths: list[str] = []
        for driver in self.drivers.all.values():
            target = driver.driver if isinstance(driver, LazyDriverProxy) else driver
            try:
                path = getattr(target, "write_path", None) if target is not None else None
            except Exception:
                path = None
            if path:
                paths.append(str(path))
        return paths

    def audit_drivers(self) -> None:
        """Ask every driver to report what it did."""
        for name, driver in self.drivers.all.items():
            report = getattr(driver, "report", None)
            if callable(report):
                report()
                continue

            self.info(
                msg=Event.Completed,
                target="driver",
                name=name,
                type=type(driver).__name__,
                reported=False,
            )

    def save_state(self) -> GenericMemento:
        return GenericMemento(
            processors={
                name: processor.save_state()
                for name, processor in self._processors.all.items()
                if isinstance(processor, IOriginator)
            }
        )

    def restore_state(self, memento: GenericMemento) -> None:
        if not isinstance(memento, GenericMemento):
            raise WorkflowException(self, f"Invalid memento: {type(memento).__name__}")
        saved = memento.to_dict().get("processors")
        if not isinstance(saved, dict):
            raise WorkflowException(self, "Invalid memento: no `processors` mapping")
        known = self._processors.all
        # Check every entry before restoring any, so a bad snapshot changes nothing.
        for name, snapshot in saved.items():
            if name not in known or not isinstance(known[name], IOriginator):
                raise WorkflowException(self, f"Cannot restore: no processor named {name!r}")
            if not isinstance(snapshot, GenericMemento):
                raise WorkflowException(self, f"Invalid snapshot for processor {name!r}")
        for name, snapshot in saved.items():
            known[name].restore_state(snapshot)

    def execute(self, **kwargs: Any) -> None:
        processors = self.processors.all
        self.info(
            msg=Event.Execute,
            processors=", ".join(processors.keys()),
        )

        for processor in processors.values():
            processor.start()

        self.info(
            msg=Event.Completed,
            processors=len(processors),
            processed=sum(p.cycle for p in processors.values()),
        )


# --------------------------------------------------------------------------- #
# region Workflow Classes                                                     #
# --------------------------------------------------------------------------- #
