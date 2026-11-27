__all__: list[str] = ["f", "value"]

from typing import Final

value: Final = 1
ordinary: int
ordinary = value
print(ordinary)


def f() -> int:
    redundant: int
    redundant: Final = 1
    late: int
    late = redundant
    return late
