# Module name: tests/test_module_layout.py
# top-level statement of a module, after the definitions it names.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_module_layout -v
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "wattleflow"


def modules() -> list[Path]:
    return [p for p in sorted(SRC.rglob("*.py")) if "__pycache__" not in p.parts]


def is_all(node: ast.stmt) -> bool:
    return isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
    )


def is_literal(node: ast.stmt) -> bool:
    value = getattr(node, "value", None)
    return isinstance(value, (ast.List, ast.Tuple)) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts
    )


def is_plain_import(node: ast.stmt) -> bool:
    if isinstance(node, ast.ImportFrom):
        return node.module != "__future__"
    return isinstance(node, ast.Import)


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

    def test_static_all_precedes_imports(self):
        misplaced = []
        for path in modules():
            body = ast.parse(path.read_text(encoding="utf-8")).body
            found = [i for i, n in enumerate(body) if is_all(n)]
            if not found or not is_literal(body[found[0]]):
                continue
            first_import = next((i for i, n in enumerate(body) if is_plain_import(n)), None)
            if first_import is not None and found[0] > first_import:
                misplaced.append(str(path.relative_to(SRC)))
        self.assertEqual(misplaced, [])

    def test_all_names_only_defined_names(self):
        undefined = {}
        for path in modules():
            if "concrete" not in path.parts or path.name == "__init__.py":
                continue
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
                if is_all(node) and is_literal(node):
                    names = ast.literal_eval(node.value)
                    gone = [name for name in names if name not in defined | imported]
                    if gone:
                        undefined[path.name] = gone
        self.assertEqual(undefined, {})


if __name__ == "__main__":
    unittest.main()
