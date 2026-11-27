__all__: list[str] = ["TestExample"]

import contextlib
import io
import os
import tomllib
import unittest
from pathlib import Path
from typing import Self

import style_checker


class TestExample(unittest.TestCase):
    def go(self: Self, file: Path, /) -> None:
        expected: str
        stdout: io.StringIO
        calldata = tomllib.loads((file.parent / "call.toml").read_text())
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            try:
                style_checker.run(
                    str(file.parent / "**" / "*.py"),
                    **calldata,
                )
            except ExceptionGroup as eg:
                exception = eg
            else:
                exception = None
        expected = file.read_text(encoding="utf-8")
        self.assertEqual(stdout.getvalue(), expected)
        self.assertEqual(exception is None, not expected)

    def test_example(self: Self, /) -> None:
        file: Path
        for file in (Path(__file__).parent / "examples").rglob("ans.txt"):
            with self.subTest(key=os.path.basename(file.parent)):
                self.go(file)


if __name__ == "__main__":
    unittest.main()
