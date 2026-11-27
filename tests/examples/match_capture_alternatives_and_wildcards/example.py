__all__: list[str] = ["f"]
def f(subject: object) -> None:
    match subject:
        case [captured, *_] | {"key": captured} if captured:
            print(captured)
        case _:
            pass
