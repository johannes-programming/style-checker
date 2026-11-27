__all__: list[str] = ['f']
def f() -> None:
    error: Exception
    try:
        pass
    except (
        ValueError,
        TypeError,
    ) as error:
        print(error)
