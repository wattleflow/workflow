# Module name: tests/test_preset.py
# Tests for decorators/preset.py — NFRQ-ORG-07 (see documentation/requirements/03-NFRQ/
# NFRQ-ORG-07-preset-allowed-declaration.md). Criteria 3–5 and the decorator's contract.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest discover -s tests -t . -v
import unittest

from wattleflow.decorators.preset import PresetDecorator, PresetGate


class Parent:
    """Minimal preset owner: records warnings so a test can see what was reported."""

    ALLOWED = ["a", "b"]

    def __init__(self, **kwargs):
        self.warnings: list[dict] = []
        self.name = "Parent"
        self.preset = PresetDecorator(self, **kwargs)

    def warning(self, **kwargs) -> None:
        self.warnings.append(kwargs)


class Child(Parent):
    ALLOWED = ["c"]


class Inheriting(Parent):
    pass


class Undeclared:
    pass


class PresetGateResolveTest(unittest.TestCase):
    """Criteria 3 and 4: the declaration is a list of str, unioned across the MRO."""

    def test_declared_keys_are_resolved(self):
        self.assertEqual(PresetGate.resolve(Parent), {"a", "b"})

    def test_declarations_are_unioned_across_the_mro(self):
        self.assertEqual(PresetGate.resolve(Child), {"a", "b", "c"})

    def test_subclass_without_own_declaration_inherits_the_base(self):
        self.assertEqual(PresetGate.resolve(Inheriting), {"a", "b"})

    def test_class_without_any_declaration_permits_nothing(self):
        self.assertEqual(PresetGate.resolve(Undeclared), set())

    def test_declaration_that_is_not_a_list_of_str_is_rejected(self):
        bad = {
            "string": "abc",
            "tuple": ("a",),
            "set": {"a"},
            "dict": {"a": 1},
            "list holding int": ["a", 1],
        }
        for label, value in bad.items():
            with self.subTest(label):
                klass = type("Bad", (Parent,), {"ALLOWED": value})
                with self.assertRaisesRegex(TypeError, r"Bad\.ALLOWED must be a list of str"):
                    PresetGate.resolve(klass)

    def test_a_string_is_never_read_as_its_characters(self):
        klass = type("Letters", (Undeclared,), {"ALLOWED": "abc"})
        with self.assertRaises(TypeError):
            PresetGate.resolve(klass)

    def test_invalid_declaration_in_a_base_is_rejected_for_the_subclass(self):
        base = type("BadBase", (Undeclared,), {"ALLOWED": "abc"})
        sub = type("GoodSub", (base,), {"ALLOWED": ["x"]})
        with self.assertRaisesRegex(TypeError, r"BadBase\.ALLOWED"):
            PresetGate.resolve(sub)

    def test_framework_keys_are_a_closed_set(self):
        self.assertEqual(
            PresetGate.FRAMEWORK,
            frozenset({"allowed", "formatting", "handler", "level", "name"}),
        )


class PresetDecoratorTest(unittest.TestCase):
    """The decorator exposes exactly the declared keys."""

    def test_declared_key_is_readable(self):
        self.assertEqual(Parent(a=1).preset.a, 1)

    def test_declared_key_that_was_not_passed_reads_as_none(self):
        self.assertIsNone(Parent(a=1).preset.b)

    def test_inherited_key_is_readable_on_a_subclass(self):
        owner = Child(a=1, c=3)
        self.assertEqual((owner.preset.a, owner.preset.c), (1, 3))

    def test_undeclared_key_is_not_stored(self):
        owner = Parent(a=1, zzz=9)
        self.assertEqual(owner.preset._values, {"a": 1})

    def test_undeclared_attribute_is_not_permitted(self):
        with self.assertRaisesRegex(AttributeError, "is not permitted"):
            Parent(a=1).preset.zzz

    def test_declared_key_can_be_set_and_an_undeclared_one_cannot(self):
        preset = Parent(a=1).preset
        preset.b = 2
        self.assertEqual(preset.b, 2)
        with self.assertRaisesRegex(AttributeError, "is not permitted"):
            preset.zzz = 3

    def test_attribute_of_the_owner_wins_over_the_preset(self):
        self.assertEqual(Parent(name="ignored").preset.name, "Parent")

    def test_framework_keys_are_never_reported_as_undeclared(self):
        owner = Parent(a=1, level=10, handler=None, formatting="x", name="n", allowed=["a"])
        self.assertEqual(owner.warnings, [])


if __name__ == "__main__":
    unittest.main()
