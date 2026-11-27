__all__: list[str] = ['C', 'value']
value: int
class C:
    def set_value(self: "C", /) -> None:
        global value
        value = 1
