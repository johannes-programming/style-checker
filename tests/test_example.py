__all__: list[str] = ["TestExample"]

import contextlib
import enum
import io
import os
import tempfile
import tomllib
import unittest
from functools import cached_property
from pathlib import Path
from typing import Any, Self

import style_checker


class Cfg(enum.Enum):
    cfg = None

    @cached_property
    def data(self: Self, /) -> dict[str, Any]:
        return tomllib.loads(
            (Path(__file__).parent / "testdata.toml").read_text(),
        )

    @staticmethod
    def make_file(*, file: str, root: Path, text: str) -> None:
        part: str
        path: Path
        path = root
        for part in file.split("/"):
            path = path / part
        path.write_bytes(text.encode("utf-8"))


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

    def go_testdata(
        self: Self,
        /,
        *,
        ans: list[str],
        call: dict[str, Any],
        code: dict[str, Any],
    ) -> None:
        exception: ExceptionGroup | None
        stdout: io.StringIO
        tmp: Path
        tmp_: str
        x: str
        y: str
        stdout = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            tempfile.TemporaryDirectory() as tmp_,
        ):
            tmp = Path(tmp_)
            for x, y in code.items():
                Cfg.make_file(text=y, file=x, root=tmp)
            try:
                style_checker.run(
                    str(tmp / "**" / "*.py"),
                    **call,
                )
            except ExceptionGroup as eg:
                exception = eg
            else:
                exception = None
            self.assertEqual(exception is None, not ans)
            if stdout.getvalue() == "":
                self.assertListEqual(ans, [])
                return
            self.assertListEqual(
                ans + [""],
                stdout.getvalue().split("\n"),
            )

    def test_example(self: Self, /) -> None:
        # This is the example runner itself: it discovers all fixtures
        # and checks their output and exception status.
        file: Path
        for file in (Path(__file__).parent / "examples").rglob("ans.txt"):
            with self.subTest(key=os.path.basename(file.parent)):
                self.go(file)

    def test_testdata(self: Self, /) -> None:
        x: str
        y: dict[str, Any]
        for x, y in Cfg.cfg.data.items():
            with self.subTest(key=x):
                self.go_testdata(**y)



if __name__ == "__main__":
    unittest.main()
