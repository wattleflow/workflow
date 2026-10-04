# Module name: tests/test_processor.py
# Tests for GenericProcessor (FRQ-PRC): preconditions, the state machine across a pass, the flush
# schedule, failure handling and its state, the audit volume (2 + N INFO records), the write context
# and the destructor. Snapshots are in test_processor_restore.py and test_processor_checkpoint.py.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_processor -v
import logging
import unittest
from unittest.mock import MagicMock

from wattleflow.concrete.blackboard import GenericBlackboard
from wattleflow.concrete.exception import PipelineException, ProcessorException
from wattleflow.concrete.processor import GenericProcessor, ProcessorState
from wattleflow.core import IPipeline
from wattleflow.enums.operation import Operation

ITEMS = 4


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(range(ITEMS))


class WithContext(Processor):
    __slots__ = ()

    @property
    def write_context(self):
        return {"skip": "x"}


class BrokenGenerator(Processor):
    __slots__ = ()

    def create_generator(self):
        raise RuntimeError("source down")


def build(cls=Processor, fail_on=None, flush_result=True, **kwargs):
    seen = []

    def process(processor, facade):
        if facade == fail_on:
            raise RuntimeError("pipeline down")
        seen.append(facade)

    pipeline = MagicMock(spec=IPipeline)
    pipeline.process.side_effect = process
    blackboard = MagicMock(spec=GenericBlackboard)
    blackboard.flush.return_value = flush_result
    processor = cls(blackboard=blackboard, pipelines=[pipeline], level=logging.DEBUG, **kwargs)
    return processor, blackboard, pipeline, seen


class PreconditionTest(unittest.TestCase):
    def test_no_blackboard_is_refused_before_the_opening_record(self):
        processor = Processor(pipelines=[MagicMock(spec=IPipeline)], level=logging.DEBUG)
        with self.assertNoLogs(level=logging.INFO), self.assertRaises(ProcessorException):
            processor.start()

    def test_no_pipeline_is_refused_before_the_opening_record(self):
        processor = Processor(blackboard=MagicMock(spec=GenericBlackboard), level=logging.DEBUG)
        with self.assertNoLogs(level=logging.INFO), self.assertRaises(ProcessorException):
            processor.start()

    def test_create_generator_is_the_only_abstract_method(self):
        self.assertEqual(GenericProcessor.__abstractmethods__, frozenset({"create_generator"}))


class PassTest(unittest.TestCase):
    def test_every_item_goes_through_every_pipeline_in_order(self):
        processor, _, pipeline, seen = build()
        processor.start()
        self.assertEqual(seen, list(range(ITEMS)))
        self.assertEqual(processor.cycle, ITEMS)
        self.assertEqual(pipeline.process.call_count, ITEMS)

    def test_the_state_machine_ends_completed(self):
        processor, *_ = build()
        self.assertIs(processor._fsm.state, ProcessorState.IDLE)
        processor.start()
        self.assertIs(processor._fsm.state, ProcessorState.COMPLETED)

    def test_info_volume_is_two_plus_one_per_item(self):
        processor, *_ = build()
        with self.assertLogs(level=logging.INFO) as logged:
            processor.start()
        infos = [r for r in logged.records if r.levelno == logging.INFO]
        self.assertEqual(len(infos), 2 + ITEMS)

    def test_an_unsupported_operation_warns_and_returns_false(self):
        processor, *_ = build()
        with self.assertLogs(level=logging.WARNING):
            self.assertFalse(processor.operation(Operation.Stop))

    def test_operation_start_runs_the_pass(self):
        processor, *_ = build()
        self.assertTrue(processor.operation(Operation.Start))
        self.assertEqual(processor.cycle, ITEMS)


class FlushScheduleTest(unittest.TestCase):
    def test_the_canvas_is_flushed_after_every_item_by_default(self):
        processor, blackboard, *_ = build()
        processor.start()
        self.assertEqual(blackboard.flush.call_count, ITEMS)

    def test_without_flush_per_cycle_the_canvas_is_flushed_once_at_the_end(self):
        processor, blackboard, *_ = build(flush_per_cycle=False)
        processor.start()
        self.assertEqual(blackboard.flush.call_count, 1)

    def test_nothing_is_flushed_at_the_end_when_there_were_no_items(self):
        class Empty(Processor):
            __slots__ = ()

            def create_generator(self):
                return iter(())

        processor, blackboard, *_ = build(Empty, flush_per_cycle=False)
        processor.start()
        self.assertEqual(blackboard.flush.call_count, 0)

    def test_a_failed_pass_does_not_flush_at_the_end(self):
        processor, blackboard, *_ = build(fail_on=2, flush_per_cycle=False)
        with self.assertRaises(PipelineException):
            processor.start()
        self.assertEqual(blackboard.flush.call_count, 0)

    def test_the_write_context_reaches_every_flush(self):
        processor, blackboard, *_ = build(WithContext)
        processor.start()
        for call in blackboard.flush.call_args_list:
            self.assertEqual(call.kwargs["skip"], "x")
            self.assertIs(call.kwargs["caller"], processor)

    def test_the_write_context_is_empty_by_default(self):
        self.assertEqual(Processor().write_context, {})

    def test_the_flush_outcome_is_the_answer_of_the_last_item(self):
        for answer, expected in ((True, True), (False, False), ("yes", None), (None, None)):
            with self.subTest(answer=answer):
                processor, *_ = build(flush_result=answer)
                processor.start()
                self.assertIs(processor.flush_outcome, expected)

    def test_the_flush_outcome_is_unknown_without_a_flush(self):
        processor, *_ = build(flush_per_cycle=False)
        processor.start()
        self.assertIsNone(processor.flush_outcome)


class FailureTest(unittest.TestCase):
    def test_a_pipeline_failure_is_a_pipeline_exception_with_its_cause(self):
        processor, *_ = build(fail_on=2)
        with self.assertRaises(PipelineException) as caught:
            processor.start()
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(processor.cycle, 2)

    def test_it_is_not_wrapped_twice(self):
        processor, *_ = build(fail_on=1)
        with self.assertRaises(PipelineException) as caught:
            processor.start()
        self.assertNotIsInstance(caught.exception.__cause__, PipelineException)

    def test_a_pipeline_failure_leaves_the_machine_failed_so_that_a_resume_is_possible(self):
        processor, *_ = build(fail_on=1)
        with self.assertRaises(PipelineException):
            processor.start()
        self.assertIs(processor._fsm.state, ProcessorState.FAILED)

    def test_a_failure_before_the_pass_starts_is_a_processor_exception_and_changes_no_state(self):
        processor, *_ = build(BrokenGenerator)
        with self.assertRaises(ProcessorException):
            processor.start()
        self.assertIs(processor._fsm.state, ProcessorState.IDLE)  # START was never applied

    def test_a_failure_in_the_final_flush_fails_the_pass(self):
        processor, blackboard, *_ = build(flush_per_cycle=False)
        blackboard.flush.side_effect = RuntimeError("repository down")
        with self.assertRaises(ProcessorException):
            processor.start()
        self.assertIs(processor._fsm.state, ProcessorState.FAILED)


class DestructorTest(unittest.TestCase):
    def test_discarding_a_processor_does_not_raise(self):
        processor, *_ = build()
        processor.start()
        processor.__del__()
        processor.__del__()  # a second call finds nothing and still does not raise

    def test_discarding_a_processor_that_never_finished_construction_does_not_raise(self):
        bare = Processor.__new__(Processor)
        bare.__del__()


if __name__ == "__main__":
    unittest.main()
