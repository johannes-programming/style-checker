"""Ordinary bindings still need declarations next to type aliases."""

from __future__ import annotations

__all__: list[str] = ["run"]

type Index[T] = list[T]
count = 1


def run() -> int:
    type Pair[T] = tuple[T, T]

    result = count + 1
    return result
