# Module name: tests/test_config.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""`Config` and `JSONConfig` load a flow description and answer `find` (concrete/config.py).

Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_config -v
"""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wattleflow.audit.exception import AuditException
from wattleflow.concrete.config import Config, JSONConfig

SECRET = "hunter2-do-not-leak"
DOCUMENT = {
    "app": {"name": "x", "items": [{"name": "a", "v": 1}], "zero": 0, "off": False, "empty": []},
    "debug": True,
}


class LeakyConfig(Config):
    """A format whose parser echoes a secret in the text of its own exception."""

    FORMAT = "LEAKY"
    ENCODING = "utf-8"
    ERRORS = (RuntimeError,)

    def _parse(self, text: str):
        raise RuntimeError(SECRET)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = Path(self._dir.name)

    def write(self, name: str, text: str | bytes) -> Path:
        path = self.dir / name
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def build(self, document=DOCUMENT) -> JSONConfig:
        return JSONConfig(self.write("ok.json", json.dumps(document)), level=logging.CRITICAL)

    # region loading (UC01)
    def test_config_file_is_a_path_for_str_and_path(self):
        path = self.write("a.json", "{}")
        self.assertEqual(JSONConfig(str(path), level=logging.CRITICAL).config_file, path)
        self.assertEqual(JSONConfig(path, level=logging.CRITICAL).config_file, path)

    def test_missing_file_raises_audit_exception(self):
        with self.assertRaises(AuditException):
            JSONConfig(self.dir / "nope.json", level=logging.CRITICAL)

    def test_bad_json_raises_value_error_with_cause(self):
        path = self.write("bad.json", "{bad")
        with self.assertRaises(ValueError) as ctx:
            JSONConfig(path, level=logging.CRITICAL)
        self.assertTrue(str(ctx.exception).startswith("Invalid JSON file:"))
        self.assertIsInstance(ctx.exception.__cause__, json.JSONDecodeError)

    def test_bad_encoding_raises_value_error_with_cause(self):
        path = self.write("bin.json", b"\xff{}")
        with self.assertRaises(ValueError) as ctx:
            JSONConfig(path, level=logging.CRITICAL)
        self.assertIsInstance(ctx.exception.__cause__, UnicodeDecodeError)

    def test_schema_violation_does_not_stop_construction(self):
        config = self.build({"debug": "yes"})
        self.assertEqual(config.find("debug"), "yes")

    def test_config_without_parse_cannot_be_built(self):
        with self.assertRaises(TypeError):
            Config(self.write("a.json", "{}"))  # type: ignore[abstract]

    # endregion

    # region find (UC02)
    def test_find_hit_and_depth(self):
        config = self.build()
        self.assertEqual(config.find("app", "name"), "x")
        self.assertEqual(config.find("app", "items", 0, "v"), 1)

    def test_find_miss_returns_default(self):
        config = self.build()
        self.assertEqual(config.find("app", "nope", default="D"), "D")
        self.assertIsNone(config.find("zzz"))

    def test_find_returns_falsy_values_not_default(self):
        config = self.build()
        self.assertEqual(config.find("app", "zero", default="D"), 0)
        self.assertIs(config.find("app", "off", default="D"), False)
        self.assertEqual(config.find("app", "empty", default="D"), [])

    # endregion

    # region NFRQ-SCR-18: error text is composed by the component
    def _records(self, method: str, build):
        with mock.patch.object(Config, method) as record:
            try:
                build()
            except Exception:
                pass
        return [repr(call) for call in record.call_args_list]

    def test_parse_failure_message_does_not_carry_foreign_text(self):
        path = self.write("x.leaky", "anything")
        with self.assertRaises(ValueError) as ctx:
            LeakyConfig(path, level=logging.CRITICAL)
        self.assertNotIn(SECRET, str(ctx.exception))
        self.assertIn("RuntimeError", str(ctx.exception))

    def test_parse_failure_log_does_not_carry_foreign_text(self):
        path = self.write("x.leaky", "anything")
        for method in ("debug", "info", "warning", "error"):
            for call in self._records(method, lambda: LeakyConfig(path, level=logging.CRITICAL)):
                self.assertNotIn(SECRET, call)

    def test_missing_file_log_does_not_carry_operating_system_text(self):
        path = self.write("a.json", "{}")
        config = JSONConfig(path, level=logging.CRITICAL)
        path.unlink()
        for method in ("debug", "error"):
            for call in self._records(method, config._load_settings):
                self.assertNotIn("No such file", call)

    def test_schema_failure_log_does_not_carry_foreign_text(self):
        path = self.write("s.json", "{}")
        target = "wattleflow.concrete.config.SchemaValidator.validate"
        with mock.patch(target, side_effect=Exception(SECRET)):
            for call in self._records("error", lambda: JSONConfig(path, level=logging.CRITICAL)):
                self.assertNotIn(SECRET, call)

    def test_find_miss_log_names_the_whole_path(self):
        config = self.build()
        calls = self._records("warning", lambda: config.find("app", "nope", "deeper"))
        self.assertEqual(len(calls), 1)
        self.assertIn("app", calls[0])
        self.assertIn("nope", calls[0])

    # endregion


if __name__ == "__main__":
    unittest.main()
