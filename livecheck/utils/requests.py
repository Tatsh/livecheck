"""Utilities for requests module."""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import hashlib
import logging

import niquests

from .credentials import get_api_credentials
from .session import build_github_session, build_session

if TYPE_CHECKING:
    import asyncio

__all__ = ('TextDataResponse', 'close_sessions', 'get_content', 'get_last_modified', 'hash_url',
           'init_sessions', 'session_init')

log = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
_sessions: dict[str, niquests.AsyncSession] = {}


def init_sessions(semaphore: asyncio.Semaphore) -> None:
    """
    Initialise the module-level HTTP semaphore and clear the session cache.

    Must be called once at the start of the async entry point before any HTTP requests.

    Parameters
    ----------
    semaphore : asyncio.Semaphore
        Shared semaphore bounding concurrent in-flight HTTP requests.
    """
    global _semaphore  # noqa: PLW0603
    _semaphore = semaphore
    _sessions.clear()


async def close_sessions() -> None:
    """Close all cached HTTP sessions."""
    for session in _sessions.values():
        await session.close()
    _sessions.clear()


@dataclass
class TextDataResponse:
    """Used for data URI responses."""
    text: str
    """Text content."""
    status_code: int = HTTPStatus.OK
    """Defaults to 200 OK."""
    def raise_for_status(self) -> None:
        """Do nothing."""


def session_init(module: str) -> niquests.AsyncSession:
    """
    Get or create a cached HTTP session for the given module.

    Parameters
    ----------
    module : str
        Module name determining default headers and authentication (for example ``github``).

    Returns
    -------
    niquests.AsyncSession
        Configured HTTP session with caching and concurrency limiting.

    Raises
    ------
    RuntimeError
        If :py:func:`init_sessions` has not been called.
    """
    if module in _sessions:
        return _sessions[module]
    if _semaphore is None:
        msg = 'Call init_sessions() before making HTTP requests.'
        raise RuntimeError(msg)
    session: niquests.AsyncSession
    session = build_github_session(_semaphore) if module == 'github' else build_session(_semaphore)
    match module:
        case 'github':
            token = get_api_credentials('github.com')
            if token:
                session.headers['Authorization'] = f'Bearer {token}'
            session.headers['Accept'] = 'application/vnd.github.v3+json'
        case 'xml':
            session.headers['Accept'] = 'application/xml'
        case 'json':
            session.headers['Accept'] = 'application/json'
        case 'gitlab':
            token = get_api_credentials('gitlab.com')
            if token:
                session.headers['Authorization'] = f'Bearer {token}'
            session.headers['Accept'] = 'application/json'
        case 'bitbucket':
            token = get_api_credentials('bitbucket.org')
            if token:
                session.headers['Authorization'] = f'Bearer {token}'
            session.headers['Accept'] = 'application/json'
    session.headers['timeout'] = '30'
    _sessions[module] = session
    return session


async def get_content(url: str,
                      headers: dict[str, str] | None = None,
                      params: dict[str, str] | None = None,
                      method: str = 'GET',
                      data: dict[str, str] | None = None,
                      *,
                      allow_redirects: bool = True) -> niquests.Response:
    """
    Fetch content from a URL.

    Parameters
    ----------
    url : str
        URL to request.
    headers : dict[str, str] | None
        Optional extra HTTP headers.
    params : dict[str, str] | None
        Optional query string parameters.
    method : str
        HTTP method name (for example ``GET``).
    data : dict[str, str] | None
        Optional form body for the request.
    allow_redirects : bool
        Whether to follow redirects.

    Returns
    -------
    niquests.Response
        Response object, or a synthetic response on failure or unimplemented schemes.
    """
    parsed_uri = urlparse(url)
    log.debug('Fetching %s', url)

    if parsed_uri.scheme == 'mirror':
        log.debug('Handling mirror:// protocol for `%s`.', url)
        response = niquests.Response()
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

    if headers:
        for key, value in headers.items():
            session.headers[key] = value

    r: TextDataResponse | niquests.Response
    try:
        req = niquests.Request(method=method.upper(), url=url, data=data, params=params)
        prepared = session.prepare_request(req)
        r = await session.send(prepared, allow_redirects=allow_redirects)
    except niquests.RequestException:
        log.exception('Caught error attempting to fetch `%s`.', url)
        r = niquests.Response()
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


async def hash_url(url: str,
                   headers: dict[str, str] | None = None,
                   params: dict[str, str] | None = None) -> tuple[str, str, int]:
    """
    Hash the content of a URL using BLAKE2b and SHA-512.

    Parameters
    ----------
    url : str
        URL whose body will be hashed.
    headers : dict[str, str] | None
        Optional HTTP headers for the GET request.
    params : dict[str, str] | None
        Optional query string parameters.

    Returns
    -------
    tuple[str, str, int]
        BLAKE2b hex digest, SHA-512 hex digest, and byte length; or two empty strings and ``0`` on
        failure.
    """
    h_blake2b = hashlib.blake2b()
    h_sha512 = hashlib.sha512()
    size = 0
    try:
        session = session_init('')
        r = await session.get(url, headers=headers, params=params, stream=True, timeout=30)
        r.raise_for_status()
        async for chunk in await r.iter_content(chunk_size=8192):
            if chunk:
                h_blake2b.update(chunk)
                h_sha512.update(chunk)
                size += len(chunk)
        return h_blake2b.hexdigest(), h_sha512.hexdigest(), size
    except niquests.RequestException:
        log.exception('Error hashing URL %s.', url)

    return '', '', 0


async def get_last_modified(url: str,
                            headers: dict[str, str] | None = None,
                            params: dict[str, str] | None = None) -> str:
    """
    Get the last modified date of a URL.

    Parameters
    ----------
    url : str
        URL to request with ``HEAD``.
    headers : dict[str, str] | None
        Optional HTTP headers.
    params : dict[str, str] | None
        Optional query string parameters.

    Returns
    -------
    str
        ``Last-Modified`` as ``YYYYMMDD``, or an empty string if unavailable or on error.
    """
    try:
        session = session_init('')
        r = await session.head(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        if last_modified := str(r.headers.get('last-modified', '')):
            return parsedate_to_datetime(last_modified).strftime('%Y%m%d')

    except niquests.RequestException:
        log.exception('Error fetching last modified header for %s.', url)

    return ''
