__all__: list[str] = ["C", "f", "value"]

from typing import Final

value: Final[int]
value = 1


def f() -> int:
    local: Final
    local = 2
    if True:
        nested: Final[int]
        nested = 3
    return local + nested


class C:
    member: Final[int]
