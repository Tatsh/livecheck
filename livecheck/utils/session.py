"""Session helpers for HTTP access with caching and concurrency control."""
from __future__ import annotations

__all__ = ('build_github_session', 'build_retry', 'build_session')

from http import HTTPStatus
from time import time
from typing import TYPE_CHECKING, Any
import asyncio
import logging

from niquests import RetryConfiguration as Retry
from niquests_cache import AsyncCachedSession
import platformdirs

if TYPE_CHECKING:
    import niquests

log = logging.getLogger(__name__)

_GITHUB_MAX_RATE_LIMIT_RETRIES = 5
_GITHUB_SECONDARY_BACKOFF_BASE = 60.0
_RATE_LIMIT_BODY_HINTS = ('rate limit', 'abuse detection', 'secondary rate')


def _cache_path() -> Any:
    return platformdirs.user_cache_path('livecheck', appauthor=False, ensure_exists=True) / 'http'


def build_retry() -> Retry:
    """
    Build a retry configuration for HTTP sessions.

    Returns
    -------
    Retry
        Retry policy for transient HTTP failures.
    """
    return Retry(backoff_factor=2.5,
                 status_forcelist=(HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS,
                                   HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.BAD_GATEWAY,
                                   HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.GATEWAY_TIMEOUT))


def _build_github_retry() -> Retry:
    return Retry(backoff_factor=2.5,
                 status_forcelist=(HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.BAD_GATEWAY,
                                   HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.GATEWAY_TIMEOUT))


class _ConcurrencyLimitedSession(AsyncCachedSession):
    """Cached async session whose requests are gated by a shared semaphore."""
    def __init__(self, *, semaphore: asyncio.Semaphore, **kwargs: Any) -> None:
        """
        Initialise the session.

        Parameters
        ----------
        semaphore : asyncio.Semaphore
            Shared semaphore bounding the total number of in-flight requests.
        **kwargs : Any
            Forwarded to :py:class:`~niquests_cache.AsyncCachedSession`.
        """
        self._semaphore = semaphore
        super().__init__(**kwargs)

    async def request(  # type: ignore[override]
            self, method: str, url: str, *args: Any, **kwargs: Any) -> niquests.Response:
        """
        Send a request while respecting the shared concurrency limit.

        Parameters
        ----------
        method : str
            HTTP method.
        url : str
            Request URL.
        *args : Any
            Forwarded to the underlying session.
        **kwargs : Any
            Forwarded to the underlying session.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        async with self._semaphore:
            return await super().request(method, url, *args, **kwargs)


class _GitHubSession(_ConcurrencyLimitedSession):
    """Concurrency-limited session that honours GitHub REST API rate-limit conventions."""
    async def request(  # type: ignore[override]
            self, method: str, url: str, *args: Any, **kwargs: Any) -> niquests.Response:
        """
        Send a request, retrying on rate-limit responses per GitHub's documented policy.

        Parameters
        ----------
        method : str
            HTTP method.
        url : str
            Request URL.
        *args : Any
            Forwarded to the underlying session.
        **kwargs : Any
            Forwarded to the underlying session.

        Returns
        -------
        niquests.Response
            The response after any rate-limit-driven retries.
        """
        async with self._semaphore:
            response: niquests.Response
            for attempt in range(_GITHUB_MAX_RATE_LIMIT_RETRIES + 1):
                response = await AsyncCachedSession.request(self, method, url, *args, **kwargs)
                sleep_for = self._rate_limit_sleep(response, attempt)
                if sleep_for is None:
                    await self._park_if_depleted(response)
                    return response
                if attempt == _GITHUB_MAX_RATE_LIMIT_RETRIES:
                    log.warning('GitHub rate limit: giving up after %d retries for %s %s.',
                                _GITHUB_MAX_RATE_LIMIT_RETRIES, method, url)
                    return response
                log.warning('GitHub rate limit hit for %s %s; sleeping %.1fs (attempt %d/%d).',
                            method, url, sleep_for, attempt + 1, _GITHUB_MAX_RATE_LIMIT_RETRIES)
                await asyncio.sleep(sleep_for)
            return response  # pragma: no cover

    @classmethod
    def _rate_limit_sleep(cls, response: niquests.Response, attempt: int) -> float | None:
        """
        Compute how long to wait before retrying, per GitHub's rate-limit guidance.

        Parameters
        ----------
        response : niquests.Response
            The response to classify.
        attempt : int
            Zero-based retry attempt for exponential backoff.

        Returns
        -------
        float | None
            Seconds to sleep, or ``None`` if no retry is warranted.
        """
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            return cls._explicit_wait(response) or cls._secondary_backoff(attempt)
        if response.status_code == HTTPStatus.FORBIDDEN and cls._is_rate_limit_403(response):
            return cls._explicit_wait(response) or cls._secondary_backoff(attempt)
        return None

    @classmethod
    def _explicit_wait(cls, response: niquests.Response) -> float | None:
        retry_after = cls._retry_after_seconds(response)
        if retry_after is not None:
            return max(retry_after, 0.0)
        if response.headers.get('x-ratelimit-remaining') == '0':
            reset = response.headers.get('x-ratelimit-reset')
            if reset is not None:
                try:
                    return max(0.0, float(reset) - time())
                except ValueError:
                    return None
        return None

    @staticmethod
    def _secondary_backoff(attempt: int) -> float:
        return float(_GITHUB_SECONDARY_BACKOFF_BASE * (2 ** attempt))

    @classmethod
    def _is_rate_limit_403(cls, response: niquests.Response) -> bool:
        if response.headers.get('retry-after') is not None:
            return True
        if response.headers.get('x-ratelimit-remaining') == '0':
            return True
        try:
            body = (response.text or '').lower()
        except (UnicodeDecodeError, AttributeError):
            return False
        return any(hint in body for hint in _RATE_LIMIT_BODY_HINTS)

    @staticmethod
    async def _park_if_depleted(response: niquests.Response) -> None:
        remaining = response.headers.get('x-ratelimit-remaining')
        reset = response.headers.get('x-ratelimit-reset')
        if remaining != '0' or reset is None:
            return
        try:
            delay = max(0.0, float(reset) - time())
        except ValueError:
            return
        if delay > 0:
            log.info('GitHub rate limit exhausted; parking %.1fs until reset.', delay)
            await asyncio.sleep(delay)

    @staticmethod
    def _retry_after_seconds(response: niquests.Response) -> float | None:
        value = response.headers.get('retry-after')
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None


def build_session(semaphore: asyncio.Semaphore) -> _ConcurrencyLimitedSession:
    """
    Build a cached async session with concurrency limiting.

    Parameters
    ----------
    semaphore : asyncio.Semaphore
        Shared semaphore bounding concurrent in-flight requests.

    Returns
    -------
    _ConcurrencyLimitedSession
        An async session backed by a SQLite cache with HTTP cache-control honoured.
    """
    return _ConcurrencyLimitedSession(cache_name=_cache_path(),
                                      backend='sqlite',
                                      cache_control=True,
                                      retries=build_retry(),
                                      semaphore=semaphore)


def build_github_session(semaphore: asyncio.Semaphore) -> _GitHubSession:
    """
    Build a GitHub-aware cached async session.

    The session uses ``always_revalidate=True`` so every request is validated server-side;
    ``304`` responses do not count against GitHub's primary rate limit.

    Parameters
    ----------
    semaphore : asyncio.Semaphore
        Shared semaphore bounding concurrent in-flight requests.

    Returns
    -------
    _GitHubSession
        An async session that honours GitHub's REST API rate-limit headers.
    """
    return _GitHubSession(cache_name=_cache_path(),
                          backend='sqlite',
                          cache_control=True,
                          always_revalidate=True,
                          retries=_build_github_retry(),
                          semaphore=semaphore)
