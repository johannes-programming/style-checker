__all__: list[str] = ["f", "value"]

from other import Final
from other import typing as t

value: Final[int] = 1


def f() -> int:
    other: t.Final = 2
    return other
