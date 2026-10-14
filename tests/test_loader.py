# Module name: tests/test_loader.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""`ClassLoader` builds a class from its dotted path (concrete/loader.py).

Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_loader -v
"""

import logging
import unittest
from collections import OrderedDict

from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.loader import ClassLoader


class Boom:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("boom")


class LoaderTest(unittest.TestCase):
    def test_it_builds_the_class_and_keeps_both(self):
        loader = ClassLoader("collections.OrderedDict", level=logging.CRITICAL)
        self.assertIs(loader.cls, OrderedDict)
        self.assertIsInstance(loader.instance, OrderedDict)

    def test_arguments_reach_the_constructor(self):
        loader = ClassLoader("collections.OrderedDict", [("a", 1)], level=logging.CRITICAL)
        self.assertEqual(dict(loader.instance), {"a": 1})

    def test_a_path_without_a_module_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Invalid class path: Plain"):
            ClassLoader("Plain", level=logging.CRITICAL)

    def test_a_missing_module_arrives_unchanged(self):
        with self.assertRaises(ModuleNotFoundError):
            ClassLoader("no_such_module_here.Thing", level=logging.CRITICAL)

    def test_a_missing_class_is_named(self):
        with self.assertRaisesRegex(
            AttributeError, "Class 'Nope' not found in module 'collections'"
        ):
            ClassLoader("collections.Nope", level=logging.CRITICAL)

    def test_a_constructor_failure_arrives_unchanged(self):
        with self.assertRaises(RuntimeError) as caught:
            ClassLoader(f"{__name__}.Boom", level=logging.CRITICAL)
        self.assertEqual(str(caught.exception), "boom")

    def test_it_is_a_framework_object_with_its_own_slots(self):
        loader = ClassLoader("collections.OrderedDict", level=logging.CRITICAL)
        self.assertIsInstance(loader, Wattleflow)
        self.assertEqual(loader.name, "ClassLoader")
        self.assertFalse(hasattr(loader, "__dict__"))

    def test_the_old_home_is_gone(self):
        import wattleflow.helpers.system as system

        self.assertFalse(hasattr(system, "ClassLoader"))


if __name__ == "__main__":
    unittest.main()
