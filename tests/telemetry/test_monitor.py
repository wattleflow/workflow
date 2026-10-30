# Module name: tests/telemetry/test_monitor.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""`Monitor` as the observer of audit records — spans, units, cycles, levels (SyRS-MNT-monitor)."""

from __future__ import annotations

import gc
import time
import unittest

from wattleflow.concrete.base import Wattleflow
from wattleflow.core import IDriver, IProcessor
from wattleflow.enums.event import Event
from wattleflow.enums.metric import Measure
from wattleflow.audit import GenericAudit as Audit
from wattleflow.telemetry.monitor import Monitor, MonitorLevel


class FakeDriver(Wattleflow, IDriver):
    """A driver that audits like the real ones: Started / Completed with units on the close."""

    def load(self) -> None: ...
    def close(self) -> None: ...
    def metadata(self): ...

    def read(self, uri: str, **kwargs):
        self.debug(msg=Event.Read, step=Event.Started, uri=uri)
        time.sleep(0.005)
        self.debug(msg=Event.Read, step=Event.Completed, size=100, colour=3, flag=True)
        return b""

    def write(self, uri: str, **kwargs):
        self.debug(msg=Event.Write, step=Event.Started)
        self.read(uri)  # nested span
        if kwargs.get("fail"):
            self.debug(msg=Event.Write, step=Event.Failed, error="boom")
            raise ValueError("boom")
        self.debug(msg=Event.Write, step=Event.Completed, size=50)
        return uri


class FakeProcessor(Wattleflow, IProcessor):
    def create_generator(self): ...
    def start(self) -> None: ...

    def processed(self, n: int) -> None:
        for i in range(n):
            time.sleep(0.002)
            self.info(msg=Event.Processed, cycle=i + 1)


class MonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor = Monitor(level="CRITICAL")
        self.monitor.configure(level="OPERATIONS", interval=3600)
        self.monitor.begin()
        gc.collect()  # a destructor of an earlier test's object must not land in this monitor
        self.previous = Audit.observe(self.monitor.hook)
        self.driver = FakeDriver(level="CRITICAL")
        self.processor = FakeProcessor(level="CRITICAL")

    def tearDown(self) -> None:
        Audit.observe(self.previous)

    def rows(self):
        return self.monitor.rows()

    def test_pair_becomes_one_row_with_units_from_the_closing_record(self) -> None:
        self.driver.read("a")
        row = self.rows()[("FakeDriver", "Read")]
        self.assertEqual((row[0], row[1]), (1, 0))
        self.assertGreaterEqual(row[2], 5_000_000)
        self.assertEqual(row[5], {Measure.Size: 100})  # `colour` unknown, `flag` not an int

    def test_nested_span_gives_exclusive_time(self) -> None:
        self.driver.write("a")
        write = self.rows()[("FakeDriver", "Write")]
        read = self.rows()[("FakeDriver", "Read")]
        self.assertGreaterEqual(write[2], read[2])
        self.assertLess(write[3], read[2])  # exclusive excludes the child

    def test_failed_closes_the_span_as_a_failure(self) -> None:
        with self.assertRaises(ValueError):
            self.driver.write("a", fail=True)
        self.assertEqual(self.rows()[("FakeDriver", "Write")][1], 1)

    def test_unpaired_close_is_counted_not_hidden(self) -> None:
        self.driver.debug(msg=Event.Close, step=Event.Completed)
        self.assertEqual(self.monitor._unpaired, 1)
        self.assertEqual(self.rows(), {})

    def test_open_frames_above_an_out_of_order_close_are_dropped_and_named(self) -> None:
        self.driver.debug(msg=Event.Write, step=Event.Started)
        self.driver.debug(msg=Event.Read, step=Event.Started)
        self.driver.debug(msg=Event.Write, step=Event.Completed)
        self.assertEqual(self.monitor._dropped, 1)
        self.assertIn(("FakeDriver", "Write"), self.rows())
        self.assertEqual(self.monitor._defects, {("FakeDriver", "Read", "open without close"): 1})
        with self.assertLogs("Monitor", level="WARNING") as logs:
            self.monitor.end()
        self.assertTrue(
            any("target=pair" in line and "operation=Read" in line for line in logs.output)
        )

    def test_processed_record_is_a_cycle(self) -> None:
        self.processor.processed(3)
        self.assertEqual(self.monitor._documents, 3)
        self.assertEqual(len(self.monitor._cycles), 2)

    def test_summary_level_measures_cycles_but_not_operations(self) -> None:
        self.monitor.configure(level="SUMMARY", interval=3600)
        Audit.observe(self.monitor.hook)
        self.driver.read("a")
        self.processor.processed(1)
        self.assertEqual(self.rows(), {})
        self.assertEqual(self.monitor._documents, 1)

    def test_level_per_role(self) -> None:
        self.monitor.configure(level="SUMMARY", roles={"driver": "OPERATIONS"}, interval=3600)
        Audit.observe(self.monitor.hook)
        self.driver.read("a")
        self.assertIn(("FakeDriver", "Read"), self.rows())

    def test_other_classes_are_summary_only_unless_asked(self) -> None:
        other = Wattleflow(level="CRITICAL")
        other.debug(msg=Event.Update, step=Event.Started)
        other.debug(msg=Event.Update, step=Event.Completed)
        self.assertEqual(self.rows(), {})
        self.monitor.configure(level="OPERATIONS", roles={"other": "OPERATIONS"}, interval=3600)
        other.debug(msg=Event.Update, step=Event.Started)
        other.debug(msg=Event.Update, step=Event.Completed)
        self.assertIn(("Wattleflow", "Update"), self.rows())

    def test_trace_keeps_bounded_spans(self) -> None:
        self.monitor.configure(level="TRACE", interval=3600)
        for _ in range(3):
            self.driver.read("a")
        self.assertEqual(len(self.monitor._trace), 3)

    def test_records_still_reach_the_logger(self) -> None:
        self.driver.set_level("DEBUG")
        try:
            with self.assertLogs("FakeDriver", level="DEBUG") as logs:
                self.driver.read("a")
        finally:
            self.driver.set_level("CRITICAL")
        self.assertEqual(len(logs.output), 2)

    def test_no_observer_means_no_measurement(self) -> None:
        Audit.observe(None)
        self.driver.read("a")
        self.assertEqual(self.rows(), {})

    def test_report_writes_run_resources_hotspots_and_health_at_info(self) -> None:
        self.driver.write("a")
        self.processor.processed(2)
        with self.assertLogs("Monitor", level="INFO") as logs:
            self.monitor.end()
        text = "\n".join(logs.output)
        for needle in (
            "target=run",
            "documents=2",
            "resource=memory",
            "resource=cpu",
            "target=volume",
            "bytes=150",
            "target=hotspot",
            "target=measure",
        ):
            self.assertIn(needle, text)

    def test_unknown_level_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            MonitorLevel.resolve("LOUD")

    def test_samples_for_a_sink(self) -> None:
        self.driver.write("a")
        names = {s.name for s in self.monitor.samples()}
        self.assertTrue(
            {"wf_operations_total", "wf_operation_seconds_total", "wf_bytes_total"} <= names
        )


if __name__ == "__main__":
    unittest.main()
