# Module name: tests/telemetry/test_exporters.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Sinks at the end of a pass — every destination visited, none able to stop the run (SyRS-MNT-monitor)."""

from __future__ import annotations

import unittest

from wattleflow.concrete.factory import WorkflowFactory
from wattleflow.telemetry.metrics import MetricSink
from wattleflow.telemetry.monitor import Monitor


class Recording(MetricSink):
    def __init__(self, driver=None, fail: bool = False, **options) -> None:
        self.driver, self.fail, self.options, self.received = driver, fail, options, None

    def publish(self, samples):
        if self.fail:
            raise ConnectionError("gateway down")
        self.received = list(samples)
        return True


class RecordingDriver:
    def __init__(self) -> None:
        self.writes = []

    def write(self, uri, data, **kwargs):
        self.writes.append((uri, data, kwargs))


class ExporterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = Monitor(level="CRITICAL")

    def test_every_sink_is_visited_and_a_failure_is_a_warning(self) -> None:
        broken, working = Recording(fail=True), Recording()
        self.monitor.configure(level="SUMMARY", sinks=[broken, working])
        self.monitor.begin()
        with self.assertLogs("Monitor", level="INFO") as logs:
            self.monitor.end()
        self.assertIsNotNone(working.received)
        names = {s.name for s in working.received}
        self.assertTrue({"wf_run_documents", "wf_run_seconds", "wf_rss_bytes", "wf_cpu_seconds"} <= names)
        text = "\n".join(logs.output)
        self.assertIn("sink=Recording', 'error=ConnectionError", text)
        self.assertNotIn("gateway down", text)
        self.assertIn("sink=Recording', 'published=True", text)

    def test_factory_builds_exporters_from_configuration(self) -> None:
        WorkflowFactory.register("RecordingSink", Recording)
        driver = RecordingDriver()

        class Drivers:
            def get_driver(self, name):
                return driver if name == "driver-x" else None

        class Built:
            drivers = Drivers()

        sinks = WorkflowFactory._build_exporters(
            [{"sink": "RecordingSink", "driver": "driver-x", "job": "j"}], Built()
        )
        self.assertEqual(len(sinks), 1)
        self.assertIs(sinks[0].driver, driver)
        self.assertEqual(sinks[0].options, {"job": "j"})

    def test_exporter_instance_defaults_to_the_workflow_name(self) -> None:
        WorkflowFactory.register("RecordingSink", Recording)

        class Built:
            class drivers:
                @staticmethod
                def get_driver(name):
                    return None

        sinks = WorkflowFactory._build_exporters([{"sink": "RecordingSink"}], Built(), "pdf-pii")
        self.assertEqual(sinks[0].options, {"instance": "pdf-pii"})
        sinks = WorkflowFactory._build_exporters([{"sink": "RecordingSink", "instance": "x"}], Built(), "pdf-pii")
        self.assertEqual(sinks[0].options, {"instance": "x"})

    def test_workflow_labels_ride_on_every_sample(self) -> None:
        self.monitor.configure(level="SUMMARY", labels={"workflow": "pdf-pii", "app": "03.yaml", "empty": None})
        self.monitor.begin()
        self.monitor.end()
        samples = self.monitor.samples()
        self.assertTrue(samples)
        self.assertTrue(all(s.labels["workflow"] == "pdf-pii" and s.labels["app"] == "03.yaml" for s in samples))
        self.assertTrue(all("empty" not in s.labels for s in samples))

    def test_exporter_without_sink_is_refused(self) -> None:
        from wattleflow.concrete.factory import WorkflowFactoryException

        with self.assertRaises(WorkflowFactoryException):
            WorkflowFactory._build_exporters([{"driver": "x"}], None)


if __name__ == "__main__":
    unittest.main()
