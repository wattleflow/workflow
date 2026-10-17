# Module name: tests/test_document_lifetime.py
# Tests for Document lifetime (SyRS-DCM-document): collecting a document changes nothing others see;
# only an explicit clear() empties the metadata.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_document_lifetime -v
import gc
import unittest

from wattleflow.concrete.document import Document


class PlainDocument(Document[dict]):
    @property
    def size(self) -> int:
        return len(self.content)


class LifetimeTest(unittest.TestCase):
    def test_metadata_view_outlives_the_document(self):
        document = PlainDocument({"a": 1})
        document.update_metadata("filename", "x.txt")
        view = document.metadata
        del document
        gc.collect()
        self.assertEqual(view["filename"], "x.txt")
        self.assertIn("created_at", view)

    def test_explicit_clear_still_empties_the_metadata(self):
        document = PlainDocument({"a": 1})
        view = document.metadata
        document.clear()
        self.assertEqual(dict(view), {})

    def test_document_has_no_destructor(self):
        self.assertNotIn("__del__", vars(Document))


if __name__ == "__main__":
    unittest.main()
