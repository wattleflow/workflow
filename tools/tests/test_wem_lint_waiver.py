"""Waiver `documented` — the `rq`/`version` obligations of a criterion's `rules` block.

Every assertion is a claim about `Criterion.validate_documentation` and about the
reader that calls it. The tool is loaded from its path; when the framework import
fails for an unrelated reason (a broken `concrete` package), a stand-in for the two
names the tool takes from it is used for the load and removed again, so no other
test module sees it.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Generic, TypeVar

__TOOL__ = Path(__file__).resolve().parent.parent / "wem_lint.py"


def _load_tool():
    def load():
        spec = importlib.util.spec_from_file_location("wem_lint_waiver_under_test", __TOOL__)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    try:
        return load()
    except Exception:  # noqa: BLE001 — unrelated framework fault, see module docstring
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("wattleflow.concrete")}
        item = TypeVar("item")

        class LazyIterator(Generic[item]):
            pass

        stub = types.ModuleType("wattleflow.concrete")
        stub.LazyIterator = LazyIterator
        stub.Wattleflow = type("Wattleflow", (), {})
        sys.modules["wattleflow.concrete"] = stub
        try:
            return load()
        finally:
            sys.modules.pop("wattleflow.concrete", None)
            sys.modules.update(saved)


wem = _load_tool()

BASE = {
    "domains": ["pipelines"],
    "documentation_version": "v0.0.5",
    "scope": {"guarded_optional": []},
    "rules": [
        {"id": "R1", "nfr": "NFRQ-ORG-01", "check": "domain_acyclicity", "severity": "error", "waiver": "documented"},
        {"id": "R2", "nfr": "NFRQ-ORG-01", "check": "helper_fan_in", "severity": "info", "waiver": "declared"},
    ],
}


def reg(**change) -> dict:
    doc = copy.deepcopy(BASE)
    doc.update(change)
    return doc


class DocumentedWaiverTest(unittest.TestCase):
    def test_defaults_come_from_nfr_and_documentation_version(self) -> None:
        doc = reg()
        wem.Criterion.validate_documentation(doc)
        self.assertEqual(doc["rules"][0]["rq"], "NFRQ-ORG-01")
        self.assertEqual(doc["rules"][0]["version"], "v0.0.5")

    def test_explicit_rq_and_version_win(self) -> None:
        doc = reg()
        doc["rules"][0].update(rq="FRQ-CON-16.1", version="v0.0.3")
        wem.Criterion.validate_documentation(doc)
        self.assertEqual((doc["rules"][0]["rq"], doc["rules"][0]["version"]), ("FRQ-CON-16.1", "v0.0.3"))

    def test_valid_rq_shapes(self) -> None:
        for rq in ("NFRQ-ORG-01", "FRQ-CON-16.1", "HLRQ-PRC-16", "FRQ-DRV-16.2-BR-3", "NFRQ-SEC-03-BR3"):
            doc = reg()
            doc["rules"][0]["rq"] = rq
            wem.Criterion.validate_documentation(doc)

    def test_invalid_rq_is_refused(self) -> None:
        for rq in ("NFRQ-ORG-01 §3", "NFRQ-ORG-07 c.1", "XX-WFL-001", "nfrq-org-01", "ORG-01", "", None):
            doc = reg()
            doc["rules"][0]["rq"] = rq
            with self.assertRaises(ValueError, msg=repr(rq)):
                wem.Criterion.validate_documentation(doc)

    def test_invalid_version_is_refused(self) -> None:
        for version in ("0.0.5", "v0.0", "v1.2.3.4", "vX.Y.Z", ""):
            doc = reg()
            doc["rules"][0]["version"] = version
            with self.assertRaises(ValueError, msg=repr(version)):
                wem.Criterion.validate_documentation(doc)

    def test_invalid_documentation_version_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            wem.Criterion.validate_documentation(reg(documentation_version="0.0.5"))

    def test_documented_without_any_version_is_refused(self) -> None:
        doc = reg()
        del doc["documentation_version"]
        with self.assertRaises(ValueError):
            wem.Criterion.validate_documentation(doc)

    def test_other_waivers_carry_no_obligation(self) -> None:
        doc = reg()
        del doc["documentation_version"]
        doc["rules"][0]["waiver"] = "forbidden"
        wem.Criterion.validate_documentation(doc)
        self.assertNotIn("rq", doc["rules"][0])

    def test_guarded_optional_ref_follows_the_same_shapes(self) -> None:
        ok = reg(scope={"guarded_optional": [{"module": "a.py", "ref": "NFRQ-SEC-03", "packages": []}]})
        wem.Criterion.validate_documentation(ok)
        self.assertEqual(ok["scope"]["guarded_optional"][0]["version"], "v0.0.5")
        bad = reg(scope={"guarded_optional": [{"module": "a.py", "ref": "NFRQ-SEC-03 §1"}]})
        with self.assertRaises(ValueError):
            wem.Criterion.validate_documentation(bad)

    def test_label_names_requirement_and_version(self) -> None:
        doc = reg()
        wem.Criterion.validate_documentation(doc)
        self.assertEqual(wem.Criterion.waiver_label(doc["rules"][0]), "documented (NFRQ-ORG-01, v0.0.5)")
        self.assertEqual(wem.Criterion.waiver_label(doc["rules"][1]), "declared")

    def test_loader_rejects_a_bad_criterion_and_resolves_a_good_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dictionary.json"
            path.write_text(json.dumps(reg()), encoding="utf-8")
            loaded = wem.Application._load_registry(path)
            self.assertEqual(loaded["rules"][0]["version"], "v0.0.5")
            self.assertEqual(loaded["documentation_version"], "v0.0.5")
            broken = reg()
            broken["rules"][0]["rq"] = "NFRQ-ORG-01 §3"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ValueError):
                wem.Application._load_registry(path)

    def test_shipped_criterion_is_valid(self) -> None:
        # Only this distribution's criterion; blackwattle and core test their own.
        path = Path(__file__).resolve().parents[1] / "dictionary.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc.get("documentation_version"), "v0.0.5")
        wem.Criterion.validate_documentation(doc)


if __name__ == "__main__":
    unittest.main()
