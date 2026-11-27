__all__: list[str] = ["update"]

async def update(a: int, /, b: int, *args: int, c: int, **kwargs: int) -> None:
    a = 1
    a = 2
    b: int = 3
    args = ()
    c, kwargs = 4, {}
    c += 1
    print((b := 6))
    print([(a := i) for i in range(2)])
