__all__: list[str] = ['f']
def f() -> None:
    value: int
    value = 1
    def middle() -> None:
        value: int
        def inner() -> None:
            nonlocal value
            value = 2
        inner()
        print(value)
    middle()
    print(value)
