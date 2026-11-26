"""Check style up to, but not beyond, a syntax error."""

__all__: list[str] = ["TestSyntaxErrors"]

import ast
import symtable
import tempfile
import unittest
from pathlib import Path
from typing import Any, Self

from style_checker._declarations import scan


class TestSyntaxErrors(unittest.TestCase):
    def check(self: Self, /, source: str, expected: list[str]) -> None:
        caught: Any
        directory: str
        path: Path
        syntax: str
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(source, encoding="utf-8")
            # Avoid depending on Python's version-specific wording.
            with self.assertRaises(SyntaxError) as caught:
                ast.parse(source, filename=str(path))
                symtable.symtable(source, str(path), "exec")
            syntax = "{name}: {msg}!".format(
                msg=caught.exception.msg,
                name=type(caught.exception).__name__,
            )
            self.assertEqual(
                list(scan(str(path), "{line}: {desc}")),
                [line.replace("<syntax>", syntax) for line in expected],
            )

    def test_module_interruption(self: Self, /) -> None:
        expected_lines: list[str]
        expected_lines = [
            "2: trailing whitespace on physical lines! "
            "missing declarations: 'value'!",
            "3: trailing whitespace on physical lines!",
            "4: <syntax>",
        ]
        self.check(
            "unused: int\nvalue = 1  \n# comment \nbroken =\nafter = 2  \n",
            expected_lines,
        )

    def test_open_function(self: Self, /) -> None:
        expected_lines: list[str]
        expected_lines = [
            "2: unannotated arguments: 'arg'!",
            "4: missing declarations: 'value'!",
            "5: <syntax>",
        ]
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f(arg):\n"
            "    unused: int\n"
            "    value = 1\n"
            "    broken =\n"
            "    unused = 2\n",
            expected_lines,
        )

    def test_closed_function(self: Self, /) -> None:
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    unused: int\n"
            "    pass\n"
            "broken =\n",
            ["5: unnecessary declarations: 'unused'! <syntax>"],
        )

    def test_completed_scope_before_error(self: Self, /) -> None:
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    unused: int\n"
            "    pass\n"
            "print(1)\n"
            "broken =\n",
            ["5: unnecessary declarations: 'unused'!", "6: <syntax>"],
        )

    def test_same_physical_line(self: Self, /) -> None:
        expected_lines: list[str]
        expected_lines = [
            "1: simple statements not at beginning of physical line! "
            "missing declarations: 'x', 'y'! <syntax>",
        ]
        self.check("x = 1; y = 2; broken =\n", expected_lines)

    def test_incomplete_suite(self: Self, /) -> None:
        expected_lines: list[str]
        expected_lines = [
            "3: unannotated arguments: 'self'! "
            "first argument must be positional-only!",
            "4: <syntax>",
        ]
        self.check(
            '__all__: list[str] = ["C"]\n'
            "class C:\n"
            "    def f(self):\n"
            "        broken =\n",
            expected_lines,
        )

    def test_unfinished_nested_try(self: Self, /) -> None:
        self.check(
            "__all__: list[str] = []\n"
            "try:\n"
            "    try:\n"
            "        value = 1\n"
            "        broken =\n",
            ["4: missing declarations: 'value'!", "5: <syntax>"],
        )

    def test_unclosed_expression(self: Self, /) -> None:
        self.check(
            "__all__: list[str] = []\nvalue = 1\nbroken = (\n",
            ["2: missing declarations: 'value'!", "3: <syntax>"],
        )

    def test_indentation_error(self: Self, /) -> None:
        self.check(
            "__all__: list[str] = []\nvalue = 1\n    broken = 2\n",
            ["2: missing declarations: 'value'!", "3: <syntax>"],
        )

    def test_symbol_table_error(self: Self, /) -> None:
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    value = 1\n"
            "    global value\n",
            ["3: missing declarations: 'value'!", "4: <syntax>"],
        )

    def test_error_at_eof(self: Self, /) -> None:
        self.check(
            '__all__: list[str] = ["f"]\ndef f(arg):\n',
            ["2: unannotated arguments: 'arg'! <syntax>"],
        )

    def test_error_at_start(self: Self, /) -> None:
        self.check("broken =\nafter = 1  \n", ["1: <syntax>"])

    def test_all_existing_examples(self: Self, /) -> None:
        """Appending a bad statement must preserve pre-EOF findings."""
        directory: str
        fixture: Path
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            for fixture in (Path(__file__).parent / "examples").rglob("*.py"):
                self._check_example(fixture, path)

    def _check_example(self: Self, /, fixture: Path, path: Path) -> None:
        actual: list[str]
        actual_lines: list[str]
        eof: int
        expected: list[str]
        expected_lines: list[str]
        source: str
        with self.subTest(fixture=fixture):
            source = fixture.read_text(encoding="utf-8")
            eof = len(source.splitlines())
            expected = list(scan(str(fixture), "{line}: {desc}"))
            path.write_text(
                source
                + ("" if source.endswith("\n") else "\n")
                + "broken =\n",
                encoding="utf-8",
            )
            actual = list(scan(str(path), "{line}: {desc}"))
            try:
                ast.parse(source)
            except SyntaxError:
                self.assertEqual(actual, expected)
                return
            # The original last line can contain EOF-only findings
            # or scope-end findings now located at the error line.
            actual_lines = [
                line for line in actual if int(line.split(":", 1)[0]) < eof
            ]
            expected_lines = [
                line for line in expected if int(line.split(":", 1)[0]) < eof
            ]
            self.assertEqual(actual_lines, expected_lines)
            self.assertTrue(actual[-1].startswith(f"{eof + 1}: "))
            self.assertTrue(
                actual[-1].endswith("SyntaxError: invalid syntax!")
            )
            self.assertNotIn("dead module names", "\n".join(actual))
            self.assertNotIn("missing '__all__'", "\n".join(actual))


if __name__ == "__main__":
    unittest.main()
