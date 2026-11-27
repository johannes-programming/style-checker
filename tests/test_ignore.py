"""Test diagnostic marks and independent rule suppression."""

from __future__ import annotations

__all__: list[str] = ["TestIgnore"]

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Self

import style_checker


class TestIgnore(unittest.TestCase):
    def test_cli_and_api(self: Self, /) -> None:
        # Static examples cannot test generator-valued ignore arguments,
        # CLI parsing or exit status. The linter also removes the spaces
        # needed for the LINE-TW diagnostic.
        args: list[str]
        directory: str
        exit_status: int
        file: Path
        files: list[str]
        name: str
        output: io.StringIO
        parsed_ignore: list[str]
        source: str
        source = "__all__: list[str] = []\nx = 1  \n"
        with tempfile.TemporaryDirectory() as directory:
            files = []
            for name in ("a.py", "b.py"):
                file = Path(directory) / name
                file.write_text(source, encoding="utf-8")
                files.append(str(file))
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                self.assertRaises(ExceptionGroup),
            ):
                style_checker.run(
                    *files,
                    ignore=(mark for mark in ("LINE-TW", "TYPE-MIS")),
                    outmsg="{desc}\n",
                )
            self.assertEqual(
                output.getvalue(),
                "unused module names should be listed in '__all__': 'x'\n" * 2,
            )
            output = io.StringIO()
            args = [
                "--ignore=LINE-TW",
                "--ignore=TYPE-MIS",
                "--ignore=ALL-DEAD",
                *files,
            ]
            with contextlib.redirect_stdout(output):
                exit_status = style_checker.main(args)
                self.assertEqual(exit_status, 0)
            self.assertEqual(output.getvalue(), "")
            args = ["--ignore=LINE-TW", "--ignore=TYPE-MIS"]
            parsed_ignore = style_checker.parse_args(args).ignore
            self.assertEqual(parsed_ignore, ["LINE-TW", "TYPE-MIS"])
            output = io.StringIO()
            args = ["--ignore=UNKNOWN", "--outmsg={desc}\n", files[0]]
            with contextlib.redirect_stdout(output):
                self.assertEqual(style_checker.main(args), 1)
            self.assertEqual(
                output.getvalue(),
                "unused module names should be listed in '__all__': 'x'\n"
                "physical lines should not end with trailing whitespace\n"
                "variables requiring declarations should be declared: 'x'\n",
            )

    def test_empty_ignore_outfile_and_next_file(self: Self, /) -> None:
        # Static examples cannot check report-file contents, CLI parsing,
        # exit status or read errors when all diagnostics are ignored.
        # The linter also removes the trailing whitespace in the inputs.
        args: list[str]
        bad: Path
        directory: str
        next_file: Path
        outfile: Path
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "a.py"
            next_file = Path(directory) / "b.py"
            outfile = Path(directory) / "report.txt"
            bad.write_text(
                "# before  \nbroken =\n# after  \n", encoding="utf-8"
            )
            next_file.write_text(
                "__all__: list[str] = []  \n", encoding="utf-8"
            )
            args = [
                "--ignore=SYN",
                f"--outfile={outfile}",
                "--outmsg={file}:{line}:{rule}\n",
                str(bad),
                str(next_file),
            ]
            self.assertEqual(style_checker.main(args), 1)
            self.assertEqual(
                outfile.read_text(encoding="utf-8"),
                f"{bad}:1:LINE-TW\n{next_file}:1:LINE-TW\n",
            )
            args = [
                "--ignore=",
                "--ignore=UNKNOWN",
                f"--outfile={outfile}",
                str(bad),
                str(next_file),
            ]
            self.assertEqual(style_checker.main(args), 0)
            self.assertEqual(outfile.read_bytes(), b"")
            style_checker.run(
                str(bad), str(next_file), ignore=[""], outfile=str(outfile)
            )
            self.assertEqual(outfile.read_bytes(), b"")
            self.assertEqual(
                style_checker.parse_args(["--ignore="]).ignore, [""]
            )
            self.assertEqual(style_checker.parse_args([]).ignore, [])
            # Ignoring diagnostics does not skip reading/checking files.
            with self.assertRaises(UnicodeDecodeError):
                bad.write_bytes(b"\xff")
                style_checker.run(str(bad), ignore=[""], outfile=str(outfile))
