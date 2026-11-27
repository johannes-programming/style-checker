__all__: list[str] = ['f']
items: list[int]
items = [1, 2]
def f() -> list[int]:
    return [item for item in items]
