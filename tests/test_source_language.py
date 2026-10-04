# Module name: tests/test_source_language.py
# Guard for the source language rule (CLAUDE.md §2.4, FRQ-DRV, DEF-DRV-02): code, comments and
# messages in `workflow/src` are English, so no Croatian letters appear in it.
#
# Limit (D-11): this finds Croatian diacritics only; a Croatian word without one (for example
# "stvarni") passes. Review catches those.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_source_language -v
import re
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src"
CROATIAN = re.compile(r"[čćšžđČĆŠŽĐ]")


class SourceLanguageTest(unittest.TestCase):
    def test_source_tree_is_present(self):
        self.assertTrue(any(SOURCE.rglob("*.py")))

    def test_no_croatian_letters_in_workflow_source(self):
        offenders = []
        for path in sorted(SOURCE.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if CROATIAN.search(line):
                    offenders.append(f"{path.relative_to(SOURCE)}:{number}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
