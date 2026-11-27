__all__: list[str] = ['f']
async def f(source: object) -> None:
    async for key, value in source:
        print(key, value)
