__all__: list[str] = []


def function_imports_before_declarations(value: float) -> int:
    """Imports may precede a function's local declarations."""
    import math
    from math import floor

    result: int
    result = floor(value)
    return result
