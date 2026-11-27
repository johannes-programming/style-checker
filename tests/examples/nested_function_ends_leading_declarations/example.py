__all__: list[str] = ['f']
def f() -> None:
    def helper() -> None:
        pass
    value: int
    value = 1
    print(helper, value)
