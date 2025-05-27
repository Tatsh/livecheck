"""String utility functions."""
from __future__ import annotations

from functools import cache
from typing import Literal
from urllib.parse import urlparse
import logging
import re

log = logging.getLogger(__name__)
# From parse-package-name
# https://github.com/egoist/parse-package-name/blob/main/src/index.ts
RE_SCOPED = r'^(@[^\/]+\/[^@\/]+)(?:@([^\/]+))?(\/.*)?$'
"""Regular expression for a Node.js scoped package name."""
RE_NON_SCOPED = r'^([^@\/]+)(?:@([^\/]+))?(\/.*)?$'
"""Regular expression for a Node.js non-scoped package name."""


@cache
def dotize(s: str) -> str:
    """Convert dashes and underscores in a string to full stops."""
    ret = s.replace('-', '.').replace('_', '.')
    log.debug('dotize(): %s -> %s', s, ret)
    return ret


@cache
def is_sha(url: str) -> Literal[40, 7, 0]:
    """
    Extract the last part of a URL and checks if it is a valid SHA-1 hash.

    Parameters
    ----------
    url : str
        The input URL string.

    Returns
    -------
    int
        Returns ``7`` if it's a short SHA, ``40`` if it's a full SHA, ``0`` otherwise.
    """
    last_part = urlparse(url).path.rsplit('/', 1)[-1] if '/' in url else url

    if re.match(r'^[0-9a-f]{40}', last_part):
        return 40
    if re.match(r'^[0-9a-f]{7}', last_part):
        return 7
    return 0


def extract_sha(text: str) -> str:
    """
    Extract the first valid SHA-1 hash (7 or 40 characters) found in the given string.

    Parameters
    ----------
    text : str
        The input string to search for a SHA-1 hash.

    Returns
    -------
    str | None
        The SHA-1 hash if found, otherwise empty string.
    """
    match = re.search(r'\b(?:[0-9a-f]{7}|[0-9a-f]{40})\b', text)

    return match.group(0) if match else ''


class InvalidPackageName(ValueError):
    """Raised when a package name is invalid."""
    def __init__(self, pkg: str) -> None:
        super().__init__(f'Invalid package name: {pkg}.')


def parse_npm_package_name(s: str) -> tuple[str, str | None, str | None]:
    """
    Parse a Node.js package name into its components.

    Parameters.
    ----------
    s : str
        The package name to parse.

    Returns
    -------
    tuple[str, str | None, str | None]
        A tuple containing the scope, name, and version of the package.

    Raises
    ------
    InvalidPackageName
        If the package name does not match the expected format.
    """
    if not (m := re.match(RE_SCOPED, s) or re.match(RE_NON_SCOPED, s)):
        raise InvalidPackageName(s)
    return m[1], m[2], m[3]


@cache
def prefix_v(s: str) -> str:
    """Prefix a version string with 'v'."""
    return f'v{s}'


@cache
def dash_to_underscore(s: str) -> str:
    """Convert dashes in a string to underscores."""
    return s.replace('-', '_')
