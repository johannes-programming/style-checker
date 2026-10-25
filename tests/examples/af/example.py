"""Function-local and nested PEP 695 type aliases need no declarations."""

from __future__ import annotations

__all__: list[str] = ["build", "load"]


def build(value: int) -> list[int]:
    result: Batch[int]

    type Batch[T] = list[T]

    result = [value]
    return result


async def load() -> None:
    type Callback[T] = list[T]

    def inner(value: str) -> list[str]:
        result: list[str]

        type Inner[T] = tuple[T, T]

        result = [value, value]
        return result

    inner("ok")
