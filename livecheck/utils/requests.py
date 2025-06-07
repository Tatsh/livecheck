"""Utilities for requests module."""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from functools import cache
from http import HTTPStatus
from urllib.parse import urlparse
import hashlib
import logging

import requests

from .credentials import get_api_credentials

log = logging.getLogger(__name__)


@dataclass
class TextDataResponse:
    """Used for data URI responses."""
    text: str
    """Text content."""
    status_code: int = HTTPStatus.OK
    """Defaults to 200 OK."""
    def raise_for_status(self) -> None:
        """Do nothing."""


@cache
def session_init(module: str) -> requests.Session:
    """Create a session."""
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
    """"Fetch content from a URL."""
    parsed_uri = urlparse(url)
    log.debug('Fetching %s', url)

    if parsed_uri.scheme == 'mirror':
        # If the URL is a mirror, we need to handle it differently
        # This is a placeholder for the actual implementation
        log.debug('Handling mirror:// protocol for `%s`.', url)
        response = requests.Response()
        response.status_code = HTTPStatus.NOT_IMPLEMENTED
        return response

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

    r: TextDataResponse | requests.Response
    try:
        r = session.get(url)
    except requests.RequestException:
        log.exception('Caught error attempting to fetch `%s`.', url)
        r = requests.Response()
        r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r
    if r.status_code not in {
            HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.ACCEPTED, HTTPStatus.PARTIAL_CONTENT,
            HTTPStatus.MOVED_PERMANENTLY, HTTPStatus.FOUND, HTTPStatus.TEMPORARY_REDIRECT,
            HTTPStatus.PERMANENT_REDIRECT
    }:
        log.error('Error fetching %s. Status code: %d', url, r.status_code)
    elif not r.text:
        log.warning('Empty response for %s.', url)

    return r


@cache
def hash_url(url: str) -> tuple[str, str, int]:
    """Hash the content of a URL using BLAKE2b and SHA-512."""
    h_blake2b = hashlib.blake2b()
    h_sha512 = hashlib.sha512()
    size = 0
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    h_blake2b.update(chunk)
                    h_sha512.update(chunk)
                    size += len(chunk)
        return h_blake2b.hexdigest(), h_sha512.hexdigest(), size
    except requests.RequestException:
        log.exception('Error hashing URL %s.', url)

    return '', '', 0


@cache
def get_last_modified(url: str) -> str:
    """Get the last modified date of a URL."""
    try:
        with requests.head(url, timeout=30) as r:
            r.raise_for_status()
            if last_modified := r.headers.get('last-modified'):
                return parsedate_to_datetime(last_modified).strftime('%Y%m%d')

    except requests.RequestException:
        log.exception('Error fetching last modified header for %s.', url)

    return ''
