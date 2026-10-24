__all__: list[str] = []


def outer(value: int) -> int:
    total: int

    def middle() -> None:
        def assign_total() -> None:
            nonlocal total
            total = value

        assign_total()

    middle()
    return total
