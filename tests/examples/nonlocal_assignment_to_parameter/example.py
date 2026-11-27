__all__: list[str] = ['f']
def f(value: int) -> None:
    def set_value() -> None:
        nonlocal value
        value = 2
    set_value()
    print(value)
