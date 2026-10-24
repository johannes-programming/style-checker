__all__: list[str] = []


def f() -> int:
    result: list[int]
    value: int

    result = [value for value in range(3)]
    value = 5
    return value + len(result)
