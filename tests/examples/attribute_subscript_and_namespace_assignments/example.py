__all__: list[str] = ['f']
def f(obj: object, items: list[int]) -> None:
    obj.value = 1
    items[0] = 2
    obj.other: int = 3
    items[1] += 4
    globals()["dynamic"] = 5
    locals()["dynamic"] = 6
