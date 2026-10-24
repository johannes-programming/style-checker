__all__: list[str] = []

counter: int


def outer() -> None:
    def assign_counter(value: int) -> None:
        global counter
        counter = value

    assign_counter(3)
