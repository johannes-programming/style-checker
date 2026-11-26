"""Check report identity, ordering, and formatting."""

__all__: list[str] = ["TestReport"]

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import Self

import style_checker
from style_checker._declarations import check_file


class TestReport(unittest.TestCase):
    def test_default_and_order(self: Self, /) -> None:
        directory: str
        early: Path
        expected: list[str]
        late: Path
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
            for file in (str(early), relative):
                expected.extend(
                    [
                        f"{file}:2:DMIS: missing declarations: 'x'!",
                        f"{file}:2:TW: trailing whitespace on physical lines!",
                        f"{file}:10:DEAD: dead module names: 'x'!",
                        f"{file}:10:TW: trailing whitespace on physical lines!",
                    ]
                )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with self.assertRaises(ExceptionGroup) as caught:
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
                self.assertEqual(
                    style_checker.main(
                        ["--outmsg={rule}/{line}", relative, str(early)]
                    ),
                    1,
                )
            self.assertEqual(
                output.getvalue().splitlines(),
                ["DMIS/2", "TW/2", "DEAD/10", "TW/10"] * 2,
            )

    def test_same_rule_across_scopes(self: Self, /) -> None:
        directory: str
        file: Path
        source: str
        source = (
            '__all__: list[str] = ["f"]\n'
            "shared: int\n"
            "zebra: int\n"
            "def f() -> None:\n"
            "    apple: int\n"
            "    shared: int\n"
            "    pass\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "example.py"
            file.write_text(source, encoding="utf-8")
            self.assertEqual(
                [(v.line, v.rule, v.desc) for v in check_file(str(file))],
                [
                    (
                        7,
                        "DUN",
                        "unnecessary declarations: 'apple', 'shared', 'zebra'!",
                    )
                ],
            )
