"""The shipped package imports numpy and the standard library only, and
nothing from the projection service, so it can leave this repository
unchanged (research/value-scale-plan.md, B4). The corpus tools and the
tests are not shipped and may use more."""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


class IndependenceTests(unittest.TestCase):
    def test_shipped_modules_use_numpy_and_the_standard_library_only(self):
        allowed = set(sys.stdlib_module_names) | {"numpy", "valuescale", "__future__"}
        shipped = sorted(PACKAGE.glob("*.py"))
        self.assertTrue(any(p.name == "gates.py" for p in shipped))
        for path in shipped:
            self.assertLessEqual(_imports(path), allowed, path.name)

    def test_nothing_imports_the_service(self):
        for path in PACKAGE.rglob("*.py"):
            self.assertNotIn("service", _imports(path), str(path.relative_to(PACKAGE)))


if __name__ == "__main__":
    unittest.main()
