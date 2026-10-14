# Module name: tests/test_audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""`GenericAudit` against SyRS-AUDIT (FR-AUD-01…18, QR-AUD-01…03).

Each test owns its logger name, so the shared handler registry never leaks between tests.
Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_audit -v
"""

from __future__ import annotations

import itertools
import logging
import threading
import unittest

from wattleflow.audit import GenericAudit
from wattleflow.audit.filters import ContextFilter
from wattleflow.constants.audit import TARGET_ATTRIBUTE
from wattleflow.enums.event import Event
from wattleflow.enums.log import LogFormat

_COUNTER = itertools.count()


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    @property
    def messages(self) -> list[str]:
        return [r.getMessage() for r in self.records]


class AuditCase(unittest.TestCase):
    def setUp(self) -> None:
        self.names: list[str] = []
        self.previous = GenericAudit.observe(None)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        GenericAudit.observe(self.previous)
        for name in self.names:
            GenericAudit._handlers.pop(name, None)
            logging.getLogger(name).handlers.clear()

    def logger_name(self) -> str:
        name = f"test.audit.{next(_COUNTER)}"
        self.names.append(name)
        return name

    def make(
        self, sink: Collect | None = None, level="DEBUG", **kwargs
    ) -> tuple[GenericAudit, Collect]:
        sink = sink or Collect()
        name = kwargs.pop("name", None) or self.logger_name()
        if name not in self.names:
            self.names.append(name)
        audit = GenericAudit(logger=logging.getLogger(name), handler=sink, level=level, **kwargs)
        return audit, sink


class IdentityTest(AuditCase):  # FR-AUD-01, QR-AUD-01
    def test_name_is_the_type_name(self):  # k.1
        class MyAudit(GenericAudit):
            __slots__ = ()

        audit = MyAudit(logger=logging.getLogger(self.logger_name()), handler=Collect())
        self.assertEqual(audit.name, "MyAudit")

    def test_str_is_the_name(self):  # k.2
        audit, _ = self.make()
        self.assertEqual(str(audit), audit.name)

    def test_the_name_cannot_be_assigned(self):  # k.3
        audit, _ = self.make()
        with self.assertRaises(AttributeError):
            audit.name = "x"

    def test_an_instance_has_no_dict(self):  # QR-AUD-01
        audit, _ = self.make()
        self.assertFalse(hasattr(audit, "__dict__"))


class LevelTest(AuditCase):  # FR-AUD-02, FR-AUD-08
    def test_a_name_resolves_to_its_level(self):  # k.4
        self.assertEqual(GenericAudit.resolve_level("info"), logging.INFO)

    def test_an_int_resolves_to_itself(self):  # k.5
        self.assertEqual(GenericAudit.resolve_level(10), 10)

    def test_an_unknown_name_is_refused(self):  # k.6
        with self.assertRaisesRegex(ValueError, "Unknown log level: 'xyz'"):
            GenericAudit(
                logger=logging.getLogger(self.logger_name()), handler=Collect(), level="xyz"
            )

    def test_another_type_is_refused(self):  # k.7
        with self.assertRaisesRegex(TypeError, "level must be int or str, got float"):
            GenericAudit(
                logger=logging.getLogger(self.logger_name()), handler=Collect(), level=1.5
            )

    def test_without_level_the_logger_keeps_its_level(self):  # k.8
        logger = logging.getLogger(self.logger_name())
        logger.setLevel(logging.ERROR)
        GenericAudit(logger=logger, handler=Collect())
        self.assertEqual(logger.level, logging.ERROR)

    def test_set_level_reaches_the_logger_and_its_handler(self):  # k.23
        audit, sink = self.make(level="ERROR")
        audit.set_level("DEBUG")
        self.assertEqual((audit._logger.level, sink.level), (logging.DEBUG, logging.DEBUG))

    def test_an_unknown_level_leaves_the_threshold_alone(self):  # k.24
        audit, _ = self.make(level="ERROR")
        with self.assertRaises(ValueError):
            audit.set_level("xyz")
        self.assertEqual(audit._logger.level, logging.ERROR)

    @unittest.expectedFailure  # k.25: SyRS-AUDIT section 8 item 7
    def test_a_threshold_reaches_every_handler_of_the_name(self):
        name = self.logger_name()
        first, h1 = self.make(name=name, level="ERROR")
        second, h2 = self.make(name=name, level="ERROR")
        second.set_level("DEBUG")
        first.debug("from A")
        self.assertIn("from A", h1.messages)

    def test_levelname_is_the_effective_level(self):
        audit, _ = self.make(level="WARNING")
        self.assertEqual(audit.levelname, "WARNING")


class SharedOutputTest(AuditCase):  # FR-AUD-03, FR-AUD-04, FR-AUD-05
    def test_instances_of_one_name_share_the_output(self):  # k.9, k.10
        name = self.logger_name()
        logger = logging.getLogger(name)
        first = GenericAudit(logger=logger, level="DEBUG")
        second = GenericAudit(logger=logger, level="DEBUG")
        self.names.append(name)
        self.assertIs(first._handler, second._handler)
        self.assertEqual(sum(h in GenericAudit._handlers.values() for h in logger.handlers), 1)

    def test_a_logger_with_a_shared_output_takes_it(self):  # k.11
        name = self.logger_name()
        first = GenericAudit(logger=logging.getLogger(name), level="DEBUG")
        again = GenericAudit(logger=logging.getLogger(name))
        self.assertIs(first._handler, again._handler)

    def test_one_warning_is_one_line(self):  # k.12
        audit, sink = self.make()
        audit.warning("once")
        self.assertEqual(sink.messages, ["once"])

    def test_the_default_output_is_a_context_stream(self):  # k.13, k.14
        name = self.logger_name()
        audit = GenericAudit(logger=logging.getLogger(name), level="CRITICAL")
        self.assertIsInstance(audit._handler, logging.StreamHandler)
        self.assertTrue(any(isinstance(f, ContextFilter) for f in audit._handler.filters))
        self.assertEqual(audit._handler.formatter._fmt, LogFormat.DEFAULT.value)

    def test_fmt_is_the_formatting(self):  # k.15
        audit = GenericAudit(
            logger=logging.getLogger(self.logger_name()), fmt="%(message)s", level="CRITICAL"
        )
        self.assertEqual(audit._handler.formatter._fmt, "%(message)s")

    def test_formatting_beats_fmt(self):  # k.16
        audit = GenericAudit(
            logger=logging.getLogger(self.logger_name()),
            fmt="%(message)s",
            formatting="%(levelname)s",
            level="CRITICAL",
        )
        self.assertEqual(audit._handler.formatter._fmt, "%(levelname)s")

    def test_the_callers_output_is_used_by_the_next_instance(self):  # k.17, k.18
        name = self.logger_name()
        mine = Collect()
        first, _ = self.make(sink=mine, name=name)
        second = GenericAudit(logger=logging.getLogger(name))
        self.assertIn(mine, logging.getLogger(name).handlers)
        self.assertIs(second._handler, mine)

    def test_concurrent_construction_does_not_double_the_output(self):  # QR-AUD-02
        name = self.logger_name()
        logger = logging.getLogger(name)
        barrier = threading.Barrier(20)

        def build():
            barrier.wait()
            GenericAudit(logger=logger, level="CRITICAL")

        threads = [threading.Thread(target=build) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.names.append(name)
        self.assertEqual(len(logger.handlers), 1)


class PropagationTest(AuditCase):  # FR-AUD-06, FR-AUD-07
    def test_propagate_false_is_applied(self):  # k.19
        audit, _ = self.make(propagate=False)
        self.assertIs(audit._logger.propagate, False)

    def test_without_propagate_the_value_stays(self):  # k.20
        audit, _ = self.make()
        self.assertIs(audit._logger.propagate, True)

    def test_the_once_hook_runs_once_per_type(self):  # k.21, k.22
        calls: list[str] = []

        class Hooked(GenericAudit):
            __slots__ = ()

            def _configure_once(self):
                calls.append(type(self).__name__)

        class Other(Hooked):
            __slots__ = ()

        for _ in range(3):
            Hooked(logger=logging.getLogger(self.logger_name()), handler=Collect())
        Other(logger=logging.getLogger(self.logger_name()), handler=Collect())
        GenericAudit._instances.discard(Hooked)
        GenericAudit._instances.discard(Other)
        self.assertEqual(calls, ["Hooked", "Other"])


class RecordTest(AuditCase):  # FR-AUD-09, FR-AUD-10, FR-AUD-11, FR-AUD-12
    def test_each_method_writes_at_its_level(self):  # k.26, k.27
        audit, sink = self.make()
        audit.debug("d")
        audit.info("i")
        audit.warning("w")
        audit.error("e")
        audit.critical("c")
        audit.fatal("f")
        self.assertEqual(
            [r.levelno for r in sink.records],
            [
                logging.DEBUG,
                logging.INFO,
                logging.WARNING,
                logging.ERROR,
                logging.CRITICAL,
                logging.CRITICAL,
            ],
        )

    def test_exception_writes_the_error_with_its_cause(self):  # k.28
        audit, sink = self.make()
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            audit.exception("failed")
        record = sink.records[0]
        self.assertEqual(record.levelno, logging.ERROR)
        self.assertIsNotNone(record.exc_info)
        self.assertIs(record.exc_info[0], RuntimeError)

    def test_below_the_threshold_nothing_is_written(self):  # k.29
        audit, sink = self.make(level="ERROR")
        audit.info("quiet")
        self.assertEqual(sink.records, [])

    def test_the_place_is_the_caller(self):  # k.30, k.31
        audit, sink = self.make()

        def caller():
            audit.info("from caller")

        def source():
            audit.update("event")

        caller()
        source()
        self.assertEqual([r.funcName for r in sink.records], ["caller", "source"])

    def test_an_explicit_stacklevel_is_used_as_given(self):  # k.32
        audit, sink = self.make()

        def inner():
            audit.info(
                "x", stacklevel=4
            )  # counts the wrapper frames: _log_msg, info, inner, outer

        def outer():
            inner()

        outer()
        self.assertEqual(sink.records[0].funcName, "outer")

    def test_plain_values_are_written_as_they_are(self):  # k.33
        audit, sink = self.make()
        audit.info("m", a=None, b=True, c=1, d=1.5, e="s")
        self.assertEqual(sink.messages[0], "m ['a=None', 'b=True', 'c=1', 'd=1.5', 'e=s']")

    def test_containers_are_counted_at_info(self):  # k.34
        audit, sink = self.make()
        audit.info("m", lst=[1, 2, 3], tup=(1,), st={1, 2}, dic={})
        self.assertEqual(
            sink.messages[0],
            "m ['lst=<list: 3>', 'tup=<tuple: 1>', 'st=<set: 2>', 'dic=<dict: 0>']",
        )

    def test_containers_are_shown_at_other_levels(self):  # k.35
        audit, sink = self.make()
        audit.debug("m", lst=[1, 2])
        self.assertEqual(sink.messages[0], "m ['lst=[1, 2]']")

    def test_a_long_repr_is_cut(self):  # k.36
        audit, sink = self.make()

        class Long:
            def __repr__(self):
                return "x" * 500

        audit.info("m", thing=Long())
        value = sink.messages[0].split("thing=")[1].rstrip("']")
        self.assertEqual((len(value), value[-1]), (100, "…"))

    def test_a_table_is_only_its_type_name(self):  # k.37
        audit, sink = self.make()

        class Frame:
            shape = (1, 2)
            columns = ["a"]

            def __repr__(self):
                return "HUGE" * 100

        audit.info("m", frame=Frame())
        self.assertIn("frame=Frame", sink.messages[0])
        self.assertNotIn("HUGE", sink.messages[0])

    def test_a_failing_repr_is_named(self):  # k.38
        audit, sink = self.make()

        class Broken:
            def __repr__(self):
                raise RuntimeError("no repr")

        audit.info("m", thing=Broken())
        self.assertIn("<unreprable Broken>", sink.messages[0])

    def test_logging_keywords_stay_out_of_the_message(self):  # k.39
        audit, sink = self.make()
        audit.info("m", extra={"k": 1}, stack_info=False, stacklevel=1)
        self.assertEqual(sink.messages[0], "m")

    def test_the_target_rides_on_the_record(self):  # k.40
        audit, sink = self.make()
        audit.info("m", target=42)
        self.assertEqual(getattr(sink.records[0], TARGET_ATTRIBUTE), "42")

    def test_an_explicit_extra_target_wins(self):  # k.41
        audit, sink = self.make()
        audit.info("m", target=42, extra={TARGET_ATTRIBUTE: "x"})
        self.assertEqual(getattr(sink.records[0], TARGET_ATTRIBUTE), "x")

    def test_without_a_target_no_attribute_is_added(self):  # k.42
        audit, sink = self.make()
        audit.info("m")
        self.assertFalse(hasattr(sink.records[0], TARGET_ATTRIBUTE))

    def test_below_the_threshold_a_value_is_never_rendered(self):  # QR-AUD-03
        audit, _ = self.make(level="ERROR")
        calls: list[int] = []

        class Probe:
            def __repr__(self):
                calls.append(1)
                return "p"

        audit.info("m", thing=Probe())
        self.assertEqual(calls, [])


class ObserverTest(AuditCase):  # FR-AUD-13…16
    def test_observe_returns_the_previous_observer(self):  # k.43
        first = lambda *a: None  # noqa: E731
        self.assertIsNone(GenericAudit.observe(first))
        self.assertIs(GenericAudit.observe(None), first)

    def test_an_observer_set_on_a_subtype_hears_every_type(self):  # k.44
        class Sub(GenericAudit):
            __slots__ = ()

        seen: list[str] = []
        Sub.observe(lambda owner, msg, step, fields: seen.append(type(owner).__name__))
        audit, _ = self.make()
        audit.info("x", step=1)
        self.assertEqual(seen, ["GenericAudit"])

    def test_after_none_the_calls_stop(self):  # k.45
        seen: list[int] = []
        GenericAudit.observe(lambda *a: seen.append(1))
        GenericAudit.observe(None)
        audit, _ = self.make()
        audit.info("x", step=1)
        self.assertEqual(seen, [])

    def test_a_step_is_reported(self):  # k.46
        seen: list = []
        GenericAudit.observe(lambda owner, msg, step, fields: seen.append((msg, step)))
        audit, _ = self.make()
        audit.info("x", step=1)
        self.assertEqual(seen, [("x", 1)])

    def test_a_closed_unit_is_reported_without_a_step(self):  # k.47, k.49
        seen: list = []
        GenericAudit.observe(lambda owner, msg, step, fields: seen.append(step))
        audit, _ = self.make()
        audit.info(Event.Processed)
        audit.info("Processed")
        self.assertEqual(seen, [None, None])

    def test_a_plain_record_is_not_reported(self):  # k.48
        seen: list = []
        GenericAudit.observe(lambda *a: seen.append(1))
        audit, _ = self.make()
        audit.info("x")
        self.assertEqual(seen, [])

    def test_reporting_does_not_depend_on_the_threshold(self):  # k.50
        seen: list = []
        GenericAudit.observe(lambda *a: seen.append(1))
        audit, sink = self.make(level="ERROR")
        audit.info("x", step=1)
        self.assertEqual((seen, sink.records), ([1], []))

    def test_a_failing_observer_never_stops_the_record(self):  # k.51, k.52, k.53
        GenericAudit.observe(lambda *a: 1 / 0)
        audit, sink = self.make()
        audit.error("e", step=2)
        self.assertIn("Audit observer failed.", sink.messages)
        self.assertTrue(any(m.startswith("e ") or m == "e" for m in sink.messages))
        failure = next(r for r in sink.records if r.getMessage() == "Audit observer failed.")
        self.assertEqual(
            (failure.levelno, failure.exc_info[0]), (logging.ERROR, ZeroDivisionError)
        )

    @unittest.expectedFailure  # k.54: SyRS-AUDIT section 8 item 9
    def test_a_failing_observer_is_written_at_critical_threshold(self):
        GenericAudit.observe(lambda *a: 1 / 0)
        audit, sink = self.make(level="CRITICAL")
        audit.error("e", step=2)
        self.assertIn("Audit observer failed.", sink.messages)


class NotificationTest(AuditCase):  # FR-AUD-17
    def test_an_event_with_a_name(self):  # k.55
        audit, sink = self.make()

        class Evt:
            name = "Started"

        audit.update(Evt())
        self.assertIn("event=Started", sink.messages[0])

    def test_an_event_without_a_name(self):  # k.56
        audit, sink = self.make()
        audit.update(5)
        self.assertIn("event=5", sink.messages[0])

    def test_the_data_is_counted(self):  # k.57
        audit, sink = self.make()
        audit.update("e", a=1, b=2)
        self.assertIn("kwargs=<dict: 2>", sink.messages[0])


class ExtraOutputTest(AuditCase):  # FR-AUD-18
    def test_a_subscribed_output_receives_the_records(self):  # k.58
        audit, _ = self.make()
        extra = Collect()
        audit.subscribe_handler(extra)
        audit.info("x")
        self.assertIn(extra, audit._logger.handlers)
        self.assertEqual(extra.messages, ["x"])

    def test_the_same_output_is_kept_once(self):  # k.59
        audit, _ = self.make()
        extra = Collect()
        audit.subscribe_handler(extra)
        audit.subscribe_handler(extra)
        self.assertEqual(audit._logger.handlers.count(extra), 1)

    def test_a_non_handler_is_refused(self):  # k.60
        audit, _ = self.make()
        before = list(audit._logger.handlers)
        with self.assertRaisesRegex(TypeError, "subscribe_handler: expected logging.Handler"):
            audit.subscribe_handler(object())
        self.assertEqual(audit._logger.handlers, before)


if __name__ == "__main__":
    unittest.main()
