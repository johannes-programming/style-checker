__all__: list[str] = ['f']
def f() -> None:
    worker: object
    async def worker() -> None:
        pass
    print(worker)
