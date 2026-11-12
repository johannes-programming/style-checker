#!/usr/bin/env python3
"""
Check module-level and function-local variable declaration style rules.

Rule implemented
----------------
At module level and inside every ``def`` or ``async def``:

* local variables that are bound by assignment-like syntax in that function
    must first be declared with a bare type annotation, e.g. ``count: int``;
* those declarations must form one block at the beginning of the function
    body (an optional docstring and interleaved classes are permitted);
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
import os
import sys
from collections import abc
from importlib import metadata
from typing import Any, TextIO

from style_checker import _declarations

ERRMSG_DEFAULT: str

ERRMSG_DEFAULT = "{file}:{line}: {desc}"


def get_files(
    *, exclude: abc.Iterable[str], include: abc.Iterable[str]
) -> list[str]:
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


def main(args: abc.Iterable[str] | None = None) -> int:
    include: abc.Sequence[str]
    kwargs: dict[str, Any]
    space: argparse.Namespace
    try:
        space = parse_args(args)
        kwargs = vars(space)
        include = kwargs.pop("include")
        run(*include, **kwargs)
    except SystemExit as exit:
        if isinstance(exit.code, int):
            return int(exit.code)
        else:
            return int(bool(exit.code))
    except BaseException:
        return 1
    else:
        return 0


def parse_args(args: abc.Iterable[str] | None = None) -> argparse.Namespace:
    parser: argparse.ArgumentParser
    version: str
    parser = argparse.ArgumentParser(
        description="Check module and function variable declaration style.",
        fromfile_prefix_chars="@",
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
    version = "%(prog)s, version " + metadata.version("style-checker")
    parser.add_argument(
        "--version",
        action="version",
        version=version,
    )
    parser.add_argument(
        "include",
        nargs="*",
        help="Python source files to check",
    )
    return parser.parse_args(args)


def run(
    *include: str,
    errfile: str = "-",
    errmsg: str = ERRMSG_DEFAULT,
    exclude: abc.Iterable[str] = (),
) -> int:
    ans: int
    file: str
    files: list[str]
    line: str
    opener: contextlib.AbstractContextManager[TextIO]
    stream: TextIO
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
    sys.exit(main())
