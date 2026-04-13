"""Type assertions."""
from __future__ import annotations

from typing import TypeVar

T = TypeVar('T')


def assert_not_none(x: T | None) -> T:  # pragma: no cover
    """
    Assert that the value is not None.

    Returns
    -------
    T
        The same value when it is not ``None``.

    Raises
    ------
    AssertionError
        If ``x`` is ``None``.
    """
    if x is None:
        msg = 'Expected non-None value'
        raise AssertionError(msg)
    return x
