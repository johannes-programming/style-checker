__all__: list[str] = ['f']
value: int
value = 1
def f() -> None:
    class Local:
        member = value
    print(Local)
