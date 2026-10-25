"""TypeVar and related typing constructs require no declarations."""

__all__: list[str] = []

from typing import ParamSpec
from typing import TypeVar as TV
from typing import TypeVarTuple

T = TV("T")
P = ParamSpec("P")
Ts = TypeVarTuple("Ts")


def local_typevar() -> object:
    from typing import TypeVar

    LocalT = TypeVar("LocalT")
    return LocalT
