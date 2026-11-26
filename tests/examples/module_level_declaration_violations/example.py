"""Regression fixture for module-level declarations."""

from __future__ import annotations

__all__: list[str] = ["valid"]

import math

zebra: int
alpha: float
duplicate: int
duplicate: int

zebra = 1
alpha = math.pi
duplicate = 2
missing = 3
initialized: int = 4
late: str
late = "value"


def valid(value: int) -> int:
    return value
