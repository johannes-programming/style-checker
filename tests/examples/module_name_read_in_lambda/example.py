__all__: list[str] = ['f']
value: int
value = 1
def f() -> int:
    return (lambda: value)()
