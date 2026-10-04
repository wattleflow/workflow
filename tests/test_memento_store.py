# Module name: tests/test_memento_store.py
# FRQ-MEM (DEF-MEM-01): the memento stores. MemoryMementoStore keeps snapshots in the process,
# FileMementoStore writes one JSON file per key, atomically, so the same path resumes a restarted run.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_memento_store -v
import json
import tempfile
import unittest
from pathlib import Path

from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.memento_store import (
    FileMementoStore,
    MementoStoreException,
    MemoryMementoStore,
)
from wattleflow.concrete.processor import ProcessorState


class StoreContract:
    """Behaviour every store shares."""

    def make(self):
        raise NotImplementedError

    def test_reading_an_unknown_key_gives_none(self):
        self.assertIsNone(self.make().read("a"))

    def test_a_written_snapshot_is_read_back(self):
        store = self.make()
        store.write("a", GenericMemento(cycle=3, state="FAILED"))
        self.assertEqual(store.read("a").to_dict(), {"cycle": 3, "state": "FAILED"})

    def test_a_second_write_replaces_the_first(self):
        store = self.make()
        store.write("a", GenericMemento(cycle=1))
        store.write("a", GenericMemento(cycle=2))
        self.assertEqual(store.read("a").cycle, 2)

    def test_keys_are_independent(self):
        store = self.make()
        store.write("a", GenericMemento(cycle=1))
        store.write("b", GenericMemento(cycle=2))
        store.clear("a")
        self.assertIsNone(store.read("a"))
        self.assertEqual(store.read("b").cycle, 2)

    def test_clearing_an_unknown_key_is_not_an_error(self):
        self.make().clear("nothing")

    def test_a_key_that_is_not_a_plain_name_is_rejected(self):
        store = self.make()
        for key in ("", "../escape", "a/b", "a\\b", ".", "..", None, 3):
            with self.subTest(key=key), self.assertRaises(MementoStoreException):
                store.write(key, GenericMemento(cycle=1))

    def test_only_a_memento_can_be_written(self):
        with self.assertRaises(MementoStoreException):
            self.make().write("a", {"cycle": 1})


class MemoryStoreTest(StoreContract, unittest.TestCase):
    def make(self):
        return MemoryMementoStore()

    def test_two_stores_do_not_share_snapshots(self):
        first, second = MemoryMementoStore(), MemoryMementoStore()
        first.write("a", GenericMemento(cycle=1))
        self.assertIsNone(second.read("a"))


class FileStoreTest(StoreContract, unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "snapshots"

    def make(self):
        return FileMementoStore(path=self.path)

    def test_the_same_path_resumes_in_a_new_store(self):
        self.make().write("a", GenericMemento(cycle=4, state="FAILED"))
        self.assertEqual(self.make().read("a").cycle, 4)

    def test_the_directory_is_created_on_the_first_write(self):
        self.assertFalse(self.path.exists())
        self.make().write("a", GenericMemento(cycle=1))
        self.assertTrue(self.path.is_dir())

    def test_an_enum_state_is_stored_as_its_name(self):
        self.make().write("a", GenericMemento(cycle=1, state=ProcessorState.FAILED))
        raw = json.loads((self.path / "a.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["state"], "FAILED")

    def test_no_temporary_file_is_left_behind(self):
        store = self.make()
        store.write("a", GenericMemento(cycle=1))
        store.write("a", GenericMemento(cycle=2))
        self.assertEqual([p.name for p in self.path.iterdir()], ["a.json"])

    def test_a_corrupt_file_is_an_error_not_an_empty_read(self):
        self.path.mkdir()
        (self.path / "a.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(MementoStoreException):
            self.make().read("a")

    def test_a_file_that_is_not_an_object_is_an_error(self):
        self.path.mkdir()
        (self.path / "a.json").write_text("[1, 2]", encoding="utf-8")
        with self.assertRaises(MementoStoreException):
            self.make().read("a")

    def test_a_value_that_cannot_be_stored_leaves_the_previous_snapshot(self):
        store = self.make()
        store.write("a", GenericMemento(cycle=1))
        with self.assertRaises(MementoStoreException):
            store.write("a", GenericMemento(cycle=2, handle=object()))
        self.assertEqual(store.read("a").cycle, 1)
        self.assertEqual([p.name for p in self.path.iterdir()], ["a.json"])

    def test_a_missing_path_is_a_configuration_error(self):
        with self.assertRaises(MementoStoreException):
            FileMementoStore()
        with self.assertRaises(MementoStoreException):
            FileMementoStore(path="")


class ExecuteTest(unittest.TestCase):
    def test_execute_dispatches_to_write_read_and_clear(self):
        store = MemoryMementoStore()
        store.execute(None, action="write", key="a", memento=GenericMemento(cycle=1))
        self.assertEqual(store.execute(None, action="read", key="a").cycle, 1)
        store.execute(None, action="clear", key="a")
        self.assertIsNone(store.execute(None, action="read", key="a"))

    def test_an_unknown_action_is_rejected(self):
        with self.assertRaises(MementoStoreException):
            MemoryMementoStore().execute(None, action="truncate", key="a")


if __name__ == "__main__":
    unittest.main()
