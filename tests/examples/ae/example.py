"""Classes interleaved with the leading function declarations are allowed."""

__all__: list[str] = ["make", "make_async"]


def make() -> int:
    class First:
        pass

    a: int

    class Middle:
        pass

    b: int

    class Last:
        pass

    a = 1
    b = 2
    return a + b


async def make_async() -> int:
    class Local:
        pass

    count: int
    count = 2
    return count
