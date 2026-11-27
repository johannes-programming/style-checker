__all__: list[str] = ['f']
def f() -> None:
    __all__: list[str]
    __all__ = ["not", "alphabetical"]
    print(__all__)
