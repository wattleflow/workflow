# Module name: tests/test_module_layout.py
# Layout rule for the concrete layer (STANDARDS §2.7, FRQ-DRV, DEF-DRV-03): `__all__` is the last
# top-level statement of a module, after the definitions it names.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_module_layout -v
import ast
import unittest
from pathlib import Path

CONCRETE = Path(__file__).resolve().parent.parent / "src" / "wattleflow" / "concrete"


def modules() -> list[Path]:
    return [p for p in sorted(CONCRETE.glob("*.py")) if p.name != "__init__.py"]


def is_all(node: ast.stmt) -> bool:
    return isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
    )


class AllPositionTest(unittest.TestCase):
    def test_concrete_modules_are_present(self):
        self.assertGreater(len(modules()), 10)

    def test_every_module_declares_all(self):
        missing = [
            p.name
            for p in modules()
            if not any(is_all(n) for n in ast.parse(p.read_text(encoding="utf-8")).body)
        ]
        self.assertEqual(missing, [])

    def test_all_is_the_last_top_level_statement(self):
        misplaced = []
        for path in modules():
            body = ast.parse(path.read_text(encoding="utf-8")).body
            if body and not is_all(body[-1]):
                misplaced.append(path.name)
        self.assertEqual(misplaced, [])

    def test_all_names_only_defined_names(self):
        undefined = {}
        for path in modules():
            body = ast.parse(path.read_text(encoding="utf-8")).body
            defined = {n.name for n in body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
            defined |= {
                t.id
                for n in body
                if isinstance(n, (ast.Assign, ast.AnnAssign))
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                if isinstance(t, ast.Name)
            }
            imported = {
                (a.asname or a.name).split(".")[0]
                for n in body
                if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names
            }
            for node in body:
                if is_all(node):
                    names = ast.literal_eval(node.value)
                    gone = [name for name in names if name not in defined | imported]
                    if gone:
                        undefined[path.name] = gone
        self.assertEqual(undefined, {})


if __name__ == "__main__":
    unittest.main()
