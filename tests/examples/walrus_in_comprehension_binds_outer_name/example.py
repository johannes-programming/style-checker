__all__: list[str] = ['f']
def f() -> None:
    values: list[int]
    values = [(last := item) for item in range(3)]
    print(values, last)
