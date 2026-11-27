__all__: list[str] = ["f", "global_capture"]
match 1:
    case unused:
        pass
def f(subject: object) -> None:
    global global_capture
    match subject:
        case global_capture:
            pass
