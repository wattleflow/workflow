# Module name: tests/test_document_hash.py
# Tests for Document hashing (SyRS-DCM-document): a document is hashable, and the hash
# agrees with __eq__ (same type and identifier).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_hash -v
import unittest

from wattleflow.concrete.document import Document


class PlainDocument(Document[dict]):
    @property
    def size(self) -> int:
        return len(self.content)


class OtherDocument(PlainDocument):
    pass


class DocumentHashTest(unittest.TestCase):
    def setUp(self):
        self.document = PlainDocument({"a": 1})

    def test_document_is_hashable(self):
        self.assertIsInstance(hash(self.document), int)

    def test_document_can_be_a_set_member(self):
        self.assertIn(self.document, {self.document})

    def test_document_can_be_a_dictionary_key(self):
        self.assertEqual({self.document: "kept"}[self.document], "kept")

    def test_distinct_documents_stay_distinct_in_a_set(self):
        self.assertEqual(len({self.document, PlainDocument({"a": 1})}), 2)

    def test_equal_documents_hash_equally(self):
        twin = PlainDocument({"a": 1})
        twin._identifier = self.document.identifier
        self.assertEqual(self.document, twin)
        self.assertEqual(hash(self.document), hash(twin))
        self.assertEqual(len({self.document, twin}), 1)

    def test_same_identifier_of_another_type_is_not_equal(self):
        other = OtherDocument({"a": 1})
        other._identifier = self.document.identifier
        self.assertNotEqual(self.document, other)

    def test_hash_is_stable_while_the_document_changes(self):
        before = hash(self.document)
        self.document.update_metadata("note", "changed")
        self.document.update_content({"notice": "other"})
        self.document.clear()
        self.assertEqual(hash(self.document), before)


if __name__ == "__main__":
    unittest.main()
