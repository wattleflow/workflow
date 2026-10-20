# Module name: tests/test_error_text.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Error text is composed by the component, never forwarded (NFRQ-SCR-18) — factory and scheduler.

Run from `workflow/`: PYTHONPATH=src:../core/src python -m unittest tests.test_error_text -v
"""

import ast
import json
import logging
import tempfile
import unittest
from pathlib import Path

from wattleflow.concrete.config import JSONConfig
from wattleflow.concrete.factory import WorkflowFactory, WorkflowFactoryException

SRC = Path(__file__).resolve().parents[1] / "src" / "wattleflow"


def forwarded_exception_text(path: Path) -> list[int]:
    """Lines where a caught exception's own text reaches a message or a record."""
    lines = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not (isinstance(node, ast.ExceptHandler) and node.name):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id in ("str", "repr")
                and sub.args
                and isinstance(sub.args[0], ast.Name)
                and sub.args[0].id == node.name
            ):
                lines.append(sub.lineno)
            if isinstance(sub, ast.FormattedValue) and isinstance(sub.value, ast.Name) and sub.value.id == node.name:
                lines.append(sub.lineno)
    return lines


class FactoryMessageTest(unittest.TestCase):
    def test_missing_sections_names_the_parameter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.json"
            path.write_text(json.dumps({"workflows": []}))
            adapter = JSONConfig(path, level=logging.CRITICAL)
            with self.assertRaises(WorkflowFactoryException) as ctx:
                WorkflowFactory.build(adapter=adapter)
        text = str(ctx.exception)
        self.assertIn("`sections`", text)
        self.assertNotIn("yaml", text.lower())


class WorkflowPackageTest(unittest.TestCase):
    def test_no_module_forwards_exception_text(self):
        found = {}
        for path in sorted(SRC.rglob("*.py")):
            lines = forwarded_exception_text(path)
            if lines:
                found[str(path.relative_to(SRC))] = lines
        self.assertEqual(found, {})


class SchedulerErrorTextTest(unittest.TestCase):
    def test_cron_job_does_not_forward_exception_text(self):
        self.assertEqual(forwarded_exception_text(SRC / "schedulers" / "cron_job.py"), [])


if __name__ == "__main__":
    unittest.main()
