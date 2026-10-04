# Module name: tests/test_workflow_memento.py
# FRQ-MEM (DEF-MEM-01): a workflow needs no memento code of its own. GenericWorkflow snapshots and restores
# its processors by registered name, and the factory turns a `memento:` section into a store that every
# processor of the workflow checkpoints to, keyed by its registered name.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_workflow_memento -v
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wattleflow.concrete.exception import ProcessorException
from wattleflow.concrete.manager import ConnectionManager, DriverManager, ProcessorManager
from wattleflow.concrete.memento import GenericMemento
from wattleflow.concrete.memento_store import FileMementoStore, MemoryMementoStore
from wattleflow.concrete.processor import GenericProcessor, ProcessorState
from wattleflow.concrete.workflow import (
    GenericWorkflow,
    WorkflowException,
    WorkflowFactory,
    WorkflowFactoryException,
)
from wattleflow.core import IConfig


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(range(10))


class Board:
    def __init__(self, **kwargs):
        pass


class Create:
    def __init__(self, **kwargs):
        pass


class Workflow(GenericWorkflow):
    """A workflow class with no memento code: only `execute`."""

    def execute(self, **kwargs):
        pass


def workflow_with(*names):
    processors = ProcessorManager()
    for name in names:
        processors.register_processor(processor=Processor(), name=name)
    return Workflow(
        adapter=MagicMock(spec=IConfig),
        connections=ConnectionManager(),
        drivers=DriverManager(),
        processors=processors,
    )


class WorkflowSnapshotTest(unittest.TestCase):
    def test_a_workflow_without_memento_code_can_be_built(self):
        workflow_with("a")

    def test_the_snapshot_holds_one_memento_per_processor_name(self):
        saved = workflow_with("a", "b").save_state().to_dict()["processors"]
        self.assertEqual(sorted(saved), ["a", "b"])
        self.assertTrue(all(isinstance(m, GenericMemento) for m in saved.values()))

    def test_restore_hands_each_processor_its_own_snapshot(self):
        workflow = workflow_with("a", "b")
        memento = GenericMemento(
            processors={
                "a": GenericMemento(cycle=2, state=ProcessorState.FAILED),
                "b": GenericMemento(cycle=4, state=ProcessorState.FAILED),
            }
        )
        workflow.restore_state(memento)
        self.assertEqual(workflow.processors.all["a"].cycle, 2)
        self.assertEqual(workflow.processors.all["b"].cycle, 4)

    def test_a_snapshot_for_an_unknown_processor_changes_nothing(self):
        workflow = workflow_with("a")
        memento = GenericMemento(
            processors={
                "a": GenericMemento(cycle=2, state=ProcessorState.FAILED),
                "ghost": GenericMemento(cycle=1, state=ProcessorState.FAILED),
            }
        )
        with self.assertRaises(WorkflowException):
            workflow.restore_state(memento)
        self.assertEqual(workflow.processors.all["a"].cycle, 0)

    def test_an_invalid_snapshot_is_rejected(self):
        workflow = workflow_with("a")
        for memento in (
            {"processors": {}},
            GenericMemento(),
            GenericMemento(processors=[1]),
            GenericMemento(processors={"a": "x"}),
        ):
            with self.subTest(memento=memento), self.assertRaises(WorkflowException):
                workflow.restore_state(memento)

    def test_a_snapshot_a_processor_rejects_is_not_hidden(self):
        workflow = workflow_with("a")
        bad = GenericMemento(processors={"a": GenericMemento(cycle=1, state=ProcessorState.RUNNING)})
        with self.assertRaises(ProcessorException):
            workflow.restore_state(bad)


def entry(**extra):
    return {
        "name": "wf",
        "type": "Workflow",
        "processors": [
            {
                "name": "reader",
                "type": "Processor",
                "blackboard": {"type": "Board", "strategy_create": "Create"},
            },
            {
                "name": "writer",
                "type": "Processor",
                "blackboard": {"type": "Board", "strategy_create": "Create"},
            },
        ],
        **extra,
    }


class FactoryMementoTest(unittest.TestCase):
    def setUp(self):
        saved = dict(WorkflowFactory._registry)
        self.addCleanup(lambda: (WorkflowFactory._registry.clear(), WorkflowFactory._registry.update(saved)))
        for cls in (Processor, Board, Create):
            WorkflowFactory.register(cls.__name__, cls)

    def processors(self, workflow):
        with patch.object(Processor, "register_blackboard"):
            return WorkflowFactory._build_processors(
                workflow, DriverManager(), handler=None, formatting=None
            )

    def test_no_memento_section_means_no_store(self):
        self.assertEqual(WorkflowFactory._build_memento(entry()), (None, None))
        manager = self.processors(entry())
        for processor in manager.all.values():
            self.assertIsNone(processor._memento_store)

    def test_a_memory_store_is_built_from_its_short_name(self):
        store, every = WorkflowFactory._build_memento(entry(memento={"store": "memory"}))
        self.assertIsInstance(store, MemoryMementoStore)
        self.assertIsNone(every)

    def test_a_file_store_is_built_with_its_path(self):
        with tempfile.TemporaryDirectory() as folder:
            store, every = WorkflowFactory._build_memento(
                entry(memento={"store": "file", "path": folder, "checkpoint_every": 5})
            )
            self.assertIsInstance(store, FileMementoStore)
            self.assertEqual(store.path, Path(folder))
            self.assertEqual(every, 5)

    def test_a_registered_store_class_can_be_named(self):
        class Custom(MemoryMementoStore):
            pass

        WorkflowFactory.register("Custom", Custom)
        store, _ = WorkflowFactory._build_memento(entry(memento={"store": "Custom"}))
        self.assertIsInstance(store, Custom)

    def test_a_bad_memento_section_is_a_configuration_error(self):
        for section in (
            "file",
            {"store": "nope"},
            {},
            {"store": "file"},
            {"store": "Processor"},
        ):
            with self.subTest(section=section), self.assertRaises(WorkflowFactoryException):
                WorkflowFactory._build_memento(entry(memento=section))

    def test_every_processor_gets_the_store_and_its_registered_name_as_key(self):
        workflow = entry(memento={"store": "memory", "checkpoint_every": 3})
        manager = self.processors(workflow)
        processors = manager.all
        stores = {id(p._memento_store) for p in processors.values()}
        self.assertEqual(len(stores), 1)
        self.assertEqual({n: p._memento_key for n, p in processors.items()},
                         {"reader": "reader", "writer": "writer"})
        self.assertTrue(all(p._checkpoint_every == 3 for p in processors.values()))

    def test_a_processor_name_that_is_not_a_plain_key_is_rejected_at_build(self):
        workflow = entry(memento={"store": "memory"})
        workflow["processors"][0]["name"] = "../reader"
        with self.assertRaises(WorkflowFactoryException):
            self.processors(workflow)


if __name__ == "__main__":
    unittest.main()
