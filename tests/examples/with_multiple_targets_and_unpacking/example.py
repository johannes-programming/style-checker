__all__: list[str] = ['f']
def f(manager: object) -> None:
    with manager() as (left, right), manager() as extra:
        print(left, right, extra)
