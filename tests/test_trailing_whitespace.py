"""Regressions for trailing whitespace on physical lines."""

__all__: list[str] = ["TestTrailingWhitespace"]

import tempfile
import unittest
from pathlib import Path
from typing import Self

from style_checker._declarations import scan


class TestTrailingWhitespace(unittest.TestCase):
    def diagnostics(self: Self, /, source: bytes) -> list[str]:
        directory: str
        path: Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_bytes(source)
            return list(scan(str(path), "{line}: {desc}"))

    def test_all_physical_line_types(self: Self, /) -> None:
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
            """1: trailing whitespace on physical lines: 1, 2, 3, 9!
4: trailing whitespace on physical lines: 5, 6!""".split("\n"),
        )

    def test_line_breaks_and_eof(self: Self, /) -> None:
        newline: bytes
        for newline in (b"\n", b"\r\n", b"\r"):
            with self.subTest(newline=newline):
                self.assertEqual(
                    self.diagnostics(b"__all__: list[str] = []" + newline), []
                )
        self.assertEqual(self.diagnostics(b"__all__: list[str] = []"), [])
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []\t"),
            ["1: trailing whitespace on physical lines: 1!"],
        )

    def test_whitespace_inside_line_is_allowed(self: Self, /) -> None:
        source: bytes
        source = b'__all__: list[str] = []\n\nprint("text  ")\n# comment\n'
        self.assertEqual(
            self.diagnostics(source),
            [],
        )

    def test_class_and_decorator(self: Self, /) -> None:
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\n'
            b"@(lambda cls: cls) \n"
            b"class C: \n"
            b"    pass\t\n"
        )
        self.assertEqual(
            self.diagnostics(source),
            ["3: trailing whitespace on physical lines: 2, 3, 4!"],
        )

    def test_trailing_whitespace_and_deep_indentation(
        self: Self,
        /,
    ) -> None:
        line: str
        source: bytes
        source = b"__all__: list[str] = []\nprint(\n        1\n)  \n"
        line = (
            "1: trailing whitespace on physical lines: 4! "
            "physical lines indented two or more levels deeper: 3!"
        )
        self.assertEqual(
            self.diagnostics(source),
            [line],
        )


if __name__ == "__main__":
    unittest.main()
