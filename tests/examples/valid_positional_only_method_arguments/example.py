__all__: list[str] = ["C", "f", "outer"]

def identity(value: object) -> object:
    return value


def f(value: int) -> int:
    return value


class C:
    def method(self: "C", /, value: int) -> int:
        def nested(value: int) -> int:
            return value
        return nested(value)

    if True:
        def conditional(self: "C", /) -> None:
            pass

    @classmethod
    def build(cls: type["C"], /) -> "C":
        return cls()

    @staticmethod
    def static(value: int) -> int:
        return value

    @classmethod
    @identity
    def not_direct(value: int) -> int:
        return value

    @identity
    @classmethod
    def direct(cls: type["C"], /) -> None:
        pass

    async def asynchronous(self: "C", /) -> None:
        pass


def outer() -> None:
    class Local:
        def method(self: "Local", /) -> None:
            pass

    def nested(value: int) -> int:
        return value
