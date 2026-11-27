"""Check report identity, ordering, and formatting."""

__all__: list[str] = ["TestReport"]

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Self

import style_checker


class TestReport(unittest.TestCase):
    def test_default_and_order(self: Self, /) -> None:
        # Static examples cannot check relative/absolute path deduplication,
        # exception contents, default formatting or CLI exit status. The
        # linter also removes the trailing whitespace needed by this test.
        caught: Any
        directory: str
        early: Path
        exit_status: int
        expected: list[str]
        file: str
        late: Path
        messages: list[str]
        output: io.StringIO
        relative: str
        source: str
        source = "__all__: list[str] = []\nx = 1  \n" + "\n" * 7 + "# end  \n"
        with tempfile.TemporaryDirectory() as directory:
            early = Path(directory) / "a.py"
            late = Path(directory) / "z.py"
            early.write_text(source, encoding="utf-8")
            late.write_text(source, encoding="utf-8")
            # Relative spelling is retained, but must not determine order.
            relative = os.path.relpath(late)
            expected = []
            messages = [
                "2:LINE-TW: trailing whitespace on physical lines!",
                "2:REQD-MIS: missing declarations: 'x'!",
                "10:DEAD-NAME: dead module names: 'x'!",
                "10:LINE-TW: trailing whitespace on physical lines!",
            ]
            for file in (str(early), relative):
                expected.extend(f"{file}:{message}" for message in messages)
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                self.assertRaises(ExceptionGroup) as caught,
            ):
                style_checker.run(str(late), str(early), relative)
            self.assertEqual(output.getvalue().splitlines(), expected)
            self.assertEqual(
                [str(exc) for exc in caught.exception.exceptions], expected
            )
            self.assertEqual(
                style_checker.parse_args([]).outmsg,
                "{file}:{line}:{rule}: {desc}",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_status = style_checker.main(
                    ["--outmsg={rule}/{line}", relative, str(early)]
                )
                self.assertEqual(exit_status, 1)
            self.assertEqual(
                output.getvalue().splitlines(),
                ["LINE-TW/2", "REQD-MIS/2", "DEAD-NAME/10", "LINE-TW/10"] * 2,
            )
