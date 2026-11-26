__all__: list[str] = ["TestExample"]

import contextlib
import io
import os
import unittest
from pathlib import Path
from typing import Self

import style_checker


class TestExample(unittest.TestCase):
    def go(self: Self, file: Path, /) -> None:
        args: list[str]
        expected: str
        stdout: io.StringIO
        args = [
            "--outmsg={line}: {desc}",
            "--",
            str(file.parent / "**" / "*.py"),
        ]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            style_checker.main(args)
        expected = file.read_text(encoding="utf-8")
        self.assertEqual(stdout.getvalue(), expected)

    def test_example(self: Self, /) -> None:
        file: Path
        for file in (Path(__file__).parent / "examples").rglob("ans.txt"):
            with self.subTest(key=os.path.basename(file.parent)):
                self.go(file)


if __name__ == "__main__":
    unittest.main()
