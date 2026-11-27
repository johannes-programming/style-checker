__all__: list[str] = ['f']
def f() -> None:
    print([x + y for pair in [(1, 2)] for x, y in [pair] if x])
