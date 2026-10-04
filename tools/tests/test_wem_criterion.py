#!/usr/bin/env python3
# Module name: tools/tests/test_wem_criterion.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""wem_criterion — every drift direction, and the prove/apply contract.

The criterion, the registers and the source tree are fixtures, and the lint is a
fake that emits one `foreign-import` per undeclared import: the suite measures the
tool, not the shipped vocabulary (the same rule as test_wem_lint_org02).

Run:  python -m unittest discover tools/tests
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

__TOOL__ = Path(__file__).resolve().parent.parent / "wem_criterion.py"
_spec = importlib.util.spec_from_file_location("wem_criterion", __TOOL__)
wc = importlib.util.module_from_spec(_spec)
sys.modules["wem_criterion"] = wc
_spec.loader.exec_module(wc)

CRITERION = {
    "_criterion_version": ["0.1.0 (2026-01-01) — first cut. First proposal."],
    "distribution": "wattleflow-processors",
    "criterion_version": "0.1.0",
    "domains": ["connections", "pipelines"],
    "shared_namespace": "helpers",
    "scope": {"core_libraries": ["kafka"], "exclude_paths": [], "guarded_optional": {}},
    "identifier_acronyms": ["PDF"],
    "subjects": ["PDF", "Mail"],
    "operations": ["Extract"],
    "targets": [],
    "qualifiers": [],
    "package_subject": {"pdf": "PDF"},
    "grouping_packages": [],
    "exempt_packages": [],
    "rules": [
        {"id": "R1", "nfr": "NFRQ-ORG-02", "check": "prohibited_standalone", "severity": "error"},
        {"id": "R2", "nfr": "NFRQ-ORG-99", "check": "ghost_check", "severity": "warning"},
    ],
}

FAKE_LINT = textwrap.dedent(
    """
    import argparse, ast, json, sys
    from pathlib import Path
    p = argparse.ArgumentParser()
    for flag in ("--src", "--registry", "--snapshot"):
        p.add_argument(flag, type=Path)
    for flag in ("--no-graph", "--no-color", "--quiet"):
        p.add_argument(flag, action="store_true")
    a = p.parse_args()
    reg = json.loads(a.registry.read_text())
    allowed = set(reg["scope"]["core_libraries"]) | set(sys.stdlib_module_names)
    allowed |= {"wattleflow", "__future__"}
    findings = []
    for f in sorted(a.src.rglob("*.py")):
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed:
                        rel = str(f.relative_to(a.src))
                        found = {"kind": "foreign-import", "location": rel + ":0", "name": rel}
                        findings.append(dict(found, message="imports " + root))
    triple = {"criterion": str(a.registry)}
    a.snapshot.write_text(json.dumps({"reproducibility_triple": triple, "findings": findings}))
    """
)


class Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.criterion = root / "tools" / "dictionary.json"
        self.criterion.parent.mkdir(parents=True)
        self.criterion.write_text(wc.Criterion.dump(CRITERION), encoding="utf-8")
        self.lint = root / "tools" / "fake_lint.py"
        self.lint.write_text(FAKE_LINT, encoding="utf-8")

        self.src = root / "src" / "wattleflow"
        self.write(
            "connections/sdr.py",
            "import os\nimport kafka\nimport rtlsdr\n\nclass SDRConnection:\n    pass\n",
        )
        self.write("pipelines/pdf/extract.py", "class PipelinePDFExtract:\n    pass\n")
        self.write("pipelines/mail/extract.py", "class PipelineMessageBody:\n    pass\n")
        self.write("metrics/counter.py", "class Counter:\n    pass\n")

        self.docs = root / "documentation"
        self.doc(
            "03-NFRQ/NFRQ-ORG-02-names-EN.md",
            "| **Criterion** | `tools/dictionary.json` — `domains`, `acronyms`, `ghost_key` |\n"
            "Guarded list: (`tools/dictionary.json → audit.import_guard`).\n"
            "`ghost_before` feeds `tools/dictionary.json` — `domains`.\n",
        )

    def write(self, relative: str, text: str) -> None:
        path = self.src / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def doc(self, relative: str, text: str) -> None:
        path = self.docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def drift(self) -> dict[str, set[str]]:
        criterion = wc.Criterion(self.criterion)
        findings = wc.Drift(criterion, wc.Code(self.src), wc.Registers(self.docs)).findings()
        kinds: dict[str, set[str]] = {}
        for f in findings:
            kinds.setdefault(f.kind, set()).add(f.subject)
        return kinds

    def patch(self, data: dict) -> wc.Patch:
        return wc.Patch(data)


class DriftTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name))
        self.kinds = self.fx.drift()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_registers_to_criterion(self) -> None:
        self.assertEqual(
            self.kinds["cited-key-missing"], {"acronyms", "ghost_key", "audit.import_guard"}
        )

    def test_alias_is_a_register_correction(self) -> None:
        criterion = wc.Criterion(self.fx.criterion)
        found = wc.Drift(
            criterion, wc.Code(self.fx.src), wc.Registers(self.fx.docs)
        ).registers_to_criterion()
        by_subject = {f.subject: f for f in found}
        self.assertEqual(by_subject["acronyms"].authority, "registers")
        self.assertEqual(by_subject["ghost_key"].authority, "documentation")

    def test_criterion_to_registers(self) -> None:
        self.assertEqual(self.kinds["rule-nfr-unregistered"], {"R2 → NFRQ-ORG-99"})
        self.assertNotIn("change-authority", self.kinds)

    def test_code_to_criterion(self) -> None:
        self.assertEqual(self.kinds["undeclared-library"], {"rtlsdr"})
        self.assertEqual(self.kinds["unregistered-acronym"], {"SDR"})
        self.assertEqual(self.kinds["undeclared-package"], {"metrics"})
        self.assertEqual(self.kinds["unmapped-pipeline-package"], {"mail"})

    def test_foundation_package_is_declared(self) -> None:
        doc = json.loads(self.fx.criterion.read_text())
        doc["foundation_packages"] = ["metrics"]
        self.fx.criterion.write_text(wc.Criterion.dump(doc))
        self.assertNotIn("undeclared-package", self.fx.drift())

    def test_criterion_to_code(self) -> None:
        self.assertEqual(self.kinds["facet-unused"], {"subjects: Mail"})

    def test_clean_core_never_allows_a_library(self) -> None:
        doc = json.loads(self.fx.criterion.read_text())
        doc["distribution"] = "wattleflow-workflow"
        self.fx.criterion.write_text(wc.Criterion.dump(doc))
        criterion = wc.Criterion(self.fx.criterion)
        found = [
            f
            for f in wc.Drift(criterion, wc.Code(self.fx.src), None).code_to_criterion()
            if f.kind == "undeclared-library"
        ]
        self.assertEqual([f.authority for f in found], ["documentation"])
        self.assertIsNone(wc.propose(found))


class PatchTest(unittest.TestCase):
    def test_ops(self) -> None:
        doc = {"scope": {"core_libraries": ["kafka"]}, "criterion_version": "0.1.0"}
        patch = wc.Patch(
            {
                "ops": [
                    {"op": "add", "path": "scope.core_libraries", "value": "rtlsdr"},
                    {"op": "remove", "path": "scope.core_libraries", "value": "kafka"},
                    {"op": "set", "path": "scope.note", "value": "x"},
                ]
            }
        )
        self.assertEqual(
            patch.apply_to(doc),
            {"scope": {"core_libraries": ["rtlsdr"], "note": "x"}, "criterion_version": "0.1.0"},
        )
        self.assertEqual(doc["scope"]["core_libraries"], ["kafka"], "the original is never mutated")

    def test_invalid_ops_refused(self) -> None:
        with self.assertRaises(ValueError):
            wc.Patch({"ops": []})
        with self.assertRaises(ValueError):
            wc.Patch({"ops": [{"op": "add", "path": "domains", "value": "a"}]}).apply_to(
                {"domains": ["a"]}
            )

    def test_bump_minor(self) -> None:
        self.assertEqual(wc.bump_minor("0.9.0"), "0.10.0")


class ProveApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name))
        self.lint = wc.Lint(self.fx.lint, self.fx.src)
        self.good = wc.Patch(
            {
                "reason": "scope.core_libraries gains rtlsdr.",
                "ops": [{"op": "add", "path": "scope.core_libraries", "value": "rtlsdr"}],
                "expect": [{"kind": "foreign-import", "match": "connections/sdr.py"}],
            }
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_prove_passes_when_the_target_disappears(self) -> None:
        proof = wc.prove(wc.Criterion(self.fx.criterion), self.good, self.lint)
        self.assertTrue(proof["passed"], proof)
        self.assertEqual(len(proof["removed"]), 1)
        self.assertEqual(proof["added"], [])

    def test_prove_fails_when_a_finding_is_added(self) -> None:
        bad = wc.Patch(
            {"ops": [{"op": "remove", "path": "scope.core_libraries", "value": "kafka"}]}
        )
        proof = wc.prove(wc.Criterion(self.fx.criterion), bad, self.lint)
        self.assertFalse(proof["passed"])
        self.assertEqual(len(proof["added"]), 1)

    def test_prove_fails_when_the_expected_finding_stays(self) -> None:
        wrong = wc.Patch(
            {
                "ops": [{"op": "add", "path": "scope.core_libraries", "value": "numpy"}],
                "expect": [{"kind": "foreign-import", "match": "connections/sdr.py"}],
            }
        )
        self.assertFalse(wc.prove(wc.Criterion(self.fx.criterion), wrong, self.lint)["passed"])

    def test_apply_needs_authority(self) -> None:
        with self.assertRaises(PermissionError):
            wc.apply(wc.Criterion(self.fx.criterion), self.good, self.lint, "", None, "2026-09-12")
        self.assertEqual(wc.Criterion(self.fx.criterion).version, "0.1.0", "nothing written")

    def test_apply_writes_version_changelog_and_record(self) -> None:
        records = self.fx.root / "07-CHANGES"
        record = wc.apply(
            wc.Criterion(self.fx.criterion),
            self.good,
            self.lint,
            "documentation, 2026-09-12",
            records,
            "2026-09-12",
        )
        after = wc.Criterion(self.fx.criterion)
        self.assertEqual(after.version, "0.2.0")
        self.assertIn("rtlsdr", after.get("scope")["core_libraries"])
        self.assertTrue(after.get("_criterion_version")[0].startswith("0.2.0 (2026-09-12)"))
        self.assertIn("Authority: documentation, 2026-09-12", " ".join(after.get("_criterion_version")))
        self.assertEqual(wc.Criterion.dump(after.doc), after.raw, "canonical form kept")
        self.assertTrue(Path(record["path"]).is_file())

    def test_propose_matches_what_prove_accepts(self) -> None:
        criterion = wc.Criterion(self.fx.criterion)
        findings = wc.Drift(criterion, wc.Code(self.fx.src), None).code_to_criterion()
        proposed = wc.Patch(wc.propose(findings))
        self.assertTrue(wc.prove(criterion, proposed, self.lint)["passed"])


class RegisterLayoutTest(unittest.TestCase):
    """The registers are read under `requirements/`, and at the root where they still are."""

    NFR = "| **Criterion** | `tools/dictionary.json` |\n"

    def registers(self, prefix: str) -> wc.Registers:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for relative, text in (
            (f"{prefix}03-NFRQ/NFRQ-ORG-02-names-EN.md", self.NFR),
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return wc.Registers(root)

    def test_registers_under_requirements(self) -> None:
        registers = self.registers("requirements/")
        self.assertEqual(registers.nfr_ids(), {"NFRQ-ORG-02"})
        self.assertEqual(len(list(registers.files())), 1)

    def test_registers_at_the_documentation_root(self) -> None:
        registers = self.registers("")
        self.assertEqual(registers.nfr_ids(), {"NFRQ-ORG-02"})


if __name__ == "__main__":
    unittest.main()
