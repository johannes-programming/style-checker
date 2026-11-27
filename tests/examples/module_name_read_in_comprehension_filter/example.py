__all__: list[str] = ['f']
limit: int
limit = 3
def f() -> list[int]:
    return [item for item in range(5) if item < limit]
