# Module name: tests/test_helpers_structure.py
# Structure of concrete/helpers.py (NFRQ-ORG-05, FRQ-HLP DEF-HLP-03): a method that refers to its own
# class goes through `cls` and is a classmethod; a staticmethod refers to no member of its class,
# except the public methods whose signature binds `cls` as a domain type (exception c.1, deferred:
# renaming that parameter is a public API decision, workflow scripts call it by keyword).
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_helpers_structure -v
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src" / "wattleflow" / "concrete" / "helpers.py"

# NFRQ-ORG-05 exception c.1: the domain type is a parameter named `cls`
DEFERRED = {
    "Attribute.exists",
    "Attribute.get",
    "Attribute.load_from_class",
    "Attribute.mandatory",
    "Attribute.optional",
}


def static_methods():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for klass in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for method in (n for n in klass.body if isinstance(n, ast.FunctionDef)):
            if "staticmethod" in {ast.unparse(d) for d in method.decorator_list}:
                yield klass, method


def names_own_class(klass: ast.ClassDef, method: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == klass.name
        for node in ast.walk(method)
    )


class OwnClassReferenceTest(unittest.TestCase):
    def test_there_are_static_methods_to_check(self):
        self.assertGreater(len(list(static_methods())), 5)

    def test_a_staticmethod_names_its_own_class_only_where_the_deferral_applies(self):
        offenders = {
            f"{klass.name}.{method.name}"
            for klass, method in static_methods()
            if names_own_class(klass, method)
        }
        self.assertEqual(offenders - DEFERRED, set())

    def test_every_deferred_method_really_binds_cls(self):
        binds = {
            f"{klass.name}.{method.name}"
            for klass, method in static_methods()
            if "cls" in [a.arg for a in method.args.posonlyargs + method.args.args]
        }
        self.assertEqual(DEFERRED - binds, set())

    def test_the_deferral_list_has_no_stale_entry(self):
        named = {
            f"{klass.name}.{method.name}"
            for klass, method in static_methods()
            if names_own_class(klass, method)
        }
        self.assertEqual(DEFERRED - named, set())


if __name__ == "__main__":
    unittest.main()
