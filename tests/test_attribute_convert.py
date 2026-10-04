# Module name: tests/test_attribute_convert.py
# Tests for Attribute.convert (FRQ-HLP, DEF-HLP-01): the method returns the converted value and
# leaves the caller's keyword arguments alone.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_attribute_convert -v
import unittest
from enum import Enum

from wattleflow.concrete.exception import AttributeException
from wattleflow.concrete.helpers import Attribute


class Colour(Enum):
    RED = "r"
    GREEN = "g"


class Level(Enum):
    LOW = 1
    HIGH = 2


class Caller:
    pass


class ConvertedValueTest(unittest.TestCase):
    def setUp(self):
        self.caller = Caller()

    def test_a_value_of_the_right_type_is_returned_unchanged(self):
        value = [1, 2]
        self.assertIs(Attribute.convert(self.caller, "n", list, n=value), value)

    def test_a_convertible_value_is_returned_converted(self):
        self.assertEqual(Attribute.convert(self.caller, "n", int, n="5"), 5)

    def test_an_enum_member_is_found_by_name(self):
        self.assertIs(Attribute.convert(self.caller, "c", Colour, c="RED"), Colour.RED)

    def test_an_enum_member_is_found_by_value(self):
        self.assertIs(Attribute.convert(self.caller, "c", Colour, c="g"), Colour.GREEN)
        self.assertIs(Attribute.convert(self.caller, "l", Level, l=2), Level.HIGH)

    def test_an_enum_member_passes_through(self):
        self.assertIs(Attribute.convert(self.caller, "c", Colour, c=Colour.GREEN), Colour.GREEN)


class ConvertRefusalTest(unittest.TestCase):
    def setUp(self):
        self.caller = Caller()

    def test_an_unknown_enum_value_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.convert(self.caller, "c", Colour, c="BLUE")

    def test_an_unconvertible_value_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.convert(self.caller, "n", int, n="five")

    def test_an_absent_name_is_refused(self):
        with self.assertRaises(AttributeException):
            Attribute.convert(self.caller, "n", int, other=1)

    def test_the_refusal_names_the_value_and_the_expectation(self):
        with self.assertRaises(AttributeException) as caught:
            Attribute.convert(self.caller, "c", Colour, c="BLUE")
        message = str(caught.exception)
        self.assertIn("BLUE", message)
        self.assertIn("RED", message)


class ConvertDoesNotTouchTheCallerTest(unittest.TestCase):
    def test_the_callers_dictionary_is_left_alone(self):
        kwargs = {"n": "5"}
        Attribute.convert(Caller(), "n", int, **kwargs)
        self.assertEqual(kwargs, {"n": "5"})


if __name__ == "__main__":
    unittest.main()
