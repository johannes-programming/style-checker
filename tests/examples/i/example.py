__all__: list[str] = []


def foo():
    try:
        0 / 0
    except Exception as exc:
        print(exc)
    print(exc)
