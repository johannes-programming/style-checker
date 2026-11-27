__all__: list[str] = ['f']
def decorator(*args: int) -> object:
    return lambda fn: fn
@decorator(
        1,
)
def f() -> None:
    pass
