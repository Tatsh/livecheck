"""Utility functions."""
import re

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar
from urllib.parse import urlparse

import logging
from http import HTTPStatus
import requests
from requests import ConnectTimeout, ReadTimeout
from loguru import logger

import keyring

__all__ = ('TextDataResponse', 'assert_not_none', 'chunks', 'dash_to_underscore', 'dotize',
           'get_github_api_credentials', 'is_sha', 'make_github_grit_commit_re', 'prefix_v',
           'session_init', 'get_content', 'extract_sha')

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
def dotize(s: str) -> str:
    ret = s.replace('-', '.').replace('_', '.')
    logger2.debug('dotize(): %s -> %s', s, ret)
    return ret


@lru_cache
def is_sha(url: str) -> int:
    """
    Extracts the last part of a URL and checks if it is a valid SHA-1 hash.

    :param url: The input URL string.
    :return: 7 if it's a short SHA, 40 if it's a full SHA, 0 otherwise.
    """
    last_part = urlparse(url).path.rsplit('/', 1)[-1] if '/' in url else url

    if re.match(r'^[0-9a-f]{40}', last_part):
        return 40
    if re.match(r'^[0-9a-f]{7}', last_part):
        return 7
    return 0


def extract_sha(text: str) -> str:
    """
    Extracts the first valid SHA-1 hash (7 or 40 characters) found in the given string.

    :param text: The input string to search.
    :return: A SHA-1 hash (7 or 40 characters) if found, otherwise None.
    """
    match = re.search(r'\b[0-9a-f]{7,40}\b', text)
    return match.group(0) if match else ''


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
def get_github_api_credentials(repo: str = 'github.com') -> str | None:
    if not (token := keyring.get_password(repo, 'livecheck')):
        logger.warning(f"No {repo} API token found in your secret store")
    return token


@lru_cache
def prefix_v(s: str) -> str:
    return f'v{s}'


def assert_not_none(x: T | None) -> T:
    assert x is not None
    return x


def dash_to_underscore(s: str) -> str:
    return s.replace('-', '_')


@dataclass
class TextDataResponse:
    """Used for data URI responses."""
    text: str
    status_code: int = HTTPStatus.OK  # Default status code for successful response

    def raise_for_status(self) -> None:
        pass


@lru_cache
def session_init(module: str) -> requests.Session:
    session = requests.Session()
    if module == 'github':
        token = get_github_api_credentials()
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Accept'] = 'application/vnd.github.v3+json'
    elif module == 'xml':
        session.headers['Accept'] = 'application/xml'
    elif module == 'json':
        session.headers['Accept'] = 'application/json'
    elif module == 'gitlab':
        token = get_github_api_credentials('gitlab.com')
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Accept'] = 'application/json'
    elif module == 'bitbucket':
        token = get_github_api_credentials('api.bitbucket.org')
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Accept'] = 'application/json'
    session.headers['timeout'] = '30'
    return session


def get_content(url: str) -> requests.Response:
    parsed_uri = urlparse(url)
    logger.debug(f'Fetching {url}')

    if parsed_uri.hostname == 'api.github.com':
        session = session_init('github')
    elif parsed_uri.hostname == 'gitlab.com':
        session = session_init('gitlab')
    elif parsed_uri.hostname == 'api.bitbucket.org':
        session = session_init('bitbucket')
    elif url.endswith('.atom') or url.endswith('.xml'):
        session = session_init('xml')
    elif url.endswith('.json'):
        session = session_init('json')
    else:
        session = session_init('')

    r: TextDataResponse | requests.Response  # only Mypy wants this
    try:
        r = session.get(url)
    except (ReadTimeout, ConnectTimeout, requests.exceptions.HTTPError,
            requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema, requests.exceptions.ChunkedEncodingError) as e:
        logger.error(f'Caught error {e} attempting to fetch {url}')
        r = requests.Response()
        r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r
    if r.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.ACCEPTED,
                             HTTPStatus.PARTIAL_CONTENT, HTTPStatus.MOVED_PERMANENTLY,
                             HTTPStatus.FOUND, HTTPStatus.TEMPORARY_REDIRECT,
                             HTTPStatus.PERMANENT_REDIRECT):
        logger.error(f'Error fetching {url} status_code {r.status_code}')
    else:
        if not r.text:
            logger.warning(f'Empty response for {url}')

    return r
