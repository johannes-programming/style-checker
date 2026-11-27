"""Check style up to, but not beyond, a syntax error."""

__all__: list[str] = ["TestSyntaxErrors"]

import ast
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Any, Self

import style_checker
from style_checker._declarations import FunctionViolation, check_file, scan


class TestSyntaxErrors(unittest.TestCase):
    def check(self: Self, /, source: str, expected: list[str]) -> None:
        actual: list[str]
        caught: Any
        directory: str
        expected_report: list[str]
        path: Path
        rule: str
        syntax: str
        violation: FunctionViolation
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(source, encoding="utf-8")
            # Avoid depending on Python's version-specific wording.
            with self.assertRaises(SyntaxError) as caught:
                compile(source, str(path), "exec", dont_inherit=True)
            syntax = "{name}: {msg}!".format(
                msg=caught.exception.msg,
                name="SYN-" + type(caught.exception).__name__,
            )
            expected_report = [
                line.replace("<syntax>", syntax) for line in expected
            ]
            rule = "SYN-" + type(caught.exception).__name__
            self.assertEqual(
                list(scan(str(path), "{line}: {rule}: {desc}")),
                expected_report,
            )
            self.assertEqual(
                list(scan(str(path), "{line}: {rule}: {desc}", ignore=[rule])),
                expected_report[:-1],
            )
            actual = list(
                scan(str(path), "{line}: {rule}: {desc}", ignore=["SYN"])
            )
            self.assertEqual(actual, expected_report[:-1])
            violation = check_file(str(path))[-1]
            self.assertEqual(
                (violation.rule, violation.desc),
                (rule, caught.exception.msg + "!"),
            )

    def test_module_interruption(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        # The linter also removes trailing whitespace needed by this case.
        expected_lines: list[str]
        expected_lines = [
            "2: LINE-TW: trailing whitespace on physical lines!",
            "2: REQD-MIS: missing declarations: 'value'!",
            "3: LINE-TW: trailing whitespace on physical lines!",
            "4: <syntax>",
        ]
        self.check(
            "unused: int\nvalue = 1  \n# comment \nbroken =\nafter = 2  \n",
            expected_lines,
        )

    def test_open_function(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        expected_lines: list[str]
        expected_lines = [
            "2: FUNC-ARG: unannotated arguments: 'arg'!",
            "4: REQD-MIS: missing declarations: 'value'!",
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
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    unused: int\n"
            "    pass\n"
            "broken =\n",
            ["5: <syntax>"],
        )

    def test_completed_scope_before_error(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    unused: int\n"
            "    pass\n"
            "print(1)\n"
            "broken =\n",
            ["5: EXEM-UN: unnecessary declarations: 'unused'!", "6: <syntax>"],
        )

    def test_same_physical_line(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        # The linter also removes trailing whitespace needed by this case.
        expected: list[str]
        expected = [
            "1: LINE-TW: trailing whitespace on physical lines!",
            "2: <syntax>",
        ]
        self.check(
            "# before  \nx = 1; y = 2; broken =  \nafter = 1  \n",
            expected,
        )
        self.check("x = 1; y = 2; broken =\n", ["1: <syntax>"])

    def test_incomplete_suite(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        expected_lines: list[str]
        expected_lines = [
            "3: FUNC-ARG: unannotated arguments: 'self'!",
            "3: FUNC-POS: first argument must be positional-only!",
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
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            "__all__: list[str] = []\n"
            "try:\n"
            "    try:\n"
            "        value = 1\n"
            "        broken =\n",
            ["4: REQD-MIS: missing declarations: 'value'!", "5: <syntax>"],
        )

    def test_unclosed_expression(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            "__all__: list[str] = []\nvalue = 1\nbroken = (\n",
            ["2: REQD-MIS: missing declarations: 'value'!", "3: <syntax>"],
        )

    def test_indentation_error(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            "__all__: list[str] = []\nvalue = 1\n    broken = 2\n",
            ["2: REQD-MIS: missing declarations: 'value'!", "3: <syntax>"],
        )

    def test_symbol_table_error(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            '__all__: list[str] = ["f"]\n'
            "def f() -> None:\n"
            "    value = 1\n"
            "    global value\n",
            ["3: REQD-MIS: missing declarations: 'value'!", "4: <syntax>"],
        )

    def test_error_at_eof(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        self.check(
            '__all__: list[str] = ["f"]\ndef f(arg):\n',
            ["2: <syntax>"],
        )

    def test_eof_rules_after_syntax_error(self: Self, /) -> None:
        # Actual and synthetic EOF lines must not bypass the syntax cutoff.
        self.check("broken =", ["1: <syntax>"])
        self.check("broken =\n\n \t", ["1: <syntax>"])
        self.check("__all__: list[str] = []\nbroken =\n\n", ["2: <syntax>"])

    def test_error_at_start(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        # The linter also removes trailing whitespace needed by this case.
        self.check("broken =\nafter = 1  \n", ["1: <syntax>"])

    def test_compiler_error(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        # The linter also removes trailing whitespace needed by this case.
        self.check(
            "__all__: list[str] = []\nvalue = 1\nreturn 1  \nafter = 2  \n",
            ["2: REQD-MIS: missing declarations: 'value'!", "3: <syntax>"],
        )

    def test_tab_error(self: Self, /) -> None:
        # Static examples cannot derive the syntax message from compile()
        # or check both forms of suppression and the violation object.
        # The linter also removes trailing whitespace needed by this case.
        self.check(
            "__all__: list[str] = []\nif True:\n    pass\n \tpass  \n",
            ["4: <syntax>"],
        )

    def test_cli_exact_syntax_rule(self: Self, /) -> None:
        # Static examples cannot check CLI exit status and the effect of
        # different spellings of the ignore option through main(). The
        # linter also removes the trailing whitespace in the input.
        directory: str
        exit_status: int
        output: io.StringIO
        path: Path
        rule: str
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("    pass  \nafter = 2  \n", encoding="utf-8")
            for rule in (
                "SYN-SyntaxError",
                "SYN-indentationerror",
                "IndentationError",
                "syn",
            ):
                self._check_cli_syntax_rule(path, rule)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_status = style_checker.main(
                    ["--ignore=SYN-IndentationError", str(path)]
                )
                self.assertEqual(exit_status, 0)
            self.assertEqual(output.getvalue(), "")

    def _check_cli_syntax_rule(self: Self, /, path: Path, rule: str) -> None:
        args: list[str]
        exit_status: int
        output: io.StringIO
        with self.subTest(rule=rule):
            output = io.StringIO()
            args = [f"--ignore={rule}", "--outmsg={rule}: {desc}", str(path)]
            with contextlib.redirect_stdout(output):
                exit_status = style_checker.main(args)
                self.assertEqual(exit_status, 1)
            self.assertEqual(
                output.getvalue(),
                "SYN-IndentationError: unexpected indent!\n",
            )

    def test_all_existing_examples(self: Self, /) -> None:
        """Appending a bad statement must preserve pre-EOF findings."""
        # Static examples cannot append a syntax error to every fixture
        # and compare the resulting diagnostics with the original findings.
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
        before_error: bool
        eof: int
        expected: list[str]
        expected_lines: list[str]
        outmsg: str
        source: str
        suppressed: list[str]
        with self.subTest(fixture=fixture):
            source = fixture.read_text(encoding="utf-8")
            eof = len(source.splitlines())
            outmsg = "{line}: {rule}: {desc}"
            expected = list(scan(str(fixture), outmsg))
            path.write_text(
                source
                + ("" if source.endswith("\n") else "\n")
                + "broken =\n",
                encoding="utf-8",
            )
            actual = list(scan(str(path), outmsg))
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
                actual[-1].endswith("SYN-SyntaxError: invalid syntax!")
            )
            before_error = all(
                int(line.split(":", 1)[0]) < eof + 1 for line in actual[:-1]
            )
            self.assertTrue(before_error)
            suppressed = list(
                scan(str(path), outmsg, ignore=["SYN-SyntaxError"])
            )
            self.assertEqual(suppressed, actual[:-1])
            self.assertNotIn("dead module names", "\n".join(actual))
            self.assertNotIn("missing '__all__'", "\n".join(actual))


if __name__ == "__main__":
    unittest.main()
