__all__: list[str] = ['f']
def f() -> None:
    value = 1
    def set_value() -> None:
        nonlocal value
        value = 2
    set_value()
    print(value)
