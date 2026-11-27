__all__: list[str] = ["Example", "f", "g"]

from typing import Final

if True:
    module_value: Final = 1
    print(module_value)


def f() -> None:
    i: int
    if True:
        a: Final[int] = 1
    else:
        b: Final = 2
    for i in range(1):
        c: Final = 3
    else:
        d: Final = 4
    while False:
        e: Final = 5
    else:
        j: Final = 6
    try:
        k: Final = 7
    except Exception:
        m: Final = 8
    else:
        n: Final = 9
    finally:
        p: Final = 10
    with open("file"):
        q: Final = 11
    match i:
        case 0:
            r: Final = 12
    if True:
        def nested() -> int:
            good: Final = 13
            return good
        class Inner:
            good: Final = 14


async def g(stream: object, manager: object) -> None:
    i: int
    async for i in stream:
        a: Final = 1
    async with manager:
        b: Final = 2


class Example:
    if True:
        value: Final = 1
