#!/usr/bin/env python3
# Module name: tools/tests/test_wem_lint_org02.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""K14 (`NFRQ-ORG-02` §1–§5) — the pipeline name grammar, and nothing else.

Scope is deliberately narrow. The rule `NomenclatureRule` implements two
criteria groups with different reach; this suite covers only the grammar half,
the one K14 names:

    K14  pipeline-grammar   criteria 1, 2, 3, 5   ERROR / WARNING
    K16  acronym-case       criterion 4           WARNING while the casing decision is open
    K13  standalone-role-noun  criterion 6        out of scope — asserted to be excluded

The criterion is a FIXTURE, not the distribution's `dictionary.json`. A test that
read the shipped vocabulary would change verdict whenever a documented change extends it, which
would measure the vocabulary instead of the rule. The fixture below is therefore
the criterion half of the reproducibility triple (D-10) and is stated in full.

Run:  PYTHONPATH=<processors>/src:<workflow>/src python -m unittest discover tools/tests
      (or: python tools/tests/test_wem_lint_org02.py)
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

__TOOL__ = Path(__file__).resolve().parent.parent / "wem_lint.py"


def _load_tool():
    """Import `wem_lint` from its path — it is a script beside the criterion,
    not an installed package, and it bootstraps its own `sys.path`."""
    spec = importlib.util.spec_from_file_location("wem_lint", __TOOL__)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wem_lint"] = module
    spec.loader.exec_module(module)
    return module


wem = _load_tool()
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Criterion fixture                                                    #
# --------------------------------------------------------------------------- #
# Minimal closed vocabulary: two subjects that are ordinary words, one that is an
# acronym (to reach criterion 4), one converter target, one synonym pair, one
# qualifier. Severities are declared here because they are a registry fact, not a
# constant of the tool (POLICY §9).
CRITERION: dict = {
    "criterion_version": "org02-test-fixture-1",
    "dictionary_version": "org02-test-fixture-1",
    "domains": ["pipelines", "drivers"],
    "pipeline_package": "pipelines",
    "shared_namespace": "helpers",
    "scope": {"core_libraries": [], "exclude_paths": [], "guarded_optional": []},
    "bases": {"pipeline": ["GenericPipeline"]},
    "subjects": ["Mail", "Markdown", "PDF"],
    "operations": ["Write", "Extract"],
    "targets": ["Word"],
    "qualifiers": ["Attachments"],
    "synonyms": {"Save": "Write"},
    "identifier_acronyms": ["PDF"],
    "package_subject": {"mail": "Mail", "convertors": "Markdown", "pdf": "PDF"},
    "grouping_packages": [],
    "exempt_packages": [],
    "package_aliases": {},
    "prohibited_standalone": ["Helper"],
    "acronym_identifier_casing": {
        "status": "undecided",
        "decision_pending": "acronym casing (PDF vs Pdf)",
    },
    "rules": [
        {"check": "base_family_membership", "severity": "error"},
        {"check": "prohibited_standalone", "severity": "error"},
        {"check": "acronym_case", "severity": "warning"},
    ],
}

K14 = "pipeline-grammar"
K16 = "acronym-case"
K13 = "standalone-role-noun"

# The criterion number is part of the finding, not decoration: it is what binds a
# report line back to the registry entry. Criterion 4 is the exception — while
# the casing decision is open the message states the waiver instead of the number, so
# the kind carries the attribution.
_CRITERION_TAG = re.compile(r"criterion (\d)")
_KIND_CRITERION = {K16: 4, K13: 6}
# --------------------------------------------------------------------------- #
# endregion Criterion fixture                                                 #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Source fixtures                                                      #
# --------------------------------------------------------------------------- #
# Modules carry no imports on purpose: `WemLint` drops any file that imports
# outside the declared tier, and an excluded file is measured by nothing at all.
# `GenericPipeline` is never defined — the family is read from base NAMES in the
# AST, so a declared root needs no module.

CLEAN: dict[str, str] = {
    # Subject + Operation, subject equals the package subject.
    "pipelines/mail/write.py": "class PipelineMailWrite(GenericPipeline):\n    pass\n",
    # Subject + Operation + registered Qualifier.
    "pipelines/mail/attachments.py": (
        "class PipelineMailExtractAttachments(GenericPipeline):\n    pass\n"
    ),
    # Subject + To<Target> — the converter form of criterion 1.
    "pipelines/convertors/word.py": "class PipelineMarkdownToWord(GenericPipeline):\n    pass\n",
    # Not a pipeline and not prefixed: criterion 2 has nothing to say about it.
    "pipelines/mail/reader.py": "class MailReader:\n    pass\n",
    # A nested class is not a top-level declaration; the grammar does not reach it,
    # so `Bogus` must not be read as a trailing qualifier of the class holding it.
    "pipelines/mail/nested.py": (
        "class PipelineMailExtract(GenericPipeline):\n    class Bogus:\n        pass\n"
    ),
}

# One violation per module, so a failure names the criterion that broke.
VIOLATIONS: dict[str, str] = {
    # 1 — no registered Subject at the front.
    "pipelines/mail/c1_subject.py": "class PipelineFooWrite(GenericPipeline):\n    pass\n",
    # 1 — Subject present, Operation missing.
    "pipelines/mail/c1_operation.py": "class PipelineMail(GenericPipeline):\n    pass\n",
    # 2 — `Pipeline` prefix on a class outside the pipeline family.
    "pipelines/mail/c2_prefix.py": "class PipelineMailWriter:\n    pass\n",
    # 2 — pipeline family member without the prefix.
    "pipelines/mail/c2_missing.py": "class MailWrite(GenericPipeline):\n    pass\n",
    # 3 — Operation is a registered synonym of the canonical verb.
    "pipelines/mail/c3_synonym.py": "class PipelineMailSave(GenericPipeline):\n    pass\n",
    # 3 — Operation outside the closed verb vocabulary.
    "pipelines/mail/c3_verb.py": "class PipelineMailBlah(GenericPipeline):\n    pass\n",
    # 3 — converter Target outside the registered targets.
    "pipelines/convertors/c3_target.py": (
        "class PipelineMarkdownToXml(GenericPipeline):\n    pass\n"
    ),
    # 3 — trailing token that is neither Qualifier nor acronym (WARNING, not ERROR).
    "pipelines/mail/c3_qualifier.py": (
        "class PipelineMailWriteBogus(GenericPipeline):\n    pass\n"
    ),
    # 4 — acronym casing; surfaces as K16, and only as a WARNING while the decision is open.
    "pipelines/pdf/c4_casing.py": "class PipelinePdfWrite(GenericPipeline):\n    pass\n",
    # 5 — Subject does not match the subject of the package holding the class.
    "pipelines/pdf/c5_package.py": "class PipelineMailWrite(GenericPipeline):\n    pass\n",
    # 6 — standalone role noun: emitted by the same rule, but it is K13, not K14.
    "pipelines/mail/c6_standalone.py": "class Helper:\n    pass\n",
}
# --------------------------------------------------------------------------- #
# endregion Source fixtures                                                   #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Harness                                                              #
# --------------------------------------------------------------------------- #


class Org02Harness(unittest.TestCase):
    """Materialises a tree and runs ONLY the ORG-02 rule over it."""

    @staticmethod
    def _findings(modules: dict[str, str]) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "wattleflow"
            for rel, body in modules.items():
                target = src / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")

            criterion = root / "dictionary.json"
            criterion.write_text(json.dumps(CRITERION), encoding="utf-8")

            # Loaded through the tool's own reader, so the test also exercises the
            # derived keys (`acronyms`, `acronym_pending`) rather than faking them.
            reg = wem.Application._load_registry(criterion)
            lint = wem.WemLint(src, reg, home=root)
            return lint.run([wem.RuleFactory.create(nfr="ORG-02")])

    @classmethod
    def facts(cls, modules: dict[str, str]) -> set[tuple]:
        """`(class, kind, severity, criterion)` per finding — the identity a report
        line carries, without its prose (presentation is versioned apart, D-13)."""
        out = set()
        for finding in cls._findings(modules):
            match = _CRITERION_TAG.search(finding.message)
            criterion = (
                int(match.group(1)) if match else _KIND_CRITERION.get(finding.kind)
            )
            out.add(
                (
                    finding.name,
                    finding.kind,
                    wem.logging.getLevelName(finding.severity),
                    criterion,
                )
            )
        return out

    @classmethod
    def k14(cls, modules: dict[str, str]) -> set[tuple]:
        return {f for f in cls.facts(modules) if f[1] == K14}

    @classmethod
    def messages(cls, modules: dict[str, str]) -> dict[str, str]:
        """Raw message per class. Used only where the wording carries SUBSTANCE the
        four-tuple cannot hold — a synonym and an unknown verb are both criterion 3
        at ERROR, and only the message says which one was found."""
        return {f.name: f.message for f in cls._findings(modules)}


# --------------------------------------------------------------------------- #
# endregion Harness                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Tests                                                                #
# --------------------------------------------------------------------------- #


class TestPipelinePackageFromCriterion(Org02Harness):
    """v1.19.0: the grammar reaches the package the criterion names, and no other."""

    MODULES = {
        "pipelines/mail/c1_subject.py": "class PipelineFooWrite(GenericPipeline):\n    pass\n",
        "pipelines/mail/c6_standalone.py": "class Helper:\n    pass\n",
    }

    def test_named_package_gets_the_grammar(self) -> None:
        self.assertIn(K14, {f[1] for f in self.facts(self.MODULES)})

    def test_without_the_key_only_criterion_6_applies(self) -> None:
        with mock.patch.dict(CRITERION):
            del CRITERION["pipeline_package"]
            facts = self.facts(self.MODULES)
        self.assertNotIn(K14, {f[1] for f in facts})
        self.assertIn("Helper", {f[0] for f in facts})


class TestK14Binding(Org02Harness):
    """The tool/registry binding K14 depends on. If this breaks, every other
    assertion below is measuring the wrong check."""

    def test_check_emits_only_the_grammar_kind(self):
        self.assertEqual(
            wem.Criterion.IMPLEMENTED["base_family_membership"],
            (K14,),
            "K14 is declared for `base_family_membership`; the tool emits another kind",
        )

    def test_grammar_severity_comes_from_the_registry(self):
        self.assertEqual(
            wem.Criterion.severity(CRITERION, "base_family_membership"),
            wem.ERROR,
            "criterion severity must be read from `rules`, not hard-coded",
        )

    def test_acronym_case_cannot_exceed_warning_while_the_dr_is_open(self):
        # METHODOLOGY §9: enforcing one side of an undecided question is forbidden.
        self.assertEqual(wem.Criterion.acronym_severity(CRITERION), wem.WARNING)


class TestValidNames(Org02Harness):
    """Correct examples — the grammar must stay silent on all of them."""

    def test_clean_tree_reports_nothing(self):
        self.assertEqual(
            self.facts(CLEAN), set(), "a conforming tree must produce no finding"
        )

    def test_each_valid_form_individually(self):
        for rel, body in CLEAN.items():
            with self.subTest(module=rel):
                self.assertEqual(self.k14({rel: body}), set())


class TestCriterion1(Org02Harness):
    """`Pipeline<Subject>(<Operation>|To<Target>)` — the shape itself."""

    def test_unregistered_subject(self):
        self.assertEqual(
            self.k14(
                {
                    "pipelines/mail/c1_subject.py": VIOLATIONS[
                        "pipelines/mail/c1_subject.py"
                    ]
                }
            ),
            {("PipelineFooWrite", K14, "ERROR", 1)},
        )

    def test_missing_operation(self):
        self.assertEqual(
            self.k14(
                {
                    "pipelines/mail/c1_operation.py": VIOLATIONS[
                        "pipelines/mail/c1_operation.py"
                    ]
                }
            ),
            {("PipelineMail", K14, "ERROR", 1)},
        )

    def test_subject_only_reports_once(self):
        # The rule returns after an unknown Subject: without the Subject the
        # remaining facets cannot be located, so further findings would be noise.
        facts = self.k14(
            {"pipelines/mail/x.py": "class PipelineFooBlah(GenericPipeline):\n p=1\n"}
        )
        self.assertEqual(len(facts), 1)


class TestCriterion2(Org02Harness):
    """The prefix marks the contract — in both directions."""

    def test_prefix_on_a_non_pipeline(self):
        self.assertEqual(
            self.k14(
                {
                    "pipelines/mail/c2_prefix.py": VIOLATIONS[
                        "pipelines/mail/c2_prefix.py"
                    ]
                }
            ),
            {("PipelineMailWriter", K14, "ERROR", 2)},
        )

    def test_pipeline_without_the_prefix(self):
        self.assertEqual(
            self.k14(
                {
                    "pipelines/mail/c2_missing.py": VIOLATIONS[
                        "pipelines/mail/c2_missing.py"
                    ]
                }
            ),
            {("MailWrite", K14, "ERROR", 2)},
        )

    def test_family_membership_is_transitive(self):
        # An intermediate base is a fact of the code, not a registry entry: a class
        # inheriting it is still a pipeline and still needs the prefix (v1.17.0).
        tree = {
            "pipelines/mail/base.py": "class PipelineMailBase(GenericPipeline):\n    pass\n",
            "pipelines/mail/leaf.py": "class MailWriteLeaf(PipelineMailBase):\n    pass\n",
        }
        self.assertIn(("MailWriteLeaf", K14, "ERROR", 2), self.k14(tree))


class TestCriterion3(Org02Harness):
    """Every facet token comes from its registered vocabulary."""

    def test_synonym_of_a_canonical_verb(self):
        module = {
            "pipelines/mail/c3_synonym.py": VIOLATIONS["pipelines/mail/c3_synonym.py"]
        }
        self.assertEqual(self.k14(module), {("PipelineMailSave", K14, "ERROR", 3)})
        # A synonym and an unknown verb are indistinguishable by severity and
        # criterion alone; what separates them is that the synonym finding can
        # name the canonical verb, and an author cannot act on it if it does not.
        self.assertIn("Write", self.messages(module)["PipelineMailSave"])

    def test_verb_outside_the_vocabulary(self):
        module = {"pipelines/mail/c3_verb.py": VIOLATIONS["pipelines/mail/c3_verb.py"]}
        self.assertEqual(self.k14(module), {("PipelineMailBlah", K14, "ERROR", 3)})
        # The counterpart: an unregistered verb has no canonical form to offer, so
        # it must NOT be reported as a synonym of one.
        self.assertNotIn("synonym", self.messages(module)["PipelineMailBlah"])

    def test_unknown_converter_target(self):
        key = "pipelines/convertors/c3_target.py"
        self.assertEqual(
            self.k14({key: VIOLATIONS[key]}),
            {("PipelineMarkdownToXml", K14, "ERROR", 3)},
        )

    def test_unregistered_qualifier_is_a_warning(self):
        # An unregistered qualifier is a question for the registry, not a broken
        # build: the name may be legitimate and awaiting a documented decision.
        key = "pipelines/mail/c3_qualifier.py"
        self.assertEqual(
            self.k14({key: VIOLATIONS[key]}),
            {("PipelineMailWriteBogus", K14, "WARNING", 3)},
        )


class TestCriterion4(Org02Harness):
    """Acronym casing — reported, but as K16 and never as K14."""

    def test_casing_surfaces_as_k16_not_k14(self):
        key = "pipelines/pdf/c4_casing.py"
        self.assertEqual(
            self.k14({key: VIOLATIONS[key]}), set(), "criterion 4 is not K14"
        )
        self.assertEqual(
            self.facts({key: VIOLATIONS[key]}),
            {("PipelinePdfWrite", K16, "WARNING", 4)},
        )

    def test_correct_casing_is_silent(self):
        self.assertEqual(
            self.facts(
                {
                    "pipelines/pdf/ok.py": "class PipelinePDFWrite(GenericPipeline):\n p=1\n"
                }
            ),
            set(),
        )


class TestCriterion5(Org02Harness):
    """The Subject facet equals the canonical subject of its package."""

    def test_subject_does_not_match_its_package(self):
        key = "pipelines/pdf/c5_package.py"
        self.assertEqual(
            self.k14({key: VIOLATIONS[key]}),
            {("PipelineMailWrite", K14, "ERROR", 5)},
        )

    def test_same_class_is_clean_in_its_own_package(self):
        # Identical name, different package — criterion 5 is about the pair.
        self.assertEqual(
            self.k14({"pipelines/mail/write.py": CLEAN["pipelines/mail/write.py"]}),
            set(),
        )


class TestScopeIsK14Only(Org02Harness):
    """The suite must measure K14 and nothing else."""

    def test_standalone_role_noun_is_excluded(self):
        key = "pipelines/mail/c6_standalone.py"
        self.assertEqual(
            self.k14({key: VIOLATIONS[key]}), set(), "criterion 6 is K13, not K14"
        )
        self.assertEqual(
            self.facts({key: VIOLATIONS[key]}), {("Helper", K13, "ERROR", 6)}
        )

    def test_every_expected_violation_is_present_together(self):
        # The whole violating tree at once: each criterion contributes exactly the
        # findings its own test asserts, and nothing extra appears from interaction.
        self.assertEqual(
            self.k14(VIOLATIONS),
            {
                ("PipelineFooWrite", K14, "ERROR", 1),
                ("PipelineMail", K14, "ERROR", 1),
                ("PipelineMailWriter", K14, "ERROR", 2),
                ("MailWrite", K14, "ERROR", 2),
                ("PipelineMailSave", K14, "ERROR", 3),
                ("PipelineMailBlah", K14, "ERROR", 3),
                ("PipelineMarkdownToXml", K14, "ERROR", 3),
                ("PipelineMailWriteBogus", K14, "WARNING", 3),
                ("PipelineMailWrite", K14, "ERROR", 5),
            },
        )


# --------------------------------------------------------------------------- #
# endregion Tests                                                             #
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    unittest.main(verbosity=2)
