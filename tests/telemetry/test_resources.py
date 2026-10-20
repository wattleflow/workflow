# Module name: tests/telemetry/test_resources.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Limits, thresholds and extensions of `Monitor` (SyRS-MNT-monitor, SyRS-RSR-MANAGER)."""

from __future__ import annotations

import unittest
from unittest import mock

from wattleflow.concrete.factory import WorkflowFactory
from wattleflow.concrete.factory import logger as factory_logger
from wattleflow.telemetry.monitor import Monitor
from wattleflow.telemetry.resources import Resource, ResourceManager, ResourceSnapshot
from wattleflow.telemetry.resources.memory import ResourceMemory


class FakeGpu(Resource):
    RESOURCE = "gpu"

    def __init__(self, used: int = 1, total: int = 100, present: bool = True) -> None:
        self.value, self.total, self.present = used, total, present

    def available(self) -> bool:
        return self.present

    def limit(self):
        return self.total, "fake"

    def used(self):
        return self.value


def snapshot(rss: int | None = 10, throttled: int | None = None) -> ResourceSnapshot:
    return ResourceSnapshot(
        at=0.0, cpu_user=0.0, cpu_system=0.0, rss=rss, peak_rss=rss, throttled=throttled
    )


class ResourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = Monitor(level="CRITICAL")

    def warnings_for(self, samples: list[ResourceSnapshot], **configure) -> list[str]:
        # The memory ceiling is declared, so the test does not depend on the host.
        manager = ResourceManager(
            limits={"memory": 100},
            thresholds=configure.get("thresholds"),
            extensions=configure.get("extensions", ()),
        )
        self.monitor.configure(limits=manager, **configure)
        with mock.patch.object(ResourceManager, "snapshot", side_effect=samples):
            with self.assertLogs("Monitor", level="WARNING") as logs:
                self.monitor.begin()
                for _ in samples[1:]:
                    self.monitor.boundary("cycle")
                self.monitor.warning(msg="marker")
        return [
            line for line in logs.output if line.startswith("WARNING") and "marker" not in line
        ]

    def test_memory_warns_once_per_crossing_and_rearms(self) -> None:
        samples = [snapshot(10), snapshot(85), snapshot(90), snapshot(50), snapshot(95)]
        found = self.warnings_for(samples, thresholds={"memory": 0.8})
        self.assertEqual(len(found), 2)
        self.assertIn("resource=memory", found[0])
        self.assertIn("used=85", found[0])
        self.assertIn("used=95", found[1])

    def test_no_threshold_no_warning(self) -> None:
        self.assertEqual(self.warnings_for([snapshot(10), snapshot(99)]), [])

    def test_throttling_is_a_signal_without_threshold(self) -> None:
        found = self.warnings_for([snapshot(10, 0), snapshot(10, 0), snapshot(10, 3)])
        self.assertEqual(len(found), 1)
        self.assertIn("throttled=3", found[0])

    def test_gpu_extension_threshold(self) -> None:
        found = self.warnings_for(
            [snapshot(), snapshot()], thresholds={"gpu": 0.5}, extensions=[FakeGpu(used=70)]
        )
        self.assertEqual(len(found), 1)
        self.assertIn("resource=gpu", found[0])

    def test_undeclared_or_invalid_threshold_is_reported_and_ignored(self) -> None:
        with self.assertLogs("Monitor", level="WARNING") as logs:
            self.monitor.configure(thresholds={"disk": 0.5, "memory": 2})
        self.assertEqual(len(logs.output), 2)
        self.assertEqual(self.monitor._thresholds, {})

    def test_announce_reports_unmeasured_gpu_and_unapplied_threshold(self) -> None:
        # EV01 is announced by the manager that settled the limits.
        manager = ResourceManager(
            thresholds={"gpu": 0.9}, extensions=[FakeGpu(0, present=False)], level="DEBUG"
        )
        self.monitor.configure(thresholds={"gpu": 0.9}, limits=manager)
        with self.assertLogs(level="DEBUG") as logs:
            self.monitor.announce()
        text = "\n".join(logs.output)
        self.assertIn("limit_source=unmeasured", text)
        self.assertIn("relative threshold is not applied", text)

    def test_unknown_memory_limit_is_not_guessed(self) -> None:
        with (
            mock.patch.object(ResourceMemory, "read", return_value=None),
            mock.patch("os.sysconf", side_effect=ValueError),
        ):
            self.assertEqual(ResourceMemory().limit(), (None, "unknown"))

    def test_factory_configures_from_yaml_section(self) -> None:
        class Adapter:
            def find(self, *keys, default=None):
                return {
                    "level": "SUMMARY",
                    "thresholds": {"memory": 0.7},
                    "extensions": ["FakeGpu"],
                    "other": 1,
                }

        class Built:
            monitor = None

            def measured_paths(self):
                return []

            def attach_monitor(self, monitor):
                self.monitor = monitor

        # The factory registers classes only and builds extensions without arguments.
        WorkflowFactory.register("FakeGpu", FakeGpu)
        # The factory logger is pinned to ERROR until the YAML declares a level.
        factory_logger.set_level("INFO")
        try:
            built = Built()
            with self.assertLogs(level="INFO") as logs:
                WorkflowFactory._configure_monitor(Adapter(), ("dev",), built)
        finally:
            factory_logger.set_level("ERROR")
        self.assertEqual(built.monitor._thresholds, {"memory": 0.7})
        self.assertIsInstance(built.monitor._manager.resource("gpu"), FakeGpu)
        self.assertTrue(any("discarded" in line and "other" in line for line in logs.output))

    def test_level_off_attaches_no_monitor(self) -> None:
        class Adapter:
            def find(self, *keys, default=None):
                return {"level": "OFF"}

        class Built:
            monitor = "untouched"

            def measured_paths(self):
                return []

            def attach_monitor(self, monitor):
                self.monitor = monitor

        built = Built()
        WorkflowFactory._configure_monitor(Adapter(), ("dev",), built)
        self.assertEqual(built.monitor, "untouched")


if __name__ == "__main__":
    unittest.main()
