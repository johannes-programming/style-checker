__all__: list[str] = ['f']
def f(obj: object, items: list[int]) -> None:
    del obj.value, items[0]
