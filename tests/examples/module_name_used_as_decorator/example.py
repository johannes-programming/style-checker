__all__: list[str] = ['f']
def decorate(fn: object) -> object:
    return fn
@decorate
def f() -> None:
    pass
