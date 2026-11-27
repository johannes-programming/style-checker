__all__: list[str] = ['f']
def f() -> None:
    print((lambda: (local := 1))())
