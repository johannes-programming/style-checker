__all__: list[str] = ["C", "Combined", "ordinary", "outside"]

class C:
    def good(self: "C", /, value: int) -> None:
        pass

    def bad(self: "C", value: int) -> None:
        pass

    def missing() -> None:
        pass

    def variadic(*args: int) -> None:
        pass

    def keyword_only(*, self: "C") -> None:
        pass

    @classmethod
    def good_class(cls: type["C"], /) -> None:
        pass

    @classmethod
    def bad_class(cls: type["C"]) -> None:
        pass

    @classmethod
    def missing_class() -> None:
        pass

    @staticmethod
    def static(value: int) -> None:
        pass

    @property
    def decorated(self: "C") -> int:
        return 0

    @staticmethod
    @classmethod
    def inner_classmethod(cls: type["C"]) -> None:
        pass

    @classmethod
    @staticmethod
    def outer_classmethod(value: int) -> None:
        pass

    if True:
        def indirect(self: "C") -> None:
            pass

        @classmethod
        def indirect_class(cls: type["C"]) -> None:
            pass

    def enclosing(self: "C", /) -> None:
        def nested(value: int) -> None:
            pass
        nested(0)

    class Nested:
        def bad(self: "C.Nested") -> None:
            pass

    async def asynchronous(self: "C") -> None:
        pass

@classmethod
def outside(cls: type[C]) -> None:
    pass

def ordinary(value: int) -> None:
    pass

class Combined(C):
    def bad(self) -> None:
        pass
