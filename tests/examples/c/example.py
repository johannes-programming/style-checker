from __future__ import annotations

__all__: list[str] = [
    "foo",
]

import ast
from pathlib import Path
from typing import Any


def foo(path: str) -> Any:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    return tree
