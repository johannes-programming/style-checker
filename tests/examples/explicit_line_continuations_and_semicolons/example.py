__all__: list[str] = ["C"]
class C:
    @staticmethod
    def f() -> None:
        if True: \
            pass; \
            pass;
        print("a;b")  # ; pass
        (
            "a"
        )
