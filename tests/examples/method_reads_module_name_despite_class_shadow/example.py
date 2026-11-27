__all__: list[str] = ['C']
value: int
value = 1
class C:
    value = 2
    def method(self: "C", /) -> int:
        return value
