__all__: list[str] = ['f']
item: int
item = 1
def f() -> list[int]:
    return [item for item in range(3)]
