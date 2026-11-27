__all__: list[str] = ["TestExample"]

import contextlib
import io
import os
import tomllib
import unittest
from pathlib import Path
from typing import Any, Self

import style_checker
from style_checker._declarations import scan


class TestExample(unittest.TestCase):
    def go(self: Self, file: Path, /) -> None:
        calldata: dict[str, Any]
        exception: ExceptionGroup[Exception] | None
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
        # This is the example runner itself: it discovers all fixtures
        # and checks their output and exception status.
        file: Path
        for file in (Path(__file__).parent / "examples").rglob("ans.txt"):
            with self.subTest(key=os.path.basename(file.parent)):
                self.go(file)

    def test_self_style(self: Self, /) -> None:
        """Apply all style rules to the implementation and test scripts."""
        file: Path
        files: list[Path]
        report: list[str]
        root: Path
        test_files: list[Path]
        tests: Path
        root = Path(__file__).resolve().parents[1]
        tests = root / "tests"
        files = sorted((root / "src").rglob("*.py"))
        self.assertTrue(files, "No implementation files found")
        test_files = sorted(
            file
            for file in tests.rglob("*.py")
            if not file.is_relative_to(tests / "examples")
        )
        files.extend(test_files)
        files.append(root / "run_tests.py")
        for file in files:
            with self.subTest(file=file.relative_to(root)):
                report = list(scan(str(file), "{file}:{line}:{rule}: {desc}"))
                self.assertEqual(report, [])


if __name__ == "__main__":
    unittest.main()
