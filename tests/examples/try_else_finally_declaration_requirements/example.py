__all__: list[str] = ['f']
def f() -> None:
    try:
        attempted = 1
    except ValueError:
        pass
    else:
        successful = 2
    finally:
        cleaned = 3
    print(attempted, successful, cleaned)
