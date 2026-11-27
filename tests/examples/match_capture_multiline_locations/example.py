__all__: list[str] = ["f"]
def f(subject: object) -> None:
    match subject:
        case (
            [first, *
             remaining] as
            whole
        ):
            print(first, remaining, whole)
        case {
            "key": value,
            **
            rest,
        }:
            print(value, rest)
        case complex(real=real, imag=imag):
            print(real, imag)
