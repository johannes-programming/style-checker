__all__: list[str] = ["C", "outer", "unrelated"]

def outer() -> int:
    from typing import Final as F
    def nested() -> int:
        value: F[int] = 1
        return value
    class Local:
        value: F = 2
    return nested() + Local.value


class C:
    from typing_extensions import Final as F
    value: F = 1
    def method(self: "C", /) -> int:
        from other import F
        local: F = 2
        return local


def unrelated() -> int:
    from other import F
    value: F = 1
    return value
