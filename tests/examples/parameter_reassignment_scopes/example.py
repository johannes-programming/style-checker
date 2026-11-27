__all__: list[str] = ["outer"]

def outer(value: int) -> None:
    def local(value: int) -> None:
        value = 2
    def other() -> None:
        value: int
        value = 3
        def inner() -> None:
            nonlocal value
            value = 4
        inner()
    class Example:
        value = 5
        def method(self: "Example", /) -> None:
            nonlocal value
            value = 6
    def default(arg: int = (value := 7)) -> None:
        pass
    print((lambda value: (value := 8))(9))
    print([value for value in range(10)])
    local(value)
    other()
    default()
    Example().method()
