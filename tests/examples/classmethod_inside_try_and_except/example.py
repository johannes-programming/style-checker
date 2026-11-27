__all__: list[str] = ['C']
class C:
    try:
        @classmethod
        def build(cls: type) -> None:
            pass
    except Exception:
        @classmethod
        def recover(cls: type) -> None:
            pass
