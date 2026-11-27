__all__: list[str] = ['f']
def f() -> None:
    print({item for item in range(3)})
    print({key: value for key, value in [(1, 2)]})
    print(sum(item for item in range(3)))
