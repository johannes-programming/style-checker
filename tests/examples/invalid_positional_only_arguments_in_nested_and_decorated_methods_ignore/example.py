__all__: list[str] = ["C", "outer", "outside"]

def identity(value: object) -> object:
    return value


class C:
    def method(self: "C") -> None:
        pass

    if True:
        def conditional(self: "C") -> None:
            pass

    def missing() -> None:
        pass

    def variadic(*args: object) -> None:
        pass

    def keyword_only(*, self: "C") -> None:
        pass

    @classmethod
    def build(cls: type["C"]) -> "C":
        return cls()

    @identity
    @classmethod
    def direct(cls: type["C"]) -> None:
        pass

    async def asynchronous(self: "C") -> None:
        pass

    @classmethod
    async def async_build(cls: type["C"]) -> None:
        pass

    def unannotated(self) -> None:
        pass


def outer() -> None:
    class Local:
        def method(self: "Local") -> None:
            pass

    @classmethod
    def nested(cls: type[object]) -> None:
        pass


@classmethod
# A comment is not an intervening decorator.

def outside(cls: type[object]) -> None:
    pass
