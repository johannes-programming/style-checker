__all__: list[str] = ["outer", "value"]

value: int
value = 0

def outer(value: list[int]) -> None:
    def global_update() -> None:
        global value
        value = 1
    def mutate() -> None:
        nonlocal value
        value.append(2)
        value[0] += 1
    def shadow() -> None:
        import math as value
        def inner() -> None:
            nonlocal value
            value = 3
        inner()
    global_update()
    mutate()
    shadow()
    del value
