"""A type alias is not a variable that should be predeclared."""

from __future__ import annotations

__all__: list[str] = ["Alias", "run"]

Alias: object
type Alias = int


def run() -> None:
    Local: object

    type Local[T] = list[T]
