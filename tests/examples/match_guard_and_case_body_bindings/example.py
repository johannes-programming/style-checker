__all__: list[str] = ["f"]
def f(subject: object) -> None:
    match subject:
        case 1 | 2 if (accepted := True):
            print(accepted)
        case _:
            rejected = True
            print(rejected)
