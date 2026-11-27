__all__: list[str] = ['f', 'value']
value: int
def f() -> None:
    value: int
    value = 1
    def inner() -> None:
        global value
        value = 2
    inner()
    print(value)
