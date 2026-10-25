"""Check imports inside nested statements of a function."""

__all__: list[str] = []


def load(enabled: bool) -> None:
    if enabled:
        from typing import Callable as Factory, Sequence
    import math
