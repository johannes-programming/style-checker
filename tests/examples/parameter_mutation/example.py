__all__: list[str] = ["update"]

def update(items: list[int], /, obj: object, *, options: dict) -> None:
    items.append(1)
    items[0] = 2
    items[0] += 1
    items[:] = [3]
    obj.value = 2
    obj.value += 1
    options["enabled"] = True
    del options["enabled"]
    print([items for items in range(3)])
