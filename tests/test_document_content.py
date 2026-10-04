# Module name: tests/test_document_content.py
# Tests for Document content (FRQ-DOC, DEF-DOC-02): None is not legal content; content leaves a
# document only through clean(), and reading it afterwards fails fast.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_content -v
import unittest

from wattleflow.concrete.document import Document, DummyReadDocument


class PlainDocument(Document[dict]):
    @property
    def size(self) -> int:
        return len(self.content)


class ContentRefusalTest(unittest.TestCase):
    def setUp(self):
        self.document = PlainDocument({"a": 1})

    def test_construction_with_none_is_refused(self):
        with self.assertRaises(ValueError):
            PlainDocument(None)

    def test_update_with_none_is_refused(self):
        with self.assertRaises(ValueError):
            self.document.update_content(None)

    def test_refused_update_leaves_content_and_audit_keys_unchanged(self):
        before = (self.document.content, dict(self.document.metadata))
        with self.assertRaises(ValueError):
            self.document.update_content(None)
        self.assertEqual((self.document.content, dict(self.document.metadata)), before)

    def test_content_never_raises_while_the_document_holds_content(self):
        self.assertEqual(self.document.content, {"a": 1})
        self.assertEqual(self.document.size, 1)


class ContentLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.document = PlainDocument({"a": 1})

    def test_update_replaces_content(self):
        self.document.update_content({"b": 2})
        self.assertEqual(self.document.content, {"b": 2})

    def test_wrong_type_is_still_refused(self):
        with self.assertRaises(TypeError):
            self.document.update_content([1])

    def test_reading_content_after_clean_fails_fast(self):
        self.document.clean()
        with self.assertRaises(ValueError):
            _ = self.document.content

    def test_placeholder_document_is_unaffected(self):
        placeholder = DummyReadDocument(identifier="x")
        self.assertEqual(placeholder.size, len(placeholder.content))


if __name__ == "__main__":
    unittest.main()
