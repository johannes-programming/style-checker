__all__: list[str] = []


def bad_order():
    zebra: int
    apple: int
    zebra = 1
    apple = 2
    return zebra + apple


def missing_and_initialized():
    good: int
    wrong: int = 5
    good = 1
    missing = good + wrong
    return missing


def good_example():
    alpha: int
    beta: int
    alpha = 1
    beta = alpha + 1
    return beta
