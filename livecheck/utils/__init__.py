"""Utility functions."""
from __future__ import annotations

from .assertions import assert_not_none
from .misc import check_program
from .requests import (
    TextDataResponse,
    close_sessions,
    get_content,
    get_last_modified,
    hash_url,
    init_sessions,
    session_init,
)
from .string import dash_to_underscore, dotize, extract_sha, is_sha, prefix_v

__all__ = ('TextDataResponse', 'assert_not_none', 'check_program', 'close_sessions',
           'dash_to_underscore', 'dotize', 'extract_sha', 'get_content', 'get_last_modified',
           'hash_url', 'init_sessions', 'is_sha', 'prefix_v', 'session_init')
