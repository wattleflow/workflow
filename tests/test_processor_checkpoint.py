# Module name: tests/test_processor_checkpoint.py
# FRQ-MEM (DEF-MEM-01): a processor given a memento store checkpoints after each cycle, resumes after the
# saved cycle when it starts again under the same name, and clears the checkpoint once the run completes.
# Without a store nothing is saved, read or cleared.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_processor_checkpoint -v
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wattleflow.concrete.exception import PipelineException, ProcessorException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.memento_store import (
    FileMementoStore,
    MementoStoreException,
    MemoryMementoStore,
)
from wattleflow.concrete.processor import GenericProcessor
from wattleflow.concrete.blackboard import GenericBlackboard
from wattleflow.core import IPipeline

ITEMS = 5


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(range(ITEMS))


def build(store=None, fail_on=None, key="proc", **kwargs):
    seen = []

    def process(processor, facade):
        if facade == fail_on:
            raise RuntimeError("pipeline down")
        seen.append(facade)

    pipeline = MagicMock(spec=IPipeline)
    pipeline.process.side_effect = process
    blackboard = MagicMock(spec=GenericBlackboard)
    blackboard.flush.return_value = True
    processor = Processor(
        memento_key=key, blackboard=blackboard, pipelines=[pipeline], memento_store=store, **kwargs
    )
    return processor, seen


class CheckpointTest(unittest.TestCase):
    def test_a_failed_run_leaves_a_checkpoint_after_the_last_completed_cycle(self):
        store = MemoryMementoStore()
        processor, _ = build(store, fail_on=3)
        with self.assertRaises(PipelineException):
            processor.start()
        saved = store.read("proc")
        self.assertEqual(saved.cycle, 3)
        self.assertEqual(saved.state, "FAILED")

    def test_a_restarted_processor_resumes_after_the_saved_cycle(self):
        store = MemoryMementoStore()
        first, _ = build(store, fail_on=3)
        with self.assertRaises(PipelineException):
            first.start()
        second, seen = build(store)
        second.start()
        self.assertEqual(seen, [3, 4])
        self.assertEqual(second.cycle, ITEMS)

    def test_a_completed_run_clears_the_checkpoint(self):
        store = MemoryMementoStore()
        processor, seen = build(store)
        processor.start()
        self.assertEqual(seen, list(range(ITEMS)))
        self.assertIsNone(store.read("proc"))

    def test_the_run_after_a_completed_one_starts_from_the_beginning(self):
        store = MemoryMementoStore()
        build(store)[0].start()
        processor, seen = build(store)
        processor.start()
        self.assertEqual(seen, list(range(ITEMS)))

    def test_each_processor_resumes_from_its_own_checkpoint(self):
        store = MemoryMementoStore()
        a, _ = build(store, fail_on=2, key="a")
        with self.assertRaises(PipelineException):
            a.start()
        other, seen = build(store, key="b")
        other.start()
        self.assertEqual(seen, list(range(ITEMS)))
        self.assertEqual(store.read("a").cycle, 2)

    def test_checkpoint_every_n_saves_on_every_nth_cycle(self):
        store = MemoryMementoStore()
        with patch.object(MemoryMementoStore, "write", wraps=store.write) as write:
            processor, _ = build(store, fail_on=4, checkpoint_every=2)
            with self.assertRaises(PipelineException):
                processor.start()
        self.assertEqual([c.args[1].cycle for c in write.call_args_list], [2, 4])

    def test_without_a_store_nothing_is_saved(self):
        processor, seen = build(None)
        processor.start()
        self.assertEqual(seen, list(range(ITEMS)))

    def test_a_store_without_flush_per_cycle_is_rejected(self):
        with self.assertRaises(ProcessorException):
            build(MemoryMementoStore(), flush_per_cycle=False)

    def test_a_checkpoint_every_that_is_not_a_positive_int_is_rejected(self):
        for value in (0, -1, 1.5, "2", True):
            with self.subTest(value=value), self.assertRaises(ProcessorException):
                build(MemoryMementoStore(), checkpoint_every=value)

    def test_a_store_that_is_not_a_store_is_rejected(self):
        with self.assertRaises(ProcessorException):
            build(object())


class FileResumeTest(unittest.TestCase):
    def test_a_new_store_on_the_same_path_resumes_a_failed_run(self):
        with tempfile.TemporaryDirectory() as folder:
            first, _ = build(FileMementoStore(path=folder), fail_on=3)
            with self.assertRaises(PipelineException):
                first.start()
            second, seen = build(FileMementoStore(path=folder))
            second.start()
            self.assertEqual(seen, [3, 4])
            self.assertEqual(list(Path(folder).iterdir()), [])


class StoreFailureTest(unittest.TestCase):
    def test_a_failed_write_does_not_stop_the_run(self):
        store = MemoryMementoStore()
        processor, seen = build(store)
        with patch.object(MemoryMementoStore, "write", side_effect=MementoStoreException(None, "disk full")):
            processor.start()
        self.assertEqual(seen, list(range(ITEMS)))

    def test_a_failed_write_is_audited(self):
        store = MemoryMementoStore()
        processor, _ = build(store)
        with patch.object(MemoryMementoStore, "write", side_effect=MementoStoreException(None, "disk full")):
            with self.assertLogs(level="WARNING") as logged:
                processor.start()
        text = "\n".join(logged.output)
        self.assertIn("Save", text)
        self.assertIn("disk full", text)

    def test_an_unreadable_checkpoint_stops_the_start(self):
        store = MemoryMementoStore()
        processor, seen = build(store)
        with patch.object(MemoryMementoStore, "read", side_effect=MementoStoreException(None, "corrupt")):
            with self.assertRaises(ProcessorException):
                processor.start()
        self.assertEqual(seen, [])

    def test_a_checkpoint_that_is_not_a_valid_snapshot_stops_the_start(self):
        store = MemoryMementoStore()
        store.write("proc", GenericMemento(cycle=2, state="NO_SUCH_STATE"))
        processor, seen = build(store)
        with self.assertRaises(ProcessorException):
            processor.start()
        self.assertEqual(seen, [])

    def test_a_failed_clear_does_not_fail_a_completed_run(self):
        store = MemoryMementoStore()
        processor, seen = build(store)
        with patch.object(MemoryMementoStore, "clear", side_effect=MementoStoreException(None, "locked")):
            processor.start()
        self.assertEqual(seen, list(range(ITEMS)))


if __name__ == "__main__":
    unittest.main()
