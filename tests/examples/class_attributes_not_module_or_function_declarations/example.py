__all__: list[str] = ['C']
class C:
    count: int = 1
    flag = True
    unused: str
    __all__ = (1,)
    def method(self: "C", /) -> None:
        self.new = 2
