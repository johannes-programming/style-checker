"""Final annotations after declarations and at later points."""

from __future__ import annotations

__all__: list[str] = ["Example", "calculate", "make_async", "total"]

from typing import Final
import typing as t
from typing_extensions import Final as Constant
import typing_extensions as te

total: int

zebra: Final[int] = 2
apple: Final = 1
total = zebra + apple
later: t.Final[int] = total

def calculate(value: int) -> int:
    result: int
    z: Constant[int] = 3
    a: Final = value
    result = z + a
    later: te.Final = result
    return later


async def make_async() -> int:
    from typing import Final as F
    result: F[int] = later
    return result


class Example:
    from typing import Final as ClassFinal
    limit: ClassFinal = 2
    threshold: Final[int] = 1

    def method(self: Example, /) -> int:
        offset: t.Final = self.limit
        return offset
