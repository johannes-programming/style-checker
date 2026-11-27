__all__: list[str] = ['f']
def f(a: int, /, b: int, *c: int, d: int, **e: int) -> None:
    a: int
    b: int
    c: tuple[int, ...]
    d: int
    e: dict[str, int]
    print(a, b, c, d, e)
