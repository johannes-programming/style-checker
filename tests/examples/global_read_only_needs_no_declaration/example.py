__all__: list[str] = ['f', 'value']
value: int
value = 1
def f() -> int:
    global value
    return value
