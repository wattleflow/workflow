# Module name: tests/test_processor_restore.py
# FRQ-MEM (DEF-MEM-04): restore_state rejects a snapshot whose `state` or `cycle` is missing or of the wrong
# type with ProcessorException, before anything is changed.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_processor_restore -v
import unittest

from wattleflow.concrete.exception import ProcessorException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.processor import GenericProcessor, ProcessorState


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(range(10))


class RestoreRejectionTest(unittest.TestCase):
    def reject(self, memento):
        processor = Processor()
        with self.assertRaises(ProcessorException):
            processor.restore_state(memento)
        return processor

    def test_a_snapshot_without_state_is_rejected(self):
        self.reject(GenericMemento(cycle=2))

    def test_a_state_that_is_not_a_processor_state_is_rejected(self):
        self.reject(GenericMemento(cycle=2, state="IDLE"))

    def test_a_snapshot_without_cycle_is_rejected(self):
        self.reject(GenericMemento(state=ProcessorState.IDLE))

    def test_a_cycle_that_is_not_a_non_negative_int_is_rejected(self):
        for cycle in ("2", -1, 1.5, None, True):
            with self.subTest(cycle=cycle):
                self.reject(GenericMemento(cycle=cycle, state=ProcessorState.IDLE))

    def test_a_rejected_snapshot_changes_nothing(self):
        processor = self.reject(GenericMemento(state=ProcessorState.FAILED))
        self.assertIs(processor._fsm.state, ProcessorState.IDLE)
        self.assertEqual(processor._cycle, 0)
        self.assertIsNone(processor._generator)

    def test_a_state_without_a_load_transition_is_still_rejected(self):
        self.reject(GenericMemento(cycle=1, state=ProcessorState.RUNNING))


class RestoreAcceptanceTest(unittest.TestCase):
    def test_a_valid_snapshot_resumes_after_the_saved_cycle(self):
        processor = Processor()
        processor.restore_state(GenericMemento(cycle=3, state=ProcessorState.IDLE))
        self.assertIs(processor._fsm.state, ProcessorState.STATE_LOADED)
        self.assertEqual(processor._cycle, 3)
        self.assertEqual(next(processor._generator), 3)

    def test_a_cycle_beyond_the_dataset_is_rejected(self):
        processor = Processor()
        with self.assertRaises(ProcessorException):
            processor.restore_state(GenericMemento(cycle=20, state=ProcessorState.IDLE))

    def test_save_then_restore_round_trips(self):
        processor = Processor()
        snapshot = processor.save_state()
        Processor().restore_state(snapshot)


if __name__ == "__main__":
    unittest.main()
