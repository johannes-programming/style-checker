"""Regressions for unused module-level definitions."""

__all__: list[str] = ["TestDeadCode"]

import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Self

from style_checker._declarations import scan


class TestDeadCode(unittest.TestCase):
    def diagnostics(self: Self, source: str) -> list[str]:
        directory: str
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            return list(scan(str(path), "{line}: {desc}"))

    def test_dead_imports_variables_functions_classes(self: Self) -> None:
        messages: list[str]
        messages = self.diagnostics(
            """\
            __all__: list[str] = ["public"]
            import math
            from pathlib import Path
            count: int
            count = 1
            def spare() -> None:
                pass
            class Unused:
                pass
            def public() -> None:
                pass
        """
        )
        self.assertEqual(
            messages,
            ["1: dead module names: Path, Unused, count, math, spare"],
        )

    def test_nested_global_read_is_use(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["user"]
                value: int
                value = 3
                def user() -> int:
                    return value
            """
            ),
            [],
        )

    def test_shadowed_local_is_not_module_use(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["user"]
                value: int
                value = 3
                def user() -> int:
                    value: int
                    value = 5
                    return value
            """
            ),
            ["1: dead module names: value"],
        )

    def test_future_annotations_count_as_uses(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                from __future__ import annotations
                __all__: list[str] = ["build"]
                from pathlib import Path
                def build(p: Path) -> Path:
                    return p
            """
            ),
            [],
        )

    def test_referenced_base_class_not_dead(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["Derived"]
                class Base:
                    pass
                class Derived(Base):
                    pass
            """
            ),
            [],
        )

    def test_nested_class_import_not_module_binding(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["Example"]
                class Example:
                    import math
            """
            ),
            [],
        )

    def test_exported_but_unread_is_not_dead(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["exported"]
                exported: int
                exported = 10
            """
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
