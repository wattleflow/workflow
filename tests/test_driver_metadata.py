# Module name: tests/test_driver_metadata.py
# Tests for DriverMetadata.capabilities (FRQ-DRV, DEF-DRV-05): a driver's self-description is
# checked against a controlled vocabulary when it is built (NFRQ-ORG-12, D-05).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_driver_metadata -v
import unittest

from wattleflow.concrete.driver import DriverMetadata
from wattleflow.enums.capability import DriverCapability

# The capability lists declared by the 22 drivers of `blackwattle/drivers` at v0.0.1.23.
DECLARED = [
    ["read", "write", "search"],
    ["read", "write", "complete"],
    ["read", "write"],
    ["write", "annotation:create", "annotation:update", "annotation:delete"],
    ["read"],
    ["read", "write", "search", "find"],
    ["read", "download", "update"],
    ["read", "write", "query", "query_range", "push"],
    ["read", "write", "stream"],
    ["read", "write", "validate"],
]


def metadata(capabilities):
    return DriverMetadata(name="D", version="1.0", protocol="p", capabilities=capabilities)


class VocabularyTest(unittest.TestCase):
    def test_every_capability_declared_by_a_current_driver_is_accepted(self):
        for declared in DECLARED:
            with self.subTest(declared=declared):
                self.assertEqual(metadata(list(declared)).capabilities, declared)

    def test_vocabulary_is_a_string_enumeration(self):
        self.assertTrue(issubclass(DriverCapability, str))
        self.assertEqual(DriverCapability("read"), "read")

    def test_vocabulary_holds_exactly_the_declared_tokens(self):
        used = {token for declared in DECLARED for token in declared}
        self.assertEqual({member.value for member in DriverCapability}, used)


class RefusalTest(unittest.TestCase):
    def test_unknown_capability_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "teleport"):
            metadata(["read", "teleport"])

    def test_duplicate_capability_is_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            metadata(["read", "read"])

    def test_capabilities_must_be_a_list(self):
        with self.assertRaises(TypeError):
            metadata("read")
        with self.assertRaises(TypeError):
            metadata(("read", "write"))

    def test_every_entry_must_be_a_string(self):
        with self.assertRaises(TypeError):
            metadata(["read", 3])

    def test_a_typo_in_case_is_refused(self):
        with self.assertRaises(ValueError):
            metadata(["Read"])


if __name__ == "__main__":
    unittest.main()
