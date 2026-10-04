# Module name: tools/tests/test_wem_lint_event.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""`Event` member detection in audit calls: the member and `.name` read the same."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

__TOOL__ = Path(__file__).resolve().parent.parent / "wem_lint.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("wem_lint", __TOOL__)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wem_lint"] = module
    spec.loader.exec_module(module)
    return module


wem = _load_tool()


def member(expression: str) -> str | None:
    return wem.AuditRuleBase._event_member(ast.parse(expression, mode="eval").body, "Event")


class EventMemberTest(unittest.TestCase):
    def test_member_and_name_read_the_same(self) -> None:
        self.assertEqual(member("Event.Write"), "Write")
        self.assertEqual(member("Event.Write.name"), "Write")

    def test_anything_else_is_none(self) -> None:
        for expression in ("'Write'", "Other.Write", "Event.Write.value", "self.name", "Event"):
            with self.subTest(expression=expression):
                self.assertIsNone(member(expression))


if __name__ == "__main__":
    unittest.main()
