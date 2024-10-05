"""Utility functions."""
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from typing import TypeVar, cast
import logging
import operator
import re
import xml.etree.ElementTree as etree

import yaml

__all__ = ('TextDataResponse', 'assert_not_none', 'chunks', 'dash_to_underscore', 'dotize',
           'get_github_api_credentials', 'is_sha', 'make_github_grit_commit_re',
           'make_github_grit_title_re', 'prefix_v', 'unique_justseen')

logger2 = logging.getLogger(__name__)
T = TypeVar('T')
# From parse-package-name
# https://github.com/egoist/parse-package-name/blob/main/src/index.ts
RE_SCOPED = r'^(@[^\/]+\/[^@\/]+)(?:@([^\/]+))?(\/.*)?$'
RE_NON_SCOPED = r'^([^@\/]+)(?:@([^\/]+))?(\/.*)?$'


@lru_cache
def make_github_grit_commit_re(version: str) -> str:
    return (r'<id>tag:github.com,2008:Grit::Commit/([0-9a-f]{' + str(len(version)) +
            r'})[0-9a-f]*</id>')


@lru_cache
def make_github_grit_title_re() -> str:
    return r'<title>\s+.*v([0-9][^ <]+) '


@lru_cache
def dotize(s: str) -> str:
    ret = s.replace('-', '.').replace('_', '.')
    logger2.debug('dotize(): %s -> %s', s, ret)
    return ret


LEN_SHA = 7
LEN_ISO_DATE = 8


@lru_cache
def is_sha(s: str) -> bool:
    return bool((len(s) == LEN_SHA or len(s) > LEN_ISO_DATE) and re.match(r'^[0-9a-f]+$', s))


def chunks(seq: Sequence[T], n: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class InvalidPackageName(ValueError):
    def __init__(self, pkg: str):
        super().__init__(f'Invalid package name: {pkg}')


def parse_npm_package_name(s: str) -> tuple[str, str | None, str | None]:
    if not (m := re.match(RE_SCOPED, s) or re.match(RE_NON_SCOPED, s)):
        raise InvalidPackageName(s)
    return m[1], m[2], m[3]


@lru_cache
def get_github_api_credentials() -> str:
    with Path('~/.config/gh/hosts.yml').expanduser().open() as f:
        data = yaml.safe_load(f)
    return cast(str, data['github.com']['oauth_token'])


@lru_cache
def prefix_v(s: str) -> str:
    return f'v{s}'


def unique_justseen(iterable: Iterable[T], key: Callable[[T], T] | None = None) -> Iterator[T]:
    """
    Returns an iterator of unique elements, preserving order.

    Parameters
    ----------
    iterable : Iterable[T]
        Iterable.

    key : Callable[[T], T] | None
        Optional key function.

    Returns
    -------
    Iterator[T]
        Unique iterator of items in ``iterable``.
    """
    return (next(x) for x in (operator.itemgetter(1)(y) for y in groupby(iterable, key)))


def assert_not_none(x: T | None) -> T:
    assert x is not None
    return x


def dash_to_underscore(s: str) -> str:
    return s.replace('-', '_')


@dataclass
class TextDataResponse:
    """Used for data URI responses."""
    text: str

    def raise_for_status(self) -> None:
        pass
