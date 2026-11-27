__all__: list[str] = ["f"]


def f(subject: object) -> None:
    match subject:
        case {"key": captured}:
            print(captured)
