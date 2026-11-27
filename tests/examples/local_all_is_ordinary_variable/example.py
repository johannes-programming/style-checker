__all__: list[str] = ['f']
def f() -> None:
    __all__: list[str] = ["local"]
    print(__all__)
