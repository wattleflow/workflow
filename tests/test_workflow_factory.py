# Module name: tests/test_workflow_factory.py
# Tests for WorkflowFactory (FRQ-WFL): registration that cannot be undone silently, a build whose own
# records follow the level the operator can see, entries whose inline keys do not vanish unreported,
# runtime values that never reach the audit trail, and one factory exception for a missing driver.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_workflow_factory -v
import logging
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from wattleflow.concrete.manager import DriverManager
from wattleflow.concrete.processor import GenericProcessor
from wattleflow.concrete.workflow import (
    GenericWorkflow,
    WorkflowFactory,
    WorkflowFactoryException,
    logger as factory_logger,
)
from wattleflow.core import IConfig


class DictConfig(IConfig):
    """An IConfig over a nested dict: `find(*keys)` walks it."""

    def __init__(self, data):
        self.data = data

    @property
    def name(self):
        return "DictConfig"

    def find(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


class Workflow(GenericWorkflow):
    def execute(self, **kwargs):
        pass


class Proc(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(())


class Board:
    def __init__(self, **kwargs):
        pass


class Create:
    def __init__(self, **kwargs):
        pass


class Fake:
    """A driver/connection stand-in that accepts any keyword."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.name = kwargs.get("name", "fake")


SECTIONS = ("infrastructure", "dev")


class Capture(logging.Handler):
    """Collects what reaches the factory logger WITHOUT changing its level (assertLogs would)."""

    def __init__(self):
        super().__init__(logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@contextmanager
def captured():
    handler, target = Capture(), factory_logger._logger
    target.addHandler(handler)
    try:
        yield handler.records
    finally:
        target.removeHandler(handler)


def document(driver_entry=None, processor_extra=None, workflow_extra=None, logging_level=None):
    processor = {
        "name": "reader",
        "type": "Proc",
        "blackboard": {"type": "Board", "strategy_create": "Create"},
    }
    processor.update(processor_extra or {})
    workflow = {"name": "wf", "type": "Workflow", "processors": [processor]}
    workflow.update(workflow_extra or {})
    dev = {"workflows": [workflow], "managers": {"drivers": [driver_entry] if driver_entry else []}}
    if logging_level:
        dev["logging"] = {"level": logging_level}
    return DictConfig({"infrastructure": {"dev": dev}})


class Isolated(unittest.TestCase):
    """Each test gets its own registry and leaves the factory logger and environment as found."""

    def setUp(self):
        saved = dict(WorkflowFactory._registry)
        self.addCleanup(lambda: (WorkflowFactory._registry.clear(), WorkflowFactory._registry.update(saved)))
        for cls in (Workflow, Proc, Board, Create, Fake):
            WorkflowFactory.register(cls.__name__, cls)
        self.addCleanup(factory_logger.set_level, factory_logger._level)
        self.addCleanup(logging.getLogger().setLevel, logging.getLogger().level)
        env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(env)))

    def build(self, config):
        with patch.object(Proc, "register_blackboard"):
            return WorkflowFactory.build(adapter=config, sections=SECTIONS)


class RegistrationTest(Isolated):
    def test_only_a_class_can_be_registered(self):
        for bad in (42, "Workflow", None, Fake()):
            with self.subTest(bad=bad), self.assertRaises(WorkflowFactoryException):
                WorkflowFactory.register("Thing", bad)

    def test_registering_the_same_class_again_is_silent(self):
        with self.assertNoLogs(factory_logger._logger, level=logging.WARNING):
            WorkflowFactory.register("Workflow", Workflow)

    def test_replacing_a_name_with_another_class_is_reported(self):
        class Other(Workflow):
            pass

        factory_logger.set_level(logging.DEBUG)
        with self.assertLogs(factory_logger._logger, level=logging.WARNING) as logged:
            WorkflowFactory.register("Workflow", Other)
        self.assertIn("Workflow", "\n".join(logged.output))
        self.assertIs(WorkflowFactory.resolve("Workflow"), Other)

    def test_an_unknown_name_names_the_close_candidates(self):
        with self.assertRaises(WorkflowFactoryException) as caught:
            WorkflowFactory.resolve("Workflw")
        self.assertIn("Workflow", str(caught.exception))


class LevelTest(Isolated):
    def messages(self, records, level=logging.INFO):
        return [r.getMessage() for r in records if r.levelno >= level]

    def test_without_a_declared_level_the_factory_follows_the_root_level(self):
        logging.getLogger().setLevel(logging.INFO)
        with captured() as records:
            self.build(document())
        self.assertTrue(any("Build" in m for m in self.messages(records)))

    def test_a_root_level_above_info_keeps_the_build_quiet(self):
        logging.getLogger().setLevel(logging.WARNING)
        with captured() as records:
            self.build(document())
        self.assertEqual(self.messages(records), [])

    def test_a_declared_level_wins(self):
        logging.getLogger().setLevel(logging.WARNING)
        with captured() as records:
            self.build(document(logging_level="INFO"))
        self.assertTrue(any("Build" in m for m in self.messages(records)))


class InlineKeysTest(Isolated):
    def test_an_unknown_inline_key_on_a_driver_is_reported_with_section_and_key(self):
        logging.getLogger().setLevel(logging.WARNING)
        with self.assertLogs(factory_logger._logger, level=logging.WARNING) as logged:
            self.build(document(driver_entry={"name": "d", "type": "Fake", "stray": 1}))
        text = "\n".join(logged.output)
        for part in ("managers.drivers", "stray"):
            self.assertIn(part, text)

    def test_the_declared_structural_keys_are_not_reported(self):
        logging.getLogger().setLevel(logging.WARNING)
        entry = {"name": "d", "type": "Fake", "description": "x", "level": "INFO", "configuration": {}}
        with self.assertNoLogs(factory_logger._logger, level=logging.WARNING):
            self.build(document(driver_entry=entry))

    def test_an_unknown_inline_key_on_a_processor_is_reported(self):
        logging.getLogger().setLevel(logging.WARNING)
        with self.assertLogs(factory_logger._logger, level=logging.WARNING) as logged:
            self.build(document(processor_extra={"pattern": "*.md"}))
        self.assertIn("pattern", "\n".join(logged.output))

    def test_a_key_inside_configuration_is_not_an_inline_key(self):
        logging.getLogger().setLevel(logging.WARNING)
        with self.assertNoLogs(factory_logger._logger, level=logging.WARNING):
            self.build(document(processor_extra={"configuration": {"pattern": "*.md"}}))


class RuntimeEnvTest(Isolated):
    def test_known_keys_are_exported_and_traced_with_their_paths(self):
        factory_logger.set_level(logging.DEBUG)
        with self.assertLogs(factory_logger._logger, level=logging.DEBUG) as logged:
            self.build(document(workflow_extra={"runtime": {"java_home": "/opt/java"}}))
        self.assertEqual(os.environ["JAVA_HOME"], "/opt/java")
        self.assertIn("JAVA_HOME", "\n".join(logged.output))

    def test_extra_env_values_are_exported_but_never_written_to_the_audit_trail(self):
        factory_logger.set_level(logging.DEBUG)
        runtime = {"env": {"API_TOKEN": "s3cret-value"}}
        with self.assertLogs(factory_logger._logger, level=logging.DEBUG) as logged:
            self.build(document(workflow_extra={"runtime": runtime}))
        self.assertEqual(os.environ["API_TOKEN"], "s3cret-value")
        text = "\n".join(logged.output)
        self.assertIn("API_TOKEN", text)
        self.assertNotIn("s3cret-value", text)


class DriverLookupTest(Isolated):
    def test_an_unknown_processor_driver_is_a_factory_exception_naming_the_entry(self):
        with self.assertRaises(WorkflowFactoryException) as caught:
            self.build(document(processor_extra={"driver": "nowhere"}))
        text = str(caught.exception)
        for part in ("nowhere", "reader"):
            self.assertIn(part, text)

    def test_a_registered_driver_reaches_the_processor(self):
        config = document(driver_entry={"name": "d", "type": "Fake"}, processor_extra={"driver": "d"})
        built = self.build(config)
        self.assertIn("reader", built.processors.all)
        self.assertIsInstance(built.drivers, DriverManager)


class CleanupTest(unittest.TestCase):
    def test_the_dead_default_table_is_gone(self):
        self.assertFalse(hasattr(WorkflowFactory, "_strategy_defaults"))


if __name__ == "__main__":
    unittest.main()
