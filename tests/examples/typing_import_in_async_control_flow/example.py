__all__: list[str] = ['f']
async def f() -> None:
    if True:
        from typing import Callable as Callback
        print(Callback)
