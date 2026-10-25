"""PEP 695 generic and non-generic module aliases are not variables."""

from __future__ import annotations

__all__: list[str] = ["DictInit", "ItemList", "Slice"]

from collections import abc


type DictInit[Key, Value] = abc.Mapping[Key, Value] | abc.Iterable[
    tuple[Key, Value]
]
type ItemList[T] = list[T]
type Slice[Index] = slice[Index, Index, Index]
