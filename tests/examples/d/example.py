__all__: list[str] = []


def nested_annotations(flag: bool):
    alpha: int
    beta: int
    alpha = 1
    if flag:
        beta: int
    else:
        beta: int = 2
    beta = 3
    return alpha + beta
