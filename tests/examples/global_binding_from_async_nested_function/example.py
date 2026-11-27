__all__: list[str] = ['f', 'value']
async def f() -> None:
    global value
    value = 1
