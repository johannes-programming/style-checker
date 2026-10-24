__all__: list[str] = []


def positional_only(value, /) -> None:
    pass


def positional_or_keyword(value) -> None:
    pass


def variadic(*values) -> None:
    pass


def keyword_only(*, value) -> None:
    pass


def keyword_variadic(**values) -> None:
    pass


class Example:
    def method(self, value: int) -> int:
        return value


async def asynchronous(value) -> None:
    pass


def all_annotated(
    positional_only: int,
    /,
    positional_or_keyword: str,
    *values: float,
    keyword_only: bool,
    **options: bytes,
) -> None:
    pass
