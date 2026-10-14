# Module name: tests/test_workflow_run.py
# StRS-WORKFLOW: Workflow is final (BR-WFL-17); it records a processor error once and passes it on
# unchanged (BR-WFL-11, BR-WFL-12); a monitor or driver report that fails is a minor error that
# stops nothing (BR-WFL-10, BR-WFL-14).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_workflow_run -v
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from wattleflow.concrete.driver import LazyDriverProxy
from wattleflow.concrete.manager import ConnectionManager, DriverManager, ProcessorManager
from wattleflow.concrete.processor import GenericProcessor
from wattleflow.concrete.workflow import Workflow, WorkflowException
from wattleflow.core import IConfig
from wattleflow.enums.event import Event
from wattleflow.audit import GenericAudit as Audit


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(())


def build(*names):
    processors = ProcessorManager()
    for name in names:
        processors.register_processor(processor=Processor(), name=name)
    return Workflow(
        adapter=MagicMock(spec=IConfig),
        connections=ConnectionManager(),
        drivers=DriverManager(),
        processors=processors,
    )


def stub_start(flow, behaviour):
    """Replace `start` on the class (the instances are slotted): `behaviour(name)` runs per processor."""
    names = {id(p): n for n, p in flow.processors.all.items()}
    return patch.object(Processor, "start", lambda self: behaviour(names[id(self)]))


class FinalTest(unittest.TestCase):
    def test_a_subclass_is_refused(self):  # BR-WFL-17
        with self.assertRaises(TypeError):
            type("Flow", (Workflow,), {})


class FrozenCompositionTest(unittest.TestCase):  # FR-WRK-03
    def test_the_monitor_is_attached_once(self):
        flow = build()
        flow.attach_monitor(MagicMock())
        with self.assertRaises(WorkflowException):
            flow.attach_monitor(MagicMock())

    def test_the_monitor_cannot_be_attached_after_a_run(self):
        flow = build()
        flow.run()
        with self.assertRaises(WorkflowException):
            flow.attach_monitor(MagicMock())
        self.assertIsNone(flow.monitor)

    def test_the_managers_cannot_be_replaced(self):
        flow = build()
        with self.assertRaises(AttributeError):
            flow.processors = ProcessorManager()


class StateErrorTest(unittest.TestCase):  # FR-WRK-11
    def test_a_bad_snapshot_gives_one_error_and_the_exception(self):
        flow = build("a")
        with patch.object(Workflow, "error") as error, self.assertRaises(WorkflowException):
            flow.restore_state(object())
        self.assertEqual(error.call_count, 1)

    def test_a_processor_that_cannot_save_gives_one_error_and_the_same_exception(self):
        flow = build("a")
        boom = RuntimeError("no save")
        with patch.object(Processor, "save_state", side_effect=boom), patch.object(
            Workflow, "error"
        ) as error, self.assertRaises(RuntimeError) as caught:
            flow.save_state()
        self.assertIs(caught.exception, boom)
        self.assertEqual(error.call_count, 1)


class SuccessfulRunTest(unittest.TestCase):
    def test_processors_start_in_order_of_registration(self):  # FR-WRK-04 k.1
        flow = build("a", "b", "c")
        order = []
        with stub_start(flow, order.append):
            flow.run()
        self.assertEqual(order, ["a", "b", "c"])

    def test_a_workflow_without_processors_completes(self):  # FR-WRK-04 k.2
        build().run()

    def test_exactly_two_info_records_bound_the_run(self):  # FR-WRK-05, QR-WRK-04
        flow = build("a", "b")
        with stub_start(flow, lambda name: None), patch.object(Workflow, "info") as info:
            flow.run()
        self.assertEqual(info.call_count, 2)
        first, last = info.call_args_list
        self.assertEqual(first.kwargs["processors"], "a, b")
        self.assertEqual((last.kwargs["processors"], last.kwargs["processed"]), (2, 0))
        for call in (first, last):
            self.assertNotIn("step", call.kwargs)


class ProcessorErrorTest(unittest.TestCase):
    def test_the_error_is_recorded_once_and_passed_on_unchanged(self):  # BR-WFL-11, BR-WFL-12
        flow = build("a", "b", "c")
        boom = RuntimeError("boom")
        started = []

        def behaviour(name):
            started.append(name)
            if name == "b":
                raise boom

        with stub_start(flow, behaviour), patch.object(
            Workflow, "error"
        ) as error, self.assertRaises(RuntimeError) as caught:
            flow._execute()
        self.assertIs(caught.exception, boom)
        self.assertEqual(started, ["a", "b"])
        self.assertEqual(error.call_count, 1)
        self.assertEqual(error.call_args.kwargs["processor"], "b")


class MonitorTest(unittest.TestCase):
    def flow_with(self, monitor):
        flow = build()
        flow.attach_monitor(monitor)
        return flow

    def test_a_monitor_that_fails_to_begin_does_not_stop_the_flow(self):  # BR-WFL-14
        monitor = MagicMock()
        monitor.begin.side_effect = RuntimeError("no begin")
        flow = self.flow_with(monitor)
        before = Audit._observer
        with patch.object(Workflow, "warning") as warning, patch.object(Workflow, "_execute", return_value=7):
            self.assertEqual(flow.run(), 7)
        warning.assert_called_once()
        monitor.end.assert_not_called()
        self.assertIs(Audit._observer, before)

    def test_a_monitor_that_fails_to_end_does_not_hide_the_processor_error(self):  # BR-WFL-14
        monitor = MagicMock()
        monitor.end.side_effect = RuntimeError("no end")
        flow = self.flow_with(monitor)
        before = Audit._observer
        boom = ValueError("processor")
        with patch.object(Workflow, "warning") as warning, patch.object(Workflow, "_execute", side_effect=boom):
            with self.assertRaises(ValueError) as caught:
                flow.run()
        self.assertIs(caught.exception, boom)
        warning.assert_called_once()
        self.assertIs(Audit._observer, before)

    def test_a_monitor_that_fails_to_end_does_not_fail_a_good_run(self):  # BR-WFL-14
        monitor = MagicMock()
        monitor.end.side_effect = RuntimeError("no end")
        flow = self.flow_with(monitor)
        with patch.object(Workflow, "warning"), patch.object(Workflow, "_execute", return_value=3):
            self.assertEqual(flow.run(), 3)


class DriverReportTest(unittest.TestCase):
    def flow_with(self, drivers):
        flow = build()
        patcher = patch.object(DriverManager, "all", new_callable=PropertyMock, return_value=drivers)
        patcher.start()
        self.addCleanup(patcher.stop)
        return flow

    def test_a_report_that_fails_does_not_stop_the_others(self):  # BR-WFL-10
        bad, good = MagicMock(), MagicMock()
        bad.report.side_effect = RuntimeError("no report")
        flow = self.flow_with({"bad": bad, "good": good})
        with patch.object(Workflow, "warning") as warning:
            flow.audit_drivers()
        good.report.assert_called_once()
        warning.assert_called_once()
        self.assertEqual((warning.call_args.kwargs["msg"], warning.call_args.kwargs["step"]), (Event.Audit, Event.Failed))

    def test_a_driver_without_a_report_is_not_an_info_record(self):  # BR-WFL-10, NFRQ-OBS-03
        flow = self.flow_with({"mute": object()})
        with patch.object(Workflow, "info") as info, patch.object(Workflow, "debug") as debug:
            flow.audit_drivers()
        info.assert_not_called()
        debug.assert_called_once()
        self.assertEqual((debug.call_args.kwargs["msg"], debug.call_args.kwargs["step"]), (Event.Audit, Event.Completed))
        self.assertIs(debug.call_args.kwargs["reported"], False)

    def test_the_write_paths_of_built_drivers_are_listed(self):  # the factory announces them to the monitor
        with_path = MagicMock(write_path="/data/out")
        without = MagicMock(spec=[])
        flow = self.flow_with({"a": with_path, "b": without, "c": MagicMock(write_path="/data/two")})
        self.assertEqual(flow.measured_paths(), ["/data/out", "/data/two"])

    def test_a_lazy_driver_that_is_not_built_is_not_woken(self):
        lazy = LazyDriverProxy(factory=MagicMock(), conn_mgr=MagicMock(), conn_name="db")
        flow = self.flow_with({"lazy": lazy})
        self.assertEqual(flow.measured_paths(), [])
        lazy._factory.assert_not_called()
        lazy._conn_mgr.get_connection.assert_not_called()

    def test_a_write_path_that_cannot_be_read_is_recorded_not_swallowed(self):  # BR-WFL-13
        class Broken:
            @property
            def write_path(self):
                raise OSError("denied")

        flow = self.flow_with({"broken": Broken()})
        with patch.object(Workflow, "warning") as warning:
            self.assertEqual(flow.measured_paths(), [])
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
