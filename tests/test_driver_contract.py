# Module name: tests/test_driver_contract.py
# Tests for the GenericDriver contract (FRQ-DRV, DEF-DRV-01): load, close, read, write and metadata
# are abstract through IDriver, so a driver that omits one cannot be instantiated.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_driver_contract -v
import unittest

from wattleflow.concrete.driver import GenericDriver, LazyDriverProxy
from wattleflow.core import IDriver

HOOKS = {"load", "close", "read", "write"}


class Forgetful(GenericDriver):
    pass


class ReadOnly(GenericDriver):
    def read(self, uri, **kwargs):
        return None

    @classmethod
    def metadata(cls):
        return None


class AbstractContractTest(unittest.TestCase):
    def test_the_core_interface_declares_every_hook_abstract(self):
        self.assertLessEqual(HOOKS | {"metadata"}, IDriver.__abstractmethods__)

    def test_the_generic_driver_leaves_every_hook_abstract(self):
        self.assertLessEqual(HOOKS | {"metadata"}, GenericDriver.__abstractmethods__)

    def test_a_driver_without_hooks_cannot_be_instantiated(self):
        with self.assertRaisesRegex(TypeError, "abstract"):
            Forgetful(connection_name="x")

    def test_the_error_names_each_missing_hook(self):
        with self.assertRaises(TypeError) as caught:
            ReadOnly(connection_name="x")
        message = str(caught.exception)
        for hook in ("load", "close", "write"):
            self.assertIn(hook, message)
        self.assertNotIn("'read'", message)

    def test_the_lazy_proxy_defines_its_own_hooks(self):
        self.assertEqual(LazyDriverProxy.__abstractmethods__, frozenset())


if __name__ == "__main__":
    unittest.main()
