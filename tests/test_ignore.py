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
from style_checker._declarations import _Rule, scan


class TestIgnore(unittest.TestCase):
    def test_marks_and_independent_suppression(self: Self, /) -> None:
        # Static examples cannot verify rule-mark uniqueness, coverage
        # or suppression of every detected mark and family across all
        # fixtures. The linter also removes the generated trailing spaces.
        actual: list[str]
        baseline: list[str]
        directory: str
        expected: list[str]
        family: str
        fixture: Path
        fixtures: list[Path]
        ignored: set[str]
        issue: str
        line: str
        mark: str
        marks: set[str]
        path: Path
        seen: set[str]
        source: str
        sources: tuple[str, ...]
        marks = {rule.mark for rule in _Rule}
        self.assertEqual(len(marks), len(_Rule))
        for mark in marks:
            self.assertRegex(mark, r"^[A-Z]{2,4}-[A-Z]{2,4}$")
        marks.update(
            {"SYN-SyntaxError", "SYN-IndentationError", "SYN-TabError"}
        )
        seen = set()
        sources = (
            "__all__ = ()\n__all__ = []\n",
            "__all__: list[str] = []\n"
            "exc: Exception\ntry:\n    pass\n"
            "except Exception as exc:\n    print(exc)\n",
            "__all__: list[str] = []  \n",
            "# comment  \nbroken =\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            fixtures = list((Path(__file__).parent / "examples").rglob("*.py"))
            for source in sources:
                path = Path(directory) / f"example{len(fixtures)}.py"
                path.write_text(source, encoding="utf-8")
                fixtures.append(path)
            for fixture in fixtures:
                baseline = list(scan(str(fixture), "{line}: {rule}: {desc}"))
                ignored = set()
                for line in baseline:
                    _, _, issue = line.partition(": ")
                    self.assertTrue(issue.endswith("!"))
                    mark = issue.split(": ", 1)[0]
                    self.assertIn(mark, marks)
                    ignored.add(mark)
                seen.update(ignored)
                for mark in ignored:
                    with self.subTest(fixture=fixture, mark=mark):
                        expected = [
                            line
                            for line in baseline
                            if line.split(": ", 2)[1] != mark
                        ]
                        actual = list(
                            scan(
                                str(fixture),
                                "{line}: {rule}: {desc}",
                                ignore=[mark],
                            )
                        )
                        self.assertEqual(actual, expected)
                for family in {mark.partition("-")[0] for mark in ignored}:
                    with self.subTest(fixture=fixture, family=family):
                        expected = [
                            line
                            for line in baseline
                            if line.split(": ", 2)[1].partition("-")[0]
                            != family
                        ]
                        self.assertEqual(
                            list(
                                scan(
                                    str(fixture),
                                    "{line}: {rule}: {desc}",
                                    ignore=[family],
                                )
                            ),
                            expected,
                        )
                self.assertEqual(
                    list(scan(str(fixture), "{desc}", ignore=marks)), []
                )
                self.assertEqual(
                    list(scan(str(fixture), "{desc}", ignore=[""])), []
                )
        self.assertEqual(seen, marks)

    def test_cli_and_api(self: Self, /) -> None:
        # Static examples cannot test generator-valued ignore arguments,
        # CLI parsing or exit status. The linter also removes the spaces
        # needed for the LINE-TW diagnostic.
        directory: str
        file: Path
        files: list[str]
        name: str
        output: io.StringIO
        source: str
        source = "__all__: list[str] = []\nx = 1  \n"
        with tempfile.TemporaryDirectory() as directory:
            files = []
            for name in ("a.py", "b.py"):
                file = Path(directory) / name
                file.write_text(source, encoding="utf-8")
                files.append(str(file))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with self.assertRaises(ExceptionGroup):
                    style_checker.run(
                        *files,
                        ignore=(mark for mark in ("LINE-TW", "REQD-MIS")),
                        outmsg="{desc}",
                    )
            self.assertEqual(
                output.getvalue(), "dead module names: 'x'!\n" * 2
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    style_checker.main(
                        [
                            "--ignore=LINE-TW",
                            "--ignore=REQD-MIS",
                            "--ignore=DEAD-NAME",
                            *files,
                        ]
                    ),
                    0,
                )
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                style_checker.parse_args(
                    ["--ignore=LINE-TW", "--ignore=REQD-MIS"]
                ).ignore,
                ["LINE-TW", "REQD-MIS"],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    style_checker.main(
                        ["--ignore=UNKNOWN", "--outmsg={desc}", files[0]]
                    ),
                    1,
                )
            self.assertEqual(
                output.getvalue(),
                "dead module names: 'x'!\n"
                "trailing whitespace on physical lines!\n"
                "missing declarations: 'x'!\n",
            )

    def test_empty_ignore_outfile_and_next_file(self: Self, /) -> None:
        # Static examples cannot check report-file contents, CLI parsing,
        # exit status or read errors when all diagnostics are ignored.
        # The linter also removes the trailing whitespace in the inputs.
        directory: str
        bad: Path
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
            self.assertEqual(
                style_checker.main(
                    [
                        "--ignore=SYN",
                        f"--outfile={outfile}",
                        "--outmsg={file}:{line}:{rule}",
                        str(bad),
                        str(next_file),
                    ]
                ),
                1,
            )
            self.assertEqual(
                outfile.read_text(encoding="utf-8"),
                f"{bad}:1:LINE-TW\n{next_file}:1:LINE-TW\n",
            )
            self.assertEqual(
                style_checker.main(
                    [
                        "--ignore=",
                        "--ignore=UNKNOWN",
                        f"--outfile={outfile}",
                        str(bad),
                        str(next_file),
                    ]
                ),
                0,
            )
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
