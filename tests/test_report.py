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
                "2:LINE-TW: physical lines should not end with trailing whitespace!",
                "2:TYPE-MIS: variables requiring declarations should be declared: 'x'!",
                "10:ALL-DEAD: unused module names should be listed in '__all__': 'x'!",
                "10:LINE-TW: physical lines should not end with trailing whitespace!",
            ]
            for file in (str(early), relative):
                expected.extend(f"{file}:{message}\n" for message in messages)
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                self.assertRaises(ExceptionGroup) as caught,
            ):
                style_checker.run(str(late), str(early), relative)
            self.assertEqual(output.getvalue(), "".join(expected))
            self.assertEqual(
                [str(exc) for exc in caught.exception.exceptions], expected
            )
            self.assertEqual(
                style_checker.parse_args([]).outmsg,
                "{file}:{line}:{rule}: {desc}!\n",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_status = style_checker.main(
                    ["--outmsg={rule}/{line}\n", relative, str(early)]
                )
                self.assertEqual(exit_status, 1)
            self.assertEqual(
                output.getvalue().splitlines(),
                ["LINE-TW/2", "TYPE-MIS/2", "ALL-DEAD/10", "LINE-TW/10"] * 2,
            )

    def test_custom_punctuation(self: Self, /) -> None:
        caught: Any
        directory: str
        expected: list[str]
        output: io.StringIO
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("# before  \nbroken =\n", encoding="utf-8")
            expected = [
                "!LINE-TW: physical lines should not end with trailing whitespace.\n",
                "!SYN-SyntaxError: invalid syntax.\n",
            ]
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                self.assertRaises(ExceptionGroup) as caught,
            ):
                style_checker.run(str(path), outmsg="!{rule}: {desc}.\n")
            self.assertEqual(output.getvalue(), "".join(expected))
            self.assertEqual(
                [str(exc) for exc in caught.exception.exceptions], expected
            )
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                self.assertRaises(ExceptionGroup),
            ):
                style_checker.run(str(path))
            expected = [
                f"{path}:1:LINE-TW: physical lines should not end with trailing whitespace!\n",
                f"{path}:2:SYN-SyntaxError: invalid syntax!\n",
            ]
            self.assertEqual(
                output.getvalue(),
                "".join(expected),
            )

    def test_custom_separators(self: Self, /) -> None:
        directory: str
        with tempfile.TemporaryDirectory() as directory:
            self.temp_custom_separators(directory=directory)

    def temp_custom_separators(self: Self, /, *, directory: str) -> None:
        args: list[str]
        caught: Any
        expected: list[str]
        outfile: Path
        outmsg: str
        output: io.StringIO
        path: Path
        separator: str
        path = Path(directory) / "example.py"
        outfile = Path(directory) / "report.txt"
        path.write_text("# before  \nbroken =\n", encoding="utf-8")
        for separator in ("", "; ", "\n\n", "\r\n", "\\n"):
            with self.subTest(separator=separator):
                outmsg = "{rule}" + separator
                expected = [
                    rule + separator for rule in ("LINE-TW", "SYN-SyntaxError")
                ]
                self.go_custom_separators(
                    expected=expected,
                    outmsg=outmsg,
                    path=path,
                )
                args = [
                    f"--outmsg={outmsg}",
                    f"--outfile={outfile}",
                    str(path),
                ]
                self.assertEqual(
                    style_checker.main(args),
                    1,
                )
                self.assertEqual(
                    outfile.read_bytes(), "".join(expected).encode()
                )
        # Suppressing the message text does not suppress the violation.
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(ExceptionGroup) as caught,
        ):
            style_checker.run(str(path), outmsg="")
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            [str(exc) for exc in caught.exception.exceptions], ["", ""]
        )

    def go_custom_separators(
        self: Self,
        /,
        expected: list[str],
        outmsg: str,
        path: Path,
    ) -> None:
        caught: Any
        output: io.StringIO
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(ExceptionGroup) as caught,
        ):
            style_checker.run(str(path), outmsg=outmsg)
        self.assertEqual(output.getvalue(), "".join(expected))
        self.assertEqual(
            [str(exc) for exc in caught.exception.exceptions],
            expected,
        )
