# Module name: tests/test_attribute_helpers.py
# Tests for Attribute and NameHelper (FRQ-HLP, DEF-HLP-02 … DEF-HLP-07): what each method
# promises, written before the corrections.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_attribute_helpers -v
import contextlib
import io
import unittest

from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import AttributeException
from wattleflow.concrete.helpers import Attribute, NameHelper


class Loadable:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class Foreign:
    pass


class LoadableWattle(Wattleflow):
    pass


class Owner(Wattleflow):
    pass


class Plain:
    pass


MODULE = __name__
LOADABLE = f"{MODULE}.Loadable"
FOREIGN = f"{MODULE}.Foreign"
WATTLE = f"{MODULE}.LoadableWattle"
MISSING = "no_such_module.Nothing"


# --------------------------------------------------------------------------- #
# mandatory
# --------------------------------------------------------------------------- #
class MandatoryTest(unittest.TestCase):
    def setUp(self):
        self.caller = Plain()

    def test_an_instance_is_stored_on_the_caller(self):
        instance = LoadableWattle()
        self.assertTrue(Attribute.mandatory(self.caller, "s", LoadableWattle, s=instance))
        self.assertIs(self.caller.s, instance)

    def test_a_class_path_is_loaded_and_stored_on_the_caller(self):
        self.assertTrue(Attribute.mandatory(self.caller, "s", LoadableWattle, s=WATTLE))
        self.assertIsInstance(self.caller.s, LoadableWattle)

    def test_a_class_of_the_wrong_type_names_the_caller(self):
        with self.assertRaises(AttributeException) as caught:
            Attribute.mandatory(self.caller, "s", LoadableWattle, s=FOREIGN)
        self.assertIs(caught.exception.caller, self.caller)

    def test_a_missing_module_names_the_caller_and_keeps_its_cause(self):
        with self.assertRaises(AttributeException) as caught:
            Attribute.mandatory(self.caller, "s", LoadableWattle, s=MISSING)
        self.assertIs(caught.exception.caller, self.caller)
        self.assertIsInstance(caught.exception.__cause__, ModuleNotFoundError)

    def test_the_loading_message_formats_the_name(self):
        with self.assertRaises(AttributeException) as caught:
            Attribute.mandatory(self.caller, "s", LoadableWattle, s=MISSING)
        message = str(caught.exception)
        self.assertIn("kwargs['s']", message)
        self.assertNotIn("!r", message)

    def test_an_absent_name_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.mandatory(self.caller, "s", LoadableWattle)

    def test_a_wrong_plain_type_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.mandatory(self.caller, "s", int, s="text")


# --------------------------------------------------------------------------- #
# get
# --------------------------------------------------------------------------- #
class GetTest(unittest.TestCase):
    def setUp(self):
        self.caller = Plain()

    def test_a_value_of_the_right_type_is_returned_and_consumed(self):
        kwargs = {"k": 5}
        self.assertEqual(Attribute.get(self.caller, "k", kwargs, int), 5)
        self.assertNotIn("k", kwargs)

    def test_without_a_type_any_object_is_returned(self):
        thing = Plain()
        self.assertIs(Attribute.get(self.caller, "k", {"k": thing}, None), thing)

    def test_without_a_type_a_mandatory_none_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": None}, None)

    def test_a_class_path_is_loaded_and_stored_on_the_caller(self):
        instance = Attribute.get(self.caller, "k", {"k": LOADABLE}, Loadable)
        self.assertIsInstance(instance, Loadable)
        self.assertIs(self.caller.k, instance)

    def test_a_loaded_instance_of_the_wrong_type_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": FOREIGN}, Loadable)

    def test_a_mandatory_value_of_the_wrong_type_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": 5}, Loadable)

    def test_an_absent_mandatory_name_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"other": 1}, int)

    def test_an_absent_optional_name_is_none(self):
        self.assertIsNone(Attribute.get(self.caller, "k", {"other": 1}, int, mandatory=False))

    def test_an_optional_value_of_the_right_type_is_returned(self):
        self.assertEqual(Attribute.get(self.caller, "k", {"k": 5}, int, mandatory=False), 5)

    def test_an_optional_value_of_the_wrong_type_is_not_dropped_silently(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": 5}, Loadable, mandatory=False)

    def test_an_optional_class_path_is_loaded(self):
        instance = Attribute.get(self.caller, "k", {"k": LOADABLE}, Loadable, mandatory=False)
        self.assertIsInstance(instance, Loadable)

    def test_an_optional_class_path_of_the_wrong_type_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": FOREIGN}, Loadable, mandatory=False)


# --------------------------------------------------------------------------- #
# optional
# --------------------------------------------------------------------------- #
class OptionalTest(unittest.TestCase):
    def setUp(self):
        self.caller = Plain()

    def test_a_value_of_the_right_type_is_stored(self):
        Attribute.optional(self.caller, "s", str, None, s="x")
        self.assertEqual(self.caller.s, "x")

    def test_an_absent_name_without_a_default_stores_nothing(self):
        Attribute.optional(self.caller, "s", str, None, other=1)
        self.assertFalse(hasattr(self.caller, "s"))

    def test_an_absent_name_with_a_default_stores_the_default(self):
        Attribute.optional(self.caller, "s", str, "d", other=1)
        self.assertEqual(self.caller.s, "d")

    def test_an_explicit_none_is_treated_as_absent(self):
        Attribute.optional(self.caller, "s", str, None, s=None)
        self.assertFalse(hasattr(self.caller, "s"))

    def test_an_explicit_none_falls_back_to_the_default(self):
        Attribute.optional(self.caller, "s", str, "d", s=None)
        self.assertEqual(self.caller.s, "d")

    def test_a_class_path_is_loaded(self):
        Attribute.optional(self.caller, "s", Loadable, None, s=LOADABLE)
        self.assertIsInstance(self.caller.s, Loadable)

    def test_it_returns_what_it_stored(self):
        caller = Plain()
        self.assertEqual(Attribute.optional(caller, "s", str, "d"), "d")

    def test_a_falsy_default_is_applied(self):
        caller = Plain()
        Attribute.optional(caller, "n", int, 0)
        self.assertEqual(caller.n, 0)


# --------------------------------------------------------------------------- #
# exists
# --------------------------------------------------------------------------- #
class ExistsTest(unittest.TestCase):
    def setUp(self):
        self.owner = Owner()

    def test_falsy_but_present_values_are_legitimate(self):
        for name, value, cls in (("zero", 0, int), ("empty", [], list), ("flag", False, bool)):
            with self.subTest(name=name):
                setattr(self.owner, name, value)
                Attribute.exists(self.owner, name, cls)

    def test_an_absent_attribute_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.exists(self.owner, "nothing_here", int)

    def test_an_attribute_that_is_none_is_refused(self):
        self.owner.holder = None
        with self.assertRaises(AttributeException):
            Attribute.exists(self.owner, "holder", int)

    def test_a_wrong_type_is_refused(self):
        self.owner.count = "three"
        with self.assertRaises(AttributeException):
            Attribute.exists(self.owner, "count", int)

    def test_a_caller_outside_the_family_is_refused_before_it_is_read(self):
        class Spy:
            touched = False

            def __getattr__(self, name):
                type(self).touched = True
                return 1

        with self.assertRaises(AttributeException):
            Attribute.exists(Spy(), "anything", int)
        self.assertFalse(Spy.touched)


# --------------------------------------------------------------------------- #
# evaluate
# --------------------------------------------------------------------------- #
class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.caller = Plain()

    def test_an_instance_passes(self):
        Attribute.evaluate(self.caller, [1], list)

    def test_the_class_itself_is_not_an_instance_of_itself(self):
        with self.assertRaises(AttributeException):
            Attribute.evaluate(self.caller, list, list)

    def test_a_wrong_type_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.evaluate(self.caller, "text", list)

    def test_a_missing_expected_type_asks_for_nothing(self):
        Attribute.evaluate(self.caller, "anything", None)

    def test_a_class_passes_where_a_type_is_expected(self):
        Attribute.evaluate(self.caller, list, type)


# --------------------------------------------------------------------------- #
# allowed
# --------------------------------------------------------------------------- #
class AllowedTest(unittest.TestCase):
    def setUp(self):
        self.caller = Plain()

    def test_declared_keys_pass(self):
        self.assertTrue(Attribute.allowed(self.caller, ["a", "b"], a=1))

    def test_an_undeclared_key_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.allowed(self.caller, ["a"], b=1)

    def test_no_declaration_returns_false(self):
        self.assertFalse(Attribute.allowed(self.caller, None, a=1))

    def test_an_empty_declaration_forbids_every_key(self):
        with self.assertRaises(AttributeException):
            Attribute.allowed(self.caller, [], a=1)

    def test_an_empty_declaration_with_no_keys_is_satisfied(self):
        self.assertTrue(Attribute.allowed(self.caller, []))

    def test_the_class_list_instead_of_a_list_is_refused_cleanly(self):
        with self.assertRaises(AttributeException):
            Attribute.allowed(self.caller, list, a=1)


# --------------------------------------------------------------------------- #
# print_all and print_prop
# --------------------------------------------------------------------------- #
class PrintTest(unittest.TestCase):
    def setUp(self):
        self.thing = Plain()
        self.thing.visible = 1
        self.thing.__dict__["_hidden_"] = 2

    def printed(self, call):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = call(self.thing)
        return result, buffer.getvalue().splitlines()

    def test_print_all_returns_nothing(self):
        result, _ = self.printed(NameHelper.print_all)
        self.assertIsNone(result)

    def test_print_all_prints_every_attribute(self):
        _, lines = self.printed(NameHelper.print_all)
        self.assertEqual(lines, ["visible: 1", "_hidden_: 2"])

    def test_print_prop_returns_nothing(self):
        result, _ = self.printed(NameHelper.print_prop)
        self.assertIsNone(result)

    def test_print_prop_skips_names_wrapped_in_underscores(self):
        _, lines = self.printed(NameHelper.print_prop)
        self.assertEqual(lines, ["visible: 1"])


# --------------------------------------------------------------------------- #
# what the merge added: names, safety of loading, slots, owner, optional
# --------------------------------------------------------------------------- #
BUILT: list = []


class Counted:
    def __init__(self, **kwargs):
        BUILT.append(1)


class CountedWattle(Wattleflow):
    def __init__(self, **kwargs):
        BUILT.append(1)
        super().__init__(**kwargs)


COUNTED = f"{MODULE}.Counted"
COUNTED_WATTLE = f"{MODULE}.CountedWattle"


class Slotted:
    __slots__ = ("shown", "_wrapped_", "unset")

    def __init__(self):
        self.shown = 1
        self._wrapped_ = 2


class Mixed(Slotted):
    def __init__(self):
        super().__init__()
        self.extra = 3


class ReservedNamesTest(unittest.TestCase):
    def test_a_caller_kwarg_named_error_does_not_hide_the_refusal(self):
        with self.assertRaises(AttributeException):
            Attribute.convert(Plain(), "x", int, x="abc", error="boom")

    def test_a_caller_kwarg_named_obj_does_not_hide_the_refusal(self):
        with self.assertRaises(AttributeException):
            Attribute.convert(Plain(), "x", int, x="abc", obj=1)


class LoadingSafetyTest(unittest.TestCase):
    def setUp(self):
        BUILT.clear()
        self.caller = Plain()

    def test_a_class_of_the_wrong_type_is_never_constructed(self):
        for call in (
            lambda: Attribute.get(self.caller, "k", {"k": COUNTED}, Foreign),
            lambda: Attribute.optional(self.caller, "k", Foreign, None, k=COUNTED),
            lambda: Attribute.mandatory(self.caller, "k", LoadableWattle, k=COUNTED),
        ):
            with self.subTest():
                with self.assertRaises(AttributeException):
                    call()
        self.assertEqual(BUILT, [])

    def test_a_class_of_the_right_type_is_constructed_once(self):
        Attribute.get(self.caller, "k", {"k": COUNTED}, Counted)
        self.assertEqual(len(BUILT), 1)

    def test_mandatory_loads_a_class_path_only_for_family_types(self):
        with self.assertRaises(AttributeException):
            Attribute.mandatory(self.caller, "k", Counted, k=COUNTED)
        self.assertEqual(BUILT, [])

    def test_with_no_type_a_string_is_returned_as_it_is(self):
        self.assertEqual(Attribute.get(self.caller, "k", {"k": COUNTED}, None), COUNTED)
        self.assertEqual(BUILT, [])

    def test_a_primitive_type_never_loads_a_class_path(self):
        with self.assertRaises(AttributeException):
            Attribute.get(self.caller, "k", {"k": COUNTED}, int)
        self.assertEqual(BUILT, [])

    def test_a_value_that_was_not_loaded_is_not_stored_on_the_caller(self):
        Attribute.get(self.caller, "k", {"k": 5}, int)
        self.assertFalse(hasattr(self.caller, "k"))


class SlottedObjectTest(unittest.TestCase):
    def printed(self, call, o):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            call(o)
        return buffer.getvalue().splitlines()

    def test_print_all_shows_slots_and_skips_the_unallocated(self):
        self.assertEqual(
            self.printed(NameHelper.print_all, Slotted()), ["shown: 1", "_wrapped_: 2"]
        )

    def test_print_prop_shows_slots_without_the_wrapped_names(self):
        self.assertEqual(self.printed(NameHelper.print_prop, Slotted()), ["shown: 1"])

    def test_list_vars_covers_slots_and_the_dictionary_of_a_subclass(self):
        self.assertEqual(sorted(NameHelper.list_vars(Mixed())), ["extra", "shown"])


class OwnerTest(unittest.TestCase):
    def test_the_name_attribute_wins(self):
        class Named:
            name = "given"

        self.assertEqual(NameHelper.owner(Named()), "given")

    def test_the_class_name_is_the_fallback(self):
        self.assertEqual(NameHelper.owner(Plain()), "Plain")

    def test_it_never_raises(self):
        class Hostile:
            @property
            def name(self):
                raise RuntimeError("no")

        self.assertEqual(NameHelper.owner(Hostile()), "Hostile")


class NameDelegationTest(unittest.TestCase):
    def test_the_attribute_names_agree_with_the_name_helper(self):
        for subject in (Plain, Plain(), len, 5):
            with self.subTest(subject=subject):
                self.assertEqual(
                    Attribute.name(subject), NameHelper.obj_name(subject) or "<unknown>"
                )
                self.assertEqual(Attribute.class_name(subject), NameHelper.cls_name(subject))
                self.assertEqual(Attribute.type_name(subject), NameHelper.typ_name(subject))


if __name__ == "__main__":
    unittest.main()
