__all__: list[str] = ['f']
import typing as t
from collections import abc
def f(x: t.Iterable[int]) -> abc.Iterator[int]:
    return iter(x)
