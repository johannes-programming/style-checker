__all__: list[str] = ['f']
def f() -> None:
    """Docstring before declarations."""
    import math
    # First group.
    a: int

    # Second group.
    b: float
    a = 1
    b = math.pi
    print(a, b)
