from __future__ import annotations

__all__: list[str] = ["main", "parse_args", "run"]

import argparse
import json
import logging
import subprocess
import sys
from collections import abc
from typing import Any


def env_create(env: str, python: str | None) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Create conda env."""
    args: list[str]
    args = [
        "conda",
        "create",
        "--name",
        env,
        "--yes",
        "--channel",
        "conda-forge",
        "--override-channels",
    ]
    if python is not None:
        args.append("python=" + python)
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )


def env_list() -> list[str]:
    """List conda envs."""
    ans: list[str]
    data: Any
    details: dict[str, Any]
    result: subprocess.CompletedProcess  # type: ignore[type-arg]
    try:
        result = subprocess.run(
            ["conda", "env", "list", "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    data = json.loads(result.stdout)
    ans = list()
    for details in data["envs_details"].values():
        ans.append(str(details["name"]))
    return ans


def env_remove(env: str) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Romove env."""
    args: list[str]
    args = ["conda", "env", "remove", "-y", "-n", env]
    return subprocess.run(args, check=True)


def main(args: abc.Iterable[str] | None = None) -> int:
    """Run script through its main CLI."""
    envs: abc.Sequence[str]
    kwargs: dict[str, Any]
    space: argparse.Namespace
    try:
        space = parse_args(args)
        kwargs = vars(space)
        envs = kwargs.pop("envs")
        run(*envs, **kwargs)
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


def parse_args(args: abc.Iterable[str] | None = None, /) -> argparse.Namespace:
    parser: argparse.ArgumentParser
    parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
    # parser.add_argument("--errfile", default="-")
    # parser.add_argument("--outfile", default="-")
    parser.add_argument("--python")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("envs", default=[], nargs="*")
    return parser.parse_args(args)


def run(*envs: str, python: str | None = None, recreate: bool = False) -> None:
    """Run script through its main API."""
    env: str
    envs_: list[str]
    envs_ = env_list()
    for env in envs:
        if env in envs_ and not recreate:
            continue
        if env in envs_:
            env_remove(env)
        env_create(env, python=python)


if __name__ == "__main__":
    sys.exit(main())
