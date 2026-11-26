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
            [
                f"{line}: trailing whitespace on physical lines!"
                for line in (1, 2, 3, 5, 6, 9)
            ],
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
        source: bytes
        source = (
            b'__all__: list[str] = ["C"]\n'
            b"@(lambda cls: cls) \n"
            b"class C: \n"
            b"    pass\t\n"
        )
        self.assertEqual(
            self.diagnostics(source),
            [
                f"{line}: trailing whitespace on physical lines!"
                for line in (2, 3, 4)
            ],
        )

    def test_trailing_whitespace_and_deep_indentation(
        self: Self,
        /,
    ) -> None:
        source: bytes
        source = b"__all__: list[str] = []\nprint(\n        1  \n)  \n"
        self.assertEqual(
            self.diagnostics(source),
            [
                "3: trailing whitespace on physical lines! "
                "physical lines indented two or more levels deeper!",
                "4: trailing whitespace on physical lines!",
            ],
        )

    def test_multiple_rules_and_scopes_on_one_line(self: Self, /) -> None:
        source = (
            b'__all__: list[str] = ["C"]\nclass C:\n    def f(self): pass  \n'
        )
        self.assertEqual(
            self.diagnostics(source),
            [
                "3: trailing whitespace on physical lines! "
                "simple statements not at beginning of physical line! "
                "unannotated arguments: 'self'! "
                "first argument must be positional-only!",
            ],
        )

    def test_multiline_signature(self: Self, /) -> None:
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
        self.assertEqual(
            self.diagnostics(source),
            [
                "6: unannotated arguments: 'value'!",
                "7: first argument must be positional-only!",
                "9: keyword-only arguments not in alphabetical order!",
            ],
        )

    def test_scope_end_and_eof(self: Self, /) -> None:
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
        self.assertEqual(
            self.diagnostics(source),
            [
                "7: unnecessary declarations: 'unused'!",
                "9: dead module names: 'g'!",
            ],
        )

    def test_eof_violations_use_last_physical_line(self: Self, /) -> None:
        source = b"def f() -> None:\n    unused: int\n    pass"
        for suffix, line in (
            (b"", 3),
            (b"\n", 3),
            (b"\n\n", 4),
            (b"\n# final comment", 4),
            (b"\n# final comment\n\n", 5),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    self.diagnostics(source + suffix),
                    [
                        f"{line}: missing '__all__'! dead module names: 'f'! "
                        "unnecessary declarations: 'unused'!",
                    ],
                )
        self.assertEqual(
            self.diagnostics(b"__all__: list[str] = []\nunused: int\n\n"),
            ["3: unnecessary declarations: 'unused'!"],
        )

    def test_multiline_binding_and_global_assignment(self: Self, /) -> None:
        source = (
            b'__all__: list[str] = ["f"]\n'
            b"def f() -> None:\n"
            b"    global x\n"
            b"    (\n"
            b"        x\n"
            b"    ) = 1\n"
        )
        self.assertEqual(
            self.diagnostics(source),
            [
                "6: missing declarations: 'x'!",
            ],
        )

    def test_multiline_all(self: Self, /) -> None:
        source = b'__all__: list[str] = [\n    "z",\n    "a",\n    42,\n]\n'
        self.assertEqual(
            self.diagnostics(source),
            [
                "3: '__all__' items not in alphabetical order!",
                "4: '__all__' items must be string literals!",
            ],
        )

    def test_missing_all_after_import(self: Self, /) -> None:
        self.assertEqual(
            self.diagnostics(b"import os\nprint(os.name)\n"),
            [
                "1: '__all__' must precede imports!",
                "2: missing '__all__'!",
            ],
        )

    def test_syntax_error_has_no_embedded_line_number(self: Self, /) -> None:
        self.assertEqual(
            self.diagnostics(b"def f():\npass\n"),
            [
                "2: cannot analyze file: invalid syntax!",
            ],
        )


if __name__ == "__main__":
    unittest.main()
