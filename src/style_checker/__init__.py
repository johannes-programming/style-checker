#!/usr/bin/env python3
"""
Check module-level and function-local variable declaration style rules.

Rule implemented
----------------
At module level and inside every ``def`` or ``async def``:

* local variables that are bound by assignment-like syntax in that function
    must first be declared with a bare type annotation, e.g. ``count: int``;
* those declarations must form one contiguous block at the beginning of the
    function body (an optional docstring may precede them);
* declarations must not assign a value;
* declaration names must be in alphabetical order;
* the first non-declaration occurrence of each local variable must be a binding
    occurrence, not a read;
* every function parameter must have a type annotation.

Function parameters, ``global`` names, and ``nonlocal`` names are exempt from
local-variable declarations.
Nested functions/classes are checked independently and their bodies are not
treated as part of the enclosing function.

Each offending function produces exactly one report line.
"""

from __future__ import annotations

__all__: list[str] = [
    "main",
    "run",
]
import argparse
import contextlib
import glob
import io
import os
import sys
from collections.abc import Iterable, Sequence
from typing import Any

from style_checker import _declarations

ERRMSG_DEFAULT: str

ERRMSG_DEFAULT = "{file}:{line}: {desc}"


def main(args: Sequence[str] | None = None, /) -> int:
    kwargs: dict[str, Any]
    parser: argparse.ArgumentParser

    parser = argparse.ArgumentParser(
        description="Check module and function variable declaration style."
    )
    parser.add_argument(
        "--errfile",
        default="-",
        help="write the report to this file instead of stderr",
    )
    parser.add_argument(
        "--errmsg",
        default=ERRMSG_DEFAULT,
        help=f"diagnostic format",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="exclude files",
        metavar="exclude",
    )
    parser.add_argument(
        "include",
        nargs="*",
        help="Python source files to check",
    )
    kwargs = vars(parser.parse_args(args))
    args = kwargs.pop("include")
    return run(*args, **kwargs)


def get_files(*, include: Iterable[str], exclude: Iterable[str]) -> list[str]:
    ans: dict[str, str]
    file: str
    pattern: str
    ans = dict()
    for pattern in include:
        for file in glob.glob(pattern, recursive=True):
            ans[os.path.abspath(file)] = file
    for pattern in exclude:
        for file in glob.glob(pattern, recursive=True):
            ans.pop(os.path.abspath(file), "")
    return list(ans.values())


def run(
    *include: str,
    errfile: str = "-",
    errmsg: str = ERRMSG_DEFAULT,
    exclude: Iterable[str] = (),
) -> int:
    ans: int
    file: str
    files: list[str]
    line: str
    opener: contextlib.AbstractContextManager[io.TextIOWrapper]
    stream: io.TextIOWrapper
    files = get_files(include=include, exclude=exclude)

    if errfile == "-":
        opener = contextlib.nullcontext(sys.stderr)
    else:
        opener = open(errfile, "w", encoding="utf-8", newline="\n")

    ans = 0
    with opener as stream:
        for file in files:
            for line in _declarations.scan(file, errmsg=errmsg):
                print(line, file=stream)
                ans = 1

    return ans


if __name__ == "__main__":
    main()
