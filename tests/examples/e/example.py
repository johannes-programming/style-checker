__all__: list[str] = []


def foo(files: list[str]) -> int:
    ans: int
    ans = 0
    for file in files:
        print(file)
        ans = 1

    return ans


def bar(lines: list[str]) -> int:
    ans: int
    ans = 0
    for line in lines:
        print(line)
        ans = 1

    return ans


def baz(lines: list[str]) -> int:
    ans: int
    line: str
    ans = 0
    with open("x.txt", "w") as stream:
        for line in lines:
            print(line, file=stream)
            ans = 1

    return ans
