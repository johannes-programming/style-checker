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
            return list(scan(str(path), "{line}: {rule}: {desc}"))

    def test_all_physical_line_types(self: Self, /) -> None:
        # The linter removes trailing whitespace from static examples.
        # Generate exact bytes to cover whitespace on all physical line types.
        expected_lines: list[str]
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
        expected_lines = [
            f"{line}: LINE-TW: trailing whitespace on physical lines!"
            for line in (1, 2, 3, 5, 6, 9)
        ]
        expected_lines.insert(
            -1, "9: LINE-NL: nonempty files must end with a linebreak!"
        )
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_line_breaks_and_eof(self: Self, /) -> None:
        # Exact LF, CRLF, CR and no-final-newline variants are needed.
        # The linter removes the trailing tab in the final variant.
        expected_lines: list[str]
        newline: bytes
        for newline in (b"\n", b"\r\n", b"\r"):
            with self.subTest(newline=newline):
                self.assertEqual(
                    self.diagnostics(b"__all__: list[str] = []" + newline), []
                )
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []"),
            ["1: LINE-NL: nonempty files must end with a linebreak!"],
        )
        expected_lines = [
            "1: LINE-NL: nonempty files must end with a linebreak!",
            "1: LINE-TW: trailing whitespace on physical lines!",
        ]
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []\t"), expected_lines
        )

    def test_class_and_decorator(self: Self, /) -> None:
        # The linter removes the trailing whitespace on the decorator,
        # class header and statement that this test must preserve.
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\n'
            b"@(lambda cls: cls) \n"
            b"class C: \n"
            b"    pass\t\n"
        )
        expected_lines = [
            f"{line}: LINE-TW: trailing whitespace on physical lines!"
            for line in (2, 3, 4)
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_trailing_whitespace_and_deep_indentation(
        self: Self,
        /,
    ) -> None:
        # The linter removes trailing whitespace, which must be preserved
        # to test its interaction with continuation indentation.
        expected_lines: list[str]
        source: bytes
        source = b"__all__: list[str] = []\nprint(\n        1  \n)  \n"
        expected_lines = [
            "3: LINE-TW: trailing whitespace on physical lines!",
            "4: LINE-TW: trailing whitespace on physical lines!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)
        expected_lines = [
            "3: LINE-CONT: physical lines indented two or more levels deeper!",
            "3: LINE-TW: trailing whitespace on physical lines!",
            "4: LINE-TW: trailing whitespace on physical lines!",
        ]
        self.assertEqual(
            self.diagnostics(source + b"if True:\n    pass\n"),
            expected_lines,
        )

    def test_multiple_rules_and_scopes_on_one_line(self: Self, /) -> None:
        # The linter removes trailing whitespace, so a static example
        # cannot preserve the combination of LINE-TW and other findings.
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\nclass C:\n    def f(self): pass  \n'
        )
        expected_lines = [
            "3: FUNC-ARG: unannotated arguments: 'self'!",
            "3: FUNC-POS: first argument must be positional-only!",
            "3: LINE-TW: trailing whitespace on physical lines!",
            "3: STMT-BEG: simple statements not at beginning of physical line!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_eof_violations_use_last_physical_line(self: Self, /) -> None:
        # The linter removes trailing empty lines; exact EOF suffixes
        # are needed to check the physical line of each violation.
        blank: str
        expected_lines: list[str]
        extra: str
        line: int
        missing: str
        source: bytes
        suffix: bytes
        blank = "LINE-BL: whitespace-only lines at end of file!"
        missing = "LINE-NL: nonempty files must end with a linebreak!"
        source = b"def f() -> None:\n    unused: int\n    pass"
        for suffix, line, extra in (
            (b"", 3, missing),
            (b"\n", 3, ""),
            (b"\n\n", 4, blank),
            (b"\n# final comment", 4, missing),
            (b"\n# final comment\n\n", 5, blank),
        ):
            with self.subTest(suffix=suffix):
                expected_lines = [
                    f"{line}: ALL-MIS: missing '__all__'!",
                    f"{line}: DEAD-NAME: dead module names: 'f'!",
                    f"{line}: EXEM-UN: unnecessary declarations: 'unused'!",
                ]
                expected_lines.extend(
                    f"{line}: {msg}" for msg in [extra] if msg
                )
                self.assertEqual(
                    self.diagnostics(source + suffix), expected_lines
                )
        expected_lines = [
            "3: EXEM-UN: unnecessary declarations: 'unused'!",
            f"3: {blank}",
        ]
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []\nunused: int\n\n"),
            expected_lines,
        )

    def test_trailing_blank_lines(self: Self, /) -> None:
        # Generate physical lines because the linter normalizes EOF.
        expected_lines: list[str]
        newline: bytes
        source: bytes
        expected_lines = [
            "2: LINE-BL: whitespace-only lines at end of file!",
            "3: LINE-BL: whitespace-only lines at end of file!",
            "3: LINE-TW: trailing whitespace on physical lines!",
            "4: LINE-BL: whitespace-only lines at end of file!",
        ]
        for newline in (b"\n", b"\r\n", b"\r"):
            source = newline.join(
                [b"__all__: list[str] = []", b"", b" \t\f", b"", b""]
            )
            with self.subTest(newline=newline):
                self.assertEqual(self.diagnostics(source), expected_lines)
        source = b"__all__: list[str] = []\n\n \t"
        expected_lines = [
            "2: LINE-BL: whitespace-only lines at end of file!",
            "3: LINE-BL: whitespace-only lines at end of file!",
            "3: LINE-NL: nonempty files must end with a linebreak!",
            "3: LINE-TW: trailing whitespace on physical lines!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_empty_and_whitespace_only_files(self: Self, /) -> None:
        expected_lines: list[str]
        self.assertEqual(
            self.diagnostics(b""), ["1: ALL-MIS: missing '__all__'!"]
        )
        expected_lines = [
            "1: ALL-MIS: missing '__all__'!",
            "1: LINE-BL: whitespace-only lines at end of file!",
        ]
        self.assertEqual(self.diagnostics(b"\n"), expected_lines)
        expected_lines += [
            "1: LINE-NL: nonempty files must end with a linebreak!",
            "1: LINE-TW: trailing whitespace on physical lines!",
        ]
        self.assertEqual(self.diagnostics(b" \t"), expected_lines)

    def test_interior_blank_lines(self: Self, /) -> None:
        source: bytes
        source = b"\n__all__: list[str] = []\n\n \t\n\n# last\n"
        self.assertEqual(
            self.diagnostics(source),
            ["4: LINE-TW: trailing whitespace on physical lines!"],
        )


if __name__ == "__main__":
    unittest.main()
