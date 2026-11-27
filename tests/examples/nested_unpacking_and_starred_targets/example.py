__all__: list[str] = ['f']
def f() -> None:
    first, (middle, *rest) = (1, (2, 3, 4))
    print(first, middle, rest)
