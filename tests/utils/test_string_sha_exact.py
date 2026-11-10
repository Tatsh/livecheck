"""Tests that is_sha() only matches exact-length hashes."""

from __future__ import annotations

from livecheck.utils.string import is_sha


def test_is_sha_rejects_longer_than_full_sha() -> None:
    sha = 'a' * 41
    assert is_sha(f'https://example.com/commit/{sha}') == 0
    assert is_sha(sha) == 0


def test_is_sha_rejects_longer_than_short_sha() -> None:
    sha = 'abcdef12'
    assert is_sha(f'https://example.com/commit/{sha}') == 0
    assert is_sha(sha) == 0
