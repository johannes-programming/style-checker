"""Regressions for physical statement placement."""

__all__: list[str] = ["TestStatementPlacement"]

import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Self

from style_checker._declarations import scan


class TestStatementPlacement(unittest.TestCase):
    def diagnostics(self: Self, source: str) -> list[str]:
        directory: str
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            return list(scan(str(path), "{line}: {desc}"))

    def test_module_and_multiline_statements(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = []; print("é"); pass
                print(
                    "hello"
                ); pass
                """
            ),
            ["1: simple statements not at beginning of physical line: 1, 4"],
        )

    def test_nested_scopes_and_headers(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                """\
                __all__: list[str] = ["C", "f"]
                class C: pass
                def f() -> None:
                    if True: pass
                    else: pass
                    try:
                        pass
                    except Exception: pass
                    match 1:
                        case 1: pass
                    async def g() -> None: pass
                """
            ),
            [
                "2: simple statements not at beginning of physical line: 2",
                "3: simple statements not at beginning of physical line: 4, 5, 8, 10",
                "11: simple statements not at beginning of physical line: 11",
            ],
        )

    def test_valid_physical_placement(self: Self) -> None:
        self.assertEqual(
            self.diagnostics(
                '__all__: list[str] = ["C"]\n'
                "class C:\n"
                "    @staticmethod\n"
                "    def f() -> None:\n"
                "        if True: \\\n"
                "            pass; \\\n"
                "            pass;\n"
                '        print("a;b")  # ; pass\n'
                "        (\n"
                '            "a"\n'
                "        )\n"
            ),
            [],
        )
