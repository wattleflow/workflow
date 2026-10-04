# Module name: tests/test_helpers_cost.py
# Time cost of every public method of Attribute and NameHelper (FRQ-HLP): each method is run on a
# representative input, its median cost per call is computed, and it must stay within a budget.
# The budget is deliberately generous (it catches an accidental order-of-magnitude regression,
# not a few nanoseconds); the table is printed when WF_TIMING=1.
#
# Run from `workflow/`:
#   WF_TIMING=1 PYTHONPATH=src:../core/src python -m unittest tests.test_helpers_cost -v
import contextlib
import io
import os
import statistics
import timeit
import unittest
from typing import Callable

from wattleflow.concrete.document import DummyReadDocument
from wattleflow.concrete.helpers import Attribute, NameHelper

BUDGET_NS = 200_000  # median per call; the slowest method measures well below a tenth of this
REPEATS = 5
WINDOW_S = 0.02  # each repeat runs for about this long

_document = DummyReadDocument(identifier="a")


class Plain:
    pass


_plain = Plain()
_plain.value = 1


def cases() -> dict[str, Callable[[], object]]:
    """One representative call per public method; `get` builds its dictionary on every call
    because the method consumes the key, so that cost is part of its figure."""
    return {
        "Attribute.allowed": lambda: Attribute.allowed(_plain, ["a", "b"], a=1),
        "Attribute.class_name": lambda: Attribute.class_name(_plain),
        "Attribute.convert": lambda: Attribute.convert(_plain, "n", int, n="5"),
        "Attribute.evaluate": lambda: Attribute.evaluate(_plain, _plain, Plain),
        "Attribute.exists": lambda: Attribute.exists(_document, "identifier", str),
        "Attribute.find_name_by_variable": lambda: Attribute.find_name_by_variable(_plain),
        "Attribute.find_object_by_name": lambda: Attribute.find_object_by_name(_plain),
        "Attribute.get": lambda: Attribute.get(_plain, "k", {"k": 1}, int),
        "Attribute.get_attr": lambda: Attribute.get_attr(_document, "_identifier"),
        "Attribute.load_from_class": lambda: Attribute.load_from_class(
            "n", "collections.OrderedDict", dict
        ),
        "Attribute.mandatory": lambda: Attribute.mandatory(_plain, "s", str, s="x"),
        "Attribute.name": lambda: Attribute.name(_plain),
        "Attribute.optional": lambda: Attribute.optional(_plain, "s", str, "d", s="x"),
        "Attribute.type_name": lambda: Attribute.type_name(_plain),
        "NameHelper.cls_name": lambda: NameHelper.cls_name(_plain),
        "NameHelper.list_dir": lambda: NameHelper.list_dir(_plain),
        "NameHelper.list_vars": lambda: NameHelper.list_vars(_plain),
        "NameHelper.name": lambda: NameHelper.name(_plain),
        "NameHelper.nc": lambda: NameHelper.nc(_plain),
        "NameHelper.nt": lambda: NameHelper.nt(_plain),
        "NameHelper.obj_name": lambda: NameHelper.obj_name(Plain),
        "NameHelper.owner": lambda: NameHelper.owner(_plain),
        "NameHelper.print_all": lambda: NameHelper.print_all(_plain),
        "NameHelper.print_prop": lambda: NameHelper.print_prop(_plain),
        "NameHelper.source_name": lambda: NameHelper.source_name(_plain),
        "NameHelper.typ_name": lambda: NameHelper.typ_name(_plain),
    }


def public_methods() -> set[str]:
    found = set()
    for owner in (Attribute, NameHelper):
        for name, member in vars(owner).items():
            if not name.startswith("_") and isinstance(member, (staticmethod, classmethod)):
                found.add(f"{owner.__name__}.{name}")
    return found


def median_ns(call: Callable[[], object]) -> float:
    """Median cost of one call in nanoseconds; output the method prints is discarded."""
    timer = timeit.Timer(call)
    with contextlib.redirect_stdout(io.StringIO()):
        probe = timer.timeit(number=200) / 200
        loops = max(20, int(WINDOW_S / max(probe, 1e-9)))
        runs = [timer.timeit(number=loops) / loops for _ in range(REPEATS)]
    return statistics.median(runs) * 1e9


class CoverageTest(unittest.TestCase):
    def test_every_public_method_has_a_timing_case(self):
        self.assertEqual(public_methods() - set(cases()), set())

    def test_no_timing_case_names_a_method_that_is_gone(self):
        self.assertEqual(set(cases()) - public_methods(), set())

    def test_the_helpers_expose_at_least_the_known_surface(self):
        self.assertGreaterEqual(len(public_methods()), 26)


class CostTest(unittest.TestCase):
    results: dict[str, float] = {}

    @classmethod
    def setUpClass(cls):
        cls.results = {name: median_ns(call) for name, call in cases().items()}

    @classmethod
    def tearDownClass(cls):
        if os.environ.get("WF_TIMING"):
            print("\nmedian cost per call (ns), budget", BUDGET_NS)
            for name, value in sorted(cls.results.items(), key=lambda item: item[1]):
                print(f"  {name:36} {value:10.0f}")

    def test_every_case_runs_successfully_once(self):
        for name, call in cases().items():
            with self.subTest(method=name), contextlib.redirect_stdout(io.StringIO()):
                call()

    def test_a_cost_is_measured_for_every_case(self):
        self.assertEqual(set(self.results), set(cases()))

    def test_every_method_stays_within_the_budget(self):
        for name, cost in self.results.items():
            with self.subTest(method=name):
                self.assertLess(cost, BUDGET_NS, f"{name}: {cost:.0f} ns per call")

    def test_a_measured_cost_is_positive(self):
        for name, cost in self.results.items():
            with self.subTest(method=name):
                self.assertGreater(cost, 0)


if __name__ == "__main__":
    unittest.main()
