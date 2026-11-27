__all__: list[str] = ["f"]


def f(subject: object) -> None:
    captured: object
    match subject:
        case {"key": captured}:
            print(captured)
