"""Ensure the checker and its test harness obey the default style rules."""

from __future__ import annotations

__all__: list[str] = ["TestSelfStyle"]

import unittest
from pathlib import Path
from typing import Self

import style_checker


class TestSelfStyle(unittest.TestCase):
    def test_self_style(self: Self, /) -> None:
        exclude: list[str]
        include: list[str]
        root: Path
        root = Path(__file__).parent.parent
        exclude = [str(root / "tests" / "examples" / "**" / "*.py")]
        include = [
            str(root / "run_tests.py"),
            str(root / "src" / "**" / "*.py"),
            str(root / "tests" / "**" / "*.py"),
        ]
        style_checker.run(
            *include,
            exclude=exclude,
        )
