"""Utility functions."""
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from functools import lru_cache
from http import HTTPStatus
from typing import TypeVar
from urllib.parse import urlparse
import hashlib
import logging
import re
import subprocess

from loguru import logger
from packaging.version import Version
from requests import ConnectTimeout, ReadTimeout
import keyring
import requests

__all__ = ('TextDataResponse', 'assert_not_none', 'chunks', 'dash_to_underscore', 'dotize',
           'is_sha', 'prefix_v', 'session_init', 'get_content', 'extract_sha', 'check_program')

logger2 = logging.getLogger(__name__)
T = TypeVar('T')
# From parse-package-name
# https://github.com/egoist/parse-package-name/blob/main/src/index.ts
RE_SCOPED = r'^(@[^\/]+\/[^@\/]+)(?:@([^\/]+))?(\/.*)?$'
RE_NON_SCOPED = r'^([^@\/]+)(?:@([^\/]+))?(\/.*)?$'


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
def get_api_credentials(repo: str) -> str | None:
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
        token = get_api_credentials('github.com')
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Accept'] = 'application/vnd.github.v3+json'
    elif module == 'xml':
        session.headers['Accept'] = 'application/xml'
    elif module == 'json':
        session.headers['Accept'] = 'application/json'
    elif module == 'gitlab':
        token = get_api_credentials('gitlab.com')
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        session.headers['Accept'] = 'application/json'
    elif module == 'bitbucket':
        token = get_api_credentials('bitbucket.org')
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
    elif parsed_uri.hostname == 'api.gitlab.com':
        session = session_init('gitlab')
    elif parsed_uri.hostname == 'api.bitbucket.org':
        session = session_init('bitbucket')
    elif parsed_uri.hostname == 'repology.org':
        session = session_init('json')
        session.headers['User-Agent'] = 'DistroWatch'
    elif url.endswith(('.atom', '.xml')):
        session = session_init('xml')
    elif url.endswith('json'):
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
    elif not r.text:
        logger.warning(f'Empty response for {url}')

    return r


def check_program(cmd: str, args: str = '', min_version: str | None = None) -> bool:
    """
    Check if a program is installed and optionally check if the installed version is at least
    the specified minimum version.

    :param cmd: The command to check.
    :param args: The arguments to pass to the command.
    :param min_version: The minimum version required.
    :return: True if the program is installed and the version is at least the minimum version.
    """
    try:
        result = subprocess.run([cmd, args],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                                check=False)
        if result.returncode != 0:
            return False
    except FileNotFoundError:
        return False
    try:
        if min_version and Version(result.stdout.strip()) < Version(min_version):
            return False
    except ValueError:
        return False

    return True


@lru_cache
def hash_url(url: str) -> tuple[str, str]:
    h_blake2b = hashlib.blake2b()
    h_sha512 = hashlib.sha512()
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    h_blake2b.update(chunk)
                    h_sha512.update(chunk)
        return h_blake2b.hexdigest(), h_sha512.hexdigest()
    except (ReadTimeout, ConnectTimeout, requests.exceptions.HTTPError,
            requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema, requests.exceptions.ChunkedEncodingError) as e:
        logger.error(f'Error hashing URL {url}: {e}')

    return "", ""


@lru_cache
def get_last_modified(url: str) -> str:
    try:
        with requests.head(url, timeout=30) as r:
            r.raise_for_status()
            if last_modified := r.headers['last-modified']:
                dt = parsedate_to_datetime(last_modified)
                return dt.strftime("%Y%m%d")

    except (ReadTimeout, ConnectTimeout, requests.exceptions.HTTPError,
            requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema, requests.exceptions.ChunkedEncodingError) as e:
        logger.error(f'Error fetching last modified header for {url}: {e}')

    return ""
