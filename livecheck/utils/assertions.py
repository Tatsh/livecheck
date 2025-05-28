"""Type assertions."""
from __future__ import annotations

from typing import TypeVar

T = TypeVar('T')


def assert_not_none(x: T | None) -> T:  # pragma: no cover
    """Assert that the value is not None."""
    assert x is not None
    return x
