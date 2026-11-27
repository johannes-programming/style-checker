__all__: list[str] = ["outer"]

def outer(value: int) -> None:
    class Example:
        nonlocal value
        value = 1
    print(Example, value)
