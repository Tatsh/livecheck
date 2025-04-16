from typing import TypeVar

T = TypeVar('T')


def assert_not_none(x: T | None) -> T:
    assert x is not None
    return x
