from __future__ import annotations

__all__: list[str] = ["main", "parse_args", "run"]

import argparse
import io
import logging
import sys
import tomllib
from collections import abc
from pathlib import Path
from typing import Any

import tomli_w
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def main(args: abc.Iterable[str] | None = None) -> int:
    space: argparse.Namespace
    try:
        space = parse_args(args)
        run(space.project)
    except SystemExit as exit:
        if isinstance(exit.code, int):
            return int(exit.code)
        else:
            return int(bool(exit.code))
    except BaseException as exc:
        logging.exception(exc)
        return 1
    else:
        return 0


def parse_args(args: abc.Iterable[str] | None = None) -> argparse.Namespace:
    parser: argparse.ArgumentParser
    parser = argparse.ArgumentParser(
        description="Canonicalize project.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument("project", type=Path)
    return parser.parse_args(args)


def run(project: Path, /) -> None:
    data: dict[str, Any]
    instream: io.BufferedReader
    outstream: io.BufferedWriter
    pyproject: Path
    pyproject = project / "pyproject.toml"
    with open(pyproject, "rb") as instream:
        data = tomllib.load(instream)
    data["project"] = run_project(data["project"])
    with open(pyproject, "wb") as outstream:
        tomli_w.dump(data, outstream)


def run_dependency(dependency: str) -> str:
    req: Requirement
    req = Requirement(dependency)
    req.name = canonicalize_name(req.name)
    return str(req)


def run_project(data: dict[str, Any], /) -> dict[str, Any]:
    name: str
    name = canonicalize_name(data["name"])
    data.setdefault("dependencies", [])
    data["dependencies"] = list(map(run_dependency, data["dependencies"]))
    data["name"] = name
    data["urls"]["Download"] = f"https://pypi.org/project/{name}/#files"
    data["urls"]["Index"] = f"https://pypi.org/project/{name}/"
    data["urls"]["Source"] = f"https://github.com/johannes-programming/{name}/"
    data["urls"]["Website"] = f"https://{name}.johannes-programming.online/"
    return data


if __name__ == "__main__":
    sys.exit(main())
