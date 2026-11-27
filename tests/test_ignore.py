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
        actual: list[str]
        baseline: list[str]
        directory: str
        expected: list[str]
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
        marks = set(_Rule.__members__)
        self.assertEqual(len(marks), len(_Rule))
        for mark in marks:
            self.assertRegex(mark, r"^[A-Z]{2,4}$")
        marks.update({"SyntaxError", "IndentationError", "TabError"})
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
                self.assertEqual(
                    list(scan(str(fixture), "{desc}", ignore=marks)), []
                )
        self.assertEqual(seen, marks)

    def test_cli_and_api(self: Self, /) -> None:
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
                        ignore=(mark for mark in ("TW", "DMIS")),
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
                            "--ignore=TW",
                            "--ignore=DMIS",
                            "--ignore=DEAD",
                            *files,
                        ]
                    ),
                    0,
                )
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                style_checker.parse_args(
                    ["--ignore=TW", "--ignore=DMIS"]
                ).ignore,
                ["TW", "DMIS"],
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
                "missing declarations: 'x'!\n"
                "trailing whitespace on physical lines!\n",
            )
