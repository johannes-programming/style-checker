__all__: list[str] = ['f']
def f() -> None:
    from typing_extensions import ParamSpec as PS, TypeAliasType as TA
    P = PS("P")
    Alias = TA("Alias", int)
    print(P, Alias)
