__all__: list[str] = ['Alias', 'P', 'T', 'Ts']
import typing as t
import typing_extensions as te
Alias = te.TypeAliasType("Alias", int)
P = t.ParamSpec("P")
T = t.TypeVar("T")
Ts = te.TypeVarTuple("Ts")
