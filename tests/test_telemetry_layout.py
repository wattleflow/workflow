# Module name: tests/test_telemetry_layout.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Audit is a leaf and measurement sits above it (QR-AUD-07, QR-MNT-07, SyRS-MNT-monitor section 2.1).

Run from `workflow/`: PYTHONPATH=src python -m unittest tests.test_telemetry_layout -v
"""

import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "wattleflow"
FOUNDATION = {"core", "enums", "constants"}


def imported_packages(package: str) -> dict[str, set[str]]:
    """Top-level wattleflow package imported by each module of `package`."""
    found: dict[str, set[str]] = {}
    for path in sorted((SRC / package).rglob("*.py")):
        tree = ast.parse(path.read_text())
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                parts = name.split(".")
                if parts[0] == "wattleflow" and len(parts) > 1:
                    modules.add(parts[1])
        found[str(path.relative_to(SRC))] = modules
    return found


class LayerTest(unittest.TestCase):
    def test_audit_is_a_leaf(self):  # QR-AUD-07
        allowed = FOUNDATION | {"audit"}
        for module, packages in imported_packages("audit").items():
            with self.subTest(module=module):
                self.assertLessEqual(packages, allowed)

    def test_telemetry_depends_only_on_audit_and_the_foundation(self):  # QR-MNT-07
        allowed = FOUNDATION | {"audit", "telemetry"}
        for module, packages in imported_packages("telemetry").items():
            with self.subTest(module=module):
                self.assertLessEqual(packages, allowed)

    def test_the_helpers_shelf_does_not_reach_up_to_telemetry(self):
        for module, packages in imported_packages("helpers").items():
            with self.subTest(module=module):
                self.assertNotIn("telemetry", packages)

    def test_resources_left_the_helpers_shelf(self):
        self.assertFalse((SRC / "helpers" / "resources").exists())
        self.assertTrue((SRC / "telemetry" / "resources").is_dir())


class ExportTest(unittest.TestCase):
    def test_telemetry_exports_the_measurement_names(self):
        import wattleflow.telemetry as telemetry

        self.assertEqual(
            set(telemetry.__all__),
            {"MeasurementFilter", "MetricSample", "MetricSink", "Monitor", "MonitorLevel"},
        )
        for name in telemetry.__all__:
            self.assertTrue(hasattr(telemetry, name), name)

    def test_audit_no_longer_exports_a_measurement_name(self):
        import wattleflow.audit as audit

        self.assertNotIn("MeasurementFilter", audit.__all__)
        self.assertFalse(hasattr(audit, "Monitor"))

    def test_the_unused_collector_mechanism_is_gone(self):
        import wattleflow.telemetry.metrics as metrics

        for name in ("MetricSet", "MetricCollector", "MetricReporter", "MetricSpan"):
            self.assertFalse(hasattr(metrics, name), name)
        self.assertEqual(set(metrics.__all__), {"MetricSample", "MetricSink"})

    def test_the_old_paths_do_not_import(self):
        import importlib

        for module in (
            "wattleflow.audit.monitor",
            "wattleflow.audit.metrics",
            "wattleflow.helpers.resources",
            "wattleflow.helpers.monitor",
        ):
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(module)

    def test_the_package_is_shipped(self):
        root = SRC.parent.parent
        self.assertIn('"wattleflow.telemetry*"', (root / "pyproject.toml").read_text())
        self.assertIn("src/wattleflow/telemetry", (root / "MANIFEST.in").read_text())


if __name__ == "__main__":
    unittest.main()
