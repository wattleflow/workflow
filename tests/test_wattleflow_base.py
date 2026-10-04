# Module name: tests/test_wattleflow_base.py
# Tests for the Wattleflow root (FRQ-PTN): identity that cannot be changed, audit by contract, the one
# place that splits the constructor keywords, and the structural rules every framework class follows
# (BR-PTN-02 Audit only through the root, BR-PTN-07 declared slots, no repeated slots, root first in
# the bases). Helpers sit below the root and name Audit themselves; they are the stated exemption.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_wattleflow_base -v
import importlib
import inspect
import logging
import pkgutil
import unittest

from wattleflow.concrete.base import Wattleflow
from wattleflow.core import IWattleflow
from wattleflow.helpers.audit import Audit

# Layers whose classes follow the root contract. `wattleflow.helpers` sits below the root (the root
# imports it), so its classes name Audit directly and are not held to these rules.
PACKAGES = ("wattleflow.concrete", "wattleflow.schedulers", "wattleflow.decorators")


def framework_classes():
    found = {}
    for package in PACKAGES:
        root = importlib.import_module(package)
        modules = [root]
        modules += [
            importlib.import_module(info.name)
            for info in pkgutil.walk_packages(root.__path__, package + ".")
        ]
        for module in modules:
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module.__name__ and issubclass(cls, Audit) and cls is not Wattleflow:
                    found[f"{cls.__module__}.{cls.__qualname__}"] = cls
    return found


def declared(cls):
    slots = cls.__dict__.get("__slots__", ())
    return (slots,) if isinstance(slots, str) else tuple(slots)


class Plain(Wattleflow):
    def __init__(self, **kwargs):
        self.seen = dict(kwargs)
        super().__init__(**kwargs)


class IdentityTest(unittest.TestCase):
    def test_the_name_is_the_concrete_type_name(self):
        self.assertEqual(Plain(level=logging.CRITICAL).name, "Plain")

    def test_the_name_cannot_be_changed(self):
        plain = Plain(level=logging.CRITICAL)
        with self.assertRaises(AttributeError):
            plain.name = "forged"

    def test_str_and_repr_follow_the_name(self):
        plain = Plain(level=logging.CRITICAL)
        self.assertEqual((str(plain), repr(plain)), ("Plain", "Plain()"))

    def test_an_instance_cannot_override_str(self):
        plain = Plain(level=logging.CRITICAL)
        plain.__str__ = lambda: "forged"  # a special method is looked up on the type
        self.assertEqual(str(plain), "Plain")


class ContractTest(unittest.TestCase):
    def test_audit_comes_before_the_interface_in_the_mro(self):
        mro = Wattleflow.__mro__
        self.assertLess(mro.index(Audit), mro.index(IWattleflow))

    def test_the_root_adds_no_state(self):
        self.assertEqual(Wattleflow.__slots__, ())

    def test_an_object_is_auditable_without_naming_audit(self):
        plain = Plain(level=logging.DEBUG)
        with self.assertLogs(level=logging.DEBUG):
            plain.debug(msg="x")


class KeywordSplitTest(unittest.TestCase):
    def test_the_logging_keywords_stop_in_audit_and_the_rest_reaches_the_subclass(self):
        plain = Plain(level="ERROR", formatting="%(message)s", propagate=True, x=1)
        self.assertEqual(plain.seen["x"], 1)

    def test_leftover_keywords_do_not_reach_object_init(self):
        Wattleflow(unknown_key=1, level=logging.CRITICAL)

    def test_fmt_is_the_formatting_for_every_framework_object(self):
        class WithFmt(Wattleflow):  # a class of its own: the handler is built once per class
            pass

        self.assertEqual(WithFmt(fmt="%(message)s", level=logging.CRITICAL)._handler.formatter._fmt, "%(message)s")

    def test_the_alias_does_not_override_an_explicit_formatting(self):
        class WithBoth(Wattleflow):
            pass

        board = WithBoth(fmt="%(message)s", formatting="%(levelname)s", level=logging.CRITICAL)
        self.assertEqual(board._handler.formatter._fmt, "%(levelname)s")


class StructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = framework_classes()

    def test_the_survey_found_the_framework(self):
        self.assertGreater(len(self.classes), 30)

    def test_no_class_names_audit_as_a_base(self):
        offenders = [n for n, c in self.classes.items() if Audit in c.__bases__]
        self.assertEqual(offenders, [])

    def test_the_root_comes_before_any_other_framework_interface(self):
        offenders = []
        for name, cls in self.classes.items():
            bases = cls.__bases__
            if Wattleflow not in bases:
                continue
            before = bases[: bases.index(Wattleflow)]
            if any(issubclass(b, IWattleflow) and not issubclass(b, Wattleflow) for b in before):
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_every_class_declares_its_own_slots(self):
        offenders = [n for n, c in self.classes.items() if "__slots__" not in c.__dict__]
        self.assertEqual(offenders, [])

    def test_no_class_repeats_a_slot_of_its_bases(self):
        offenders = {}
        for name, cls in self.classes.items():
            inherited = set()
            for base in cls.__mro__[1:]:
                inherited |= set(declared(base))
            repeated = sorted(set(declared(cls)) & inherited)
            if repeated:
                offenders[name] = repeated
        self.assertEqual(offenders, {})


if __name__ == "__main__":
    unittest.main()
