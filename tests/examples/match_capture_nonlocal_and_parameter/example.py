__all__: list[str] = ["f"]
def f(parameter: object) -> None:
    captured: object
    def inner(subject: object) -> None:
        nonlocal captured
        match subject:
            case captured:
                print(captured)
    match 1:
        case parameter:
            print(parameter)
    inner(parameter)
