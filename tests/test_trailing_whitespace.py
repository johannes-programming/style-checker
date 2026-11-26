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
            f"{line}: trailing whitespace on physical lines!"
            for line in (1, 2, 3, 5, 6, 9)
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

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
            ["1: trailing whitespace on physical lines!"],
        )

    def test_whitespace_inside_line_is_allowed(self: Self, /) -> None:
        source: bytes
        source = b'__all__: list[str] = []\n\nprint("text  ")\n# comment\n'
        self.assertEqual(
            self.diagnostics(source),
            [],
        )

    def test_class_and_decorator(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\n'
            b"@(lambda cls: cls) \n"
            b"class C: \n"
            b"    pass\t\n"
        )
        expected_lines = [
            f"{line}: trailing whitespace on physical lines!"
            for line in (2, 3, 4)
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_trailing_whitespace_and_deep_indentation(
        self: Self,
        /,
    ) -> None:
        expected_lines: list[str]
        source: bytes
        source = b"__all__: list[str] = []\nprint(\n        1  \n)  \n"
        expected_lines = [
            "3: trailing whitespace on physical lines!",
            "4: trailing whitespace on physical lines!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)
        expected_lines = [
            "3: trailing whitespace on physical lines! "
            "physical lines indented two or more levels deeper!",
            "4: trailing whitespace on physical lines!",
        ]
        self.assertEqual(
            self.diagnostics(source + b"if True:\n    pass\n"),
            expected_lines,
        )

    def test_suite_indentation_reported_once(self: Self, /) -> None:
        source: bytes
        source = (
            b"if True:\n"
            b'          print("hello")\n'
            b'          print("world")\n'
            b"__all__: list[str] = []\n"
        )
        self.assertEqual(
            self.diagnostics(source),
            ["2: indentation must be four spaces per level!"],
        )

    def test_nested_and_sibling_suite_indentation(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b"__all__: list[str] = []\n"
            b"if True:\n"
            b"          if True:\n"
            b"              pass\n"
            b'          print("world")\n'
            b"          if True:\n"
            b"                pass\n"
            b"                pass\n"
            b"          pass\n"
            b"else:\n"
            b"          pass\n"
            b"          pass\n"
        )
        expected_lines = [
            f"{line}: indentation must be four spaces per level!"
            for line in (3, 7, 11)
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_two_space_continuation_width(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b"__all__: list[str] = []\n"
            b"if True:\n"
            b"  pass\n"
            b"print(\n"
            b"  1,\n"
            b"    2,\n"
            b")\n"
        )
        expected_lines = [
            "3: indentation must be four spaces per level!",
            "6: physical lines indented two or more levels deeper!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_multiple_rules_and_scopes_on_one_line(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\nclass C:\n    def f(self): pass  \n'
        )
        expected_lines = [
            "3: trailing whitespace on physical lines! "
            "simple statements not at beginning of physical line! "
            "unannotated arguments: 'self'! "
            "first argument must be positional-only!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_multiline_signature(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\n'
            b"class C:\n"
            b"    def f(\n"
            b'        self: "C",\n'
            b"        value\n"
            b"        ,\n"
            b"        *\n"
            b"        , zebra: int,\n"
            b"        apple: int,\n"
            b"    ) -> None:\n"
            b"        pass\n"
        )
        expected_lines = [
            "6: unannotated arguments: 'value'!",
            "7: first argument must be positional-only!",
            "9: keyword-only arguments not in alphabetical order!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_scope_end_and_eof(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["f"]\n'
            b"def f() -> None:\n"
            b"    unused: int\n"
            b"    pass;\n"
            b"# comment\n"
            b"\n"
            b"def g() -> None:\n"
            b'    print("done")\n'
            b"# final comment\n"
        )
        expected_lines = [
            "7: unnecessary declarations: 'unused'!",
            "9: dead module names: 'g'!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_eof_violations_use_last_physical_line(self: Self, /) -> None:
        expected_lines: list[str]
        line: int
        source: bytes
        suffix: bytes
        source = b"def f() -> None:\n    unused: int\n    pass"
        for suffix, line in (
            (b"", 3),
            (b"\n", 3),
            (b"\n\n", 4),
            (b"\n# final comment", 4),
            (b"\n# final comment\n\n", 5),
        ):
            with self.subTest(suffix=suffix):
                expected_lines = [
                    f"{line}: missing '__all__'! dead module names: 'f'! "
                    "unnecessary declarations: 'unused'!",
                ]
                self.assertEqual(
                    self.diagnostics(source + suffix),
                    expected_lines,
                )
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []\nunused: int\n\n"),
            ["3: unnecessary declarations: 'unused'!"],
        )

    def test_multiline_binding_and_global_assignment(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = (
            b'__all__: list[str] = ["f"]\n'
            b"def f() -> None:\n"
            b"    global x\n"
            b"    (\n"
            b"        x\n"
            b"    ) = 1\n"
        )
        expected_lines = [
            "6: missing declarations: 'x'!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_multiline_all(self: Self, /) -> None:
        expected_lines: list[str]
        source: bytes
        source = b'__all__: list[str] = [\n    "z",\n    "a",\n    42,\n]\n'
        expected_lines = [
            "3: '__all__' items not in alphabetical order!",
            "4: '__all__' items must be string literals!",
        ]
        self.assertEqual(self.diagnostics(source), expected_lines)

    def test_missing_all_after_import(self: Self, /) -> None:
        expected_lines: list[str]
        expected_lines = [
            "1: '__all__' must precede imports!",
            "2: missing '__all__'!",
        ]
        self.assertEqual(
            self.diagnostics(b"import os\nprint(os.name)\n"),
            expected_lines,
        )


if __name__ == "__main__":
    unittest.main()
