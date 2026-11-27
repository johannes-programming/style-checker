__all__: list[str] = ['f']
async def f(manager: object) -> None:
    first: object
    async with manager() as first, manager() as second:
        print(first, second)
