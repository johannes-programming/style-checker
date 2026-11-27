__all__: list[str] = ['f']
async def f(manager: object, source: object) -> None:
    first: object
    item: object
    last: bool
    async with manager() as first:
        print(first)
    async for item in source:
        print(item)
    else:
        last = True
        print(last)
