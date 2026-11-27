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
* ``Final`` annotations are initialized in place at namespace indentation,
    after the declaration block or later, and are not declarations;
* the first non-declaration occurrence of each local variable must be a binding
    occurrence, not a read;
* every function parameter must have a type annotation;
* function parameters must not be reassigned.

Function parameters, ``global`` names, and ``nonlocal`` names are exempt from
local-variable declarations.
Nested functions/classes are checked independently and their bodies are not
treated as part of the enclosing function.

Each distinct file, physical line, and rule produces one report line.
"""

from __future__ import annotations

__all__: list[str] = [
    "main",
    "parse_args",
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

ERRMSG_DEFAULT = "{file}:{line}:{rule}: {desc}"


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
    return [ans[path] for path in sorted(ans)]


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
        add_help=False,
        description="Check module and function variable declaration style.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="exclude files",
        metavar="exclude",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help=("ignore a rule or family; empty mark ignores all (repeatable)"),
        metavar="mark",
    )
    parser.add_argument(
        "--outfile",
        default="-",
        help="write the report to this file, stdout being designated by the default of '-'",
    )
    parser.add_argument(
        "--outmsg",
        default=ERRMSG_DEFAULT,
        help="format each message",
    )
    version = "%(prog)s, version " + metadata.version("style-checker")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        help="print the version and abort",
        version=version,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="print this message and abort",
    )
    parser.add_argument(
        "include",
        nargs="*",
        help="Python source files to check",
    )
    return parser.parse_args(args)


def run(
    *include: str,
    exclude: abc.Iterable[str] = (),
    ignore: abc.Iterable[str] = (),
    outfile: str = "-",
    outmsg: str = ERRMSG_DEFAULT,
) -> None:
    exceptions: list[Exception]
    file: str
    files: list[str]
    ignored: frozenset[str]
    line: str
    opener: contextlib.AbstractContextManager[TextIO]
    stream: TextIO
    files = get_files(include=include, exclude=exclude)
    ignored = frozenset(ignore)

    if outfile == "-":
        opener = contextlib.nullcontext(sys.stdout)
    else:
        opener = open(outfile, "w", encoding="utf-8", newline="\n")

    exceptions = []
    with opener as stream:
        for file in files:
            for line in _declarations.scan(
                file, errmsg=outmsg, ignore=ignored
            ):
                print(line, file=stream)
                exceptions.append(Exception(line))
    if exceptions:
        raise ExceptionGroup(
            "Style violated!",
            exceptions,
        )


if __name__ == "__main__":
    sys.exit(main())
