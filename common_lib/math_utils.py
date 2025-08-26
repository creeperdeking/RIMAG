import math


def greater_than_or_close(x: float, y: float) -> bool:
    return x > y or math.isclose(x, y)


def less_than_or_close(x: float, y: float) -> bool:
    return x < y or math.isclose(x, y)


def strict_greater_than(x: float, y: float) -> bool:
    return x > y and not math.isclose(x, y)


def strict_less_than(x: float, y: float) -> bool:
    return x < y and not math.isclose(x, y)
