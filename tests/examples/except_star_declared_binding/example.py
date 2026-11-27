__all__: list[str] = ['f']
def f() -> None:
    errors: ExceptionGroup
    try:
        raise ExceptionGroup("group", [ValueError()])
    except* ValueError as errors:
        print(errors)
