"""Regressions for trailing whitespace on physical lines."""

__all__: list[str] = ["TestTrailingWhitespace"]

import tempfile
import unittest
from pathlib import Path
from typing import Self

from style_checker._declarations import scan


class TestTrailingWhitespace(unittest.TestCase):
    def diagnostics(self: Self, source: bytes) -> list[str]:
        directory: str
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_bytes(source)
            return list(scan(str(path), "{line}: {desc}"))

    def test_all_physical_line_types(self: Self) -> None:
        source: bytes
        source = (
            b'__all__: list[str] = ["f"]  \r\n'
            b"# comment\t\r\n"
            b" \t\r\n"
            b"def f() -> None:\r\n"
            b'    print("hello ") \r\n'
            b'    print("""first  \r\n'
            b"    second\r\n"
            b'    """)\r\n'
            b"# final comment "
        )
        self.assertEqual(
            self.diagnostics(source),
            """1: trailing whitespace on physical lines: 1, 2, 3, 9
4: trailing whitespace on physical lines: 5, 6""".split("\n")
        )
