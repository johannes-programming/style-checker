"""Check class-scope imports, but permit typing-only annotations."""

__all__: list[str] = []


class Example:
    from collections.abc import Iterable
    from typing import Iterator, Self
