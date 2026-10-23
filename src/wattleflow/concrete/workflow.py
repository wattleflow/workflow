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

from typing import Any, ClassVar, final
from wattleflow.core import IConfig, IOriginator
from wattleflow.enums.event import Event
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.audit import GenericAudit
from wattleflow.telemetry.monitor import Monitor
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

@final
class Workflow(Wattleflow, IOriginator):
    __slots__ = (
        "_connections",
        "_drivers",
        "_processors",
        "_monitor",
    )

    _UNATTACHED: ClassVar[Any] = object()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError(f"{cls.__name__}: Workflow is final and cannot be subclassed")

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
        self._monitor: Any = self._UNATTACHED

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
        return None if self._monitor is self._UNATTACHED else self._monitor

    def attach_monitor(self, monitor: Monitor | None) -> None:
        """The factory hands over the monitor the configuration asked for (`monitoring:`).

        Once only, and before the first `run`."""
        if self._monitor is not self._UNATTACHED:
            raise WorkflowException(
                self, "The monitor is attached once, before the first run"
            )
        self._monitor = monitor

    def run(self, **kwargs: Any) -> Any:
        if self._monitor is self._UNATTACHED:
            self._monitor = None
        monitor = self._monitor
        if monitor is None:
            return self._execute(**kwargs)
        begun = observed = False
        previous = None
        try:
            monitor.begin(self.measured_paths())
            begun = True
            previous = GenericAudit.observe(monitor.hook)
            observed = True
        except Exception as error:
            self.warning(msg=Event.Start, target="monitor", reason=type(error).__name__)
        try:
            return self._execute(**kwargs)
        finally:
            if observed:
                GenericAudit.observe(previous)
            if begun:
                try:
                    monitor.end()
                except Exception as error:
                    self.warning(msg=Event.Stop, target="monitor", reason=type(error).__name__)

    def measured_paths(self) -> list[str]:
        """Write paths of the drivers already built; a lazy driver is not woken."""
        paths: list[str] = []
        for name, driver in self.drivers.all.items():
            target = driver.driver if isinstance(driver, LazyDriverProxy) else driver
            try:
                path = (
                    getattr(target, "write_path", None) if target is not None else None
                )
            except Exception as error:
                self.warning(
                    msg=Event.Check, target="driver", name=name, reason=type(error).__name__
                )
                path = None
            if path:
                paths.append(str(path))
        return paths

    def audit_drivers(self) -> None:
        """Ask every driver to report what it did; one that cannot or fails does not stop the rest."""
        for name, driver in self.drivers.all.items():
            report = getattr(driver, "report", None)
            if not callable(report):
                self.debug(
                    msg=Event.Audit,
                    step=Event.Completed,
                    target="driver",
                    name=name,
                    type=type(driver).__name__,
                    reported=False,
                )
                continue
            try:
                report()
            except Exception as error:
                self.warning(
                    msg=Event.Audit,
                    step=Event.Failed,
                    target="driver",
                    name=name,
                    type=type(driver).__name__,
                    reason=type(error).__name__,
                )

    def save_state(self) -> GenericMemento:
        try:
            return self._save_state()
        except Exception as error:
            self.error(msg=Event.Save, step=Event.Failed, error=type(error).__name__)
            raise

    def restore_state(self, memento: GenericMemento) -> None:
        try:
            self._restore_state(memento)
        except Exception as error:
            self.error(msg=Event.Restore, step=Event.Failed, error=type(error).__name__)
            raise

    def _save_state(self) -> GenericMemento:
        return GenericMemento(
            processors={
                name: processor.save_state()
                for name, processor in self._processors.all.items()
                if isinstance(processor, IOriginator)
            }
        )

    def _restore_state(self, memento: GenericMemento) -> None:
        if not isinstance(memento, GenericMemento):
            raise WorkflowException(self, f"Invalid memento: {type(memento).__name__}")
        saved = memento.to_dict().get("processors")
        if not isinstance(saved, dict):
            raise WorkflowException(self, "Invalid memento: no `processors` mapping")
        known = self._processors.all
        for name, snapshot in saved.items():
            if name not in known or not isinstance(known[name], IOriginator):
                raise WorkflowException(
                    self, f"Cannot restore: no processor named {name!r}"
                )
            if not isinstance(snapshot, GenericMemento):
                raise WorkflowException(
                    self, f"Invalid snapshot for processor {name!r}"
                )
        commits = []
        for name, snapshot in saved.items():
            processor = known[name]
            prepare = getattr(processor, "prepare_restore", None)
            if callable(prepare):
                commits.append(prepare(snapshot))
            else:
                commits.append(lambda p=processor, s=snapshot: p.restore_state(s))
        for commit in commits:
            commit()

    def _execute(self, **kwargs: Any) -> None:
        processors = self.processors.all
        self.info(
            msg=Event.Execute,
            processors=", ".join(processors.keys()),
        )

        for name, processor in processors.items():
            try:
                processor.start()
            except Exception as error:
                self.error(
                    msg=Event.Execute,
                    step=Event.Failed,
                    processor=name,
                    error=type(error).__name__,
                )
                raise

        self.info(
            msg=Event.Completed,
            processors=len(processors),
            processed=sum(p.cycle for p in processors.values()),
        )


# --------------------------------------------------------------------------- #
# region Workflow Classes                                                     #
# --------------------------------------------------------------------------- #
