__all__: list[str] = ['f']
def f() -> None:
    for left, right in [(1, 2)]:
        print(left, right)
    else:
        exhausted = True
        print(exhausted)
