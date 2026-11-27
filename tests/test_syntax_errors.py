"""Check style up to, but not beyond, a syntax error."""

__all__: list[str] = ["TestSyntaxErrors"]

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Self

import style_checker


class TestSyntaxErrors(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
