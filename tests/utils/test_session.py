# ruff: noqa: EM101, RUF012, RUF069, SLF001
from __future__ import annotations

from http import HTTPStatus
from time import time
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock
import asyncio

from livecheck.utils.session import build_github_session, build_retry, build_session
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    import niquests


def test_build_retry_returns_retry_with_expected_status_codes() -> None:
    retry = build_retry()
    assert HTTPStatus.TOO_MANY_REQUESTS in retry.status_forcelist
    assert HTTPStatus.INTERNAL_SERVER_ERROR in retry.status_forcelist
    assert HTTPStatus.BAD_GATEWAY in retry.status_forcelist
    assert HTTPStatus.SERVICE_UNAVAILABLE in retry.status_forcelist
    assert HTTPStatus.GATEWAY_TIMEOUT in retry.status_forcelist
    assert HTTPStatus.FORBIDDEN not in retry.status_forcelist


def test_build_retry_backoff_factor() -> None:
    retry = build_retry()
    assert retry.backoff_factor == 2.5


def test_build_retry_total() -> None:
    retry = build_retry()
    assert retry.total == 3


def test_build_session_returns_concurrency_limited_session() -> None:
    sem = asyncio.Semaphore(1)
    session = build_session(sem)
    assert session._semaphore is sem


def test_build_github_session_returns_github_session() -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    assert session._semaphore is sem


@pytest.mark.asyncio
async def test_concurrency_limited_session_gates_on_semaphore(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_session(sem)
    mock_super_request = mocker.patch('niquests_cache.AsyncCachedSession.request',
                                      new_callable=AsyncMock,
                                      return_value=mocker.MagicMock(status_code=HTTPStatus.OK))
    result = await session.request('GET', 'https://example.com')
    assert result.status_code == HTTPStatus.OK
    mock_super_request.assert_called_once()


@pytest.mark.asyncio
async def test_github_session_returns_on_success(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    mock_response = mocker.MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=mock_response)
    result = await session.request('GET', 'https://api.github.com/repos/foo/bar')
    assert result.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_github_session_retries_on_429(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {'retry-after': '0'}
    rate_limited.text = ''
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[rate_limited, ok_response])
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_github_session_gives_up_after_max_retries(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {'retry-after': '0'}
    rate_limited.text = ''
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=rate_limited)
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_github_session_retries_on_rate_limit_403(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    forbidden = mocker.MagicMock()
    forbidden.status_code = HTTPStatus.FORBIDDEN
    forbidden.headers = {'x-ratelimit-remaining': '0'}
    forbidden.text = 'rate limit exceeded'
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[forbidden, ok_response])
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_github_session_parks_when_rate_limit_exhausted(mocker: MockerFixture) -> None:
    """A 200 with remaining=0 + a future reset should drive the park-sleep branch."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    future_reset = str(time() + 5)
    ok_exhausted = mocker.MagicMock()
    ok_exhausted.status_code = HTTPStatus.OK
    ok_exhausted.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': future_reset}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=ok_exhausted)
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] > 0


@pytest.mark.asyncio
async def test_github_session_does_not_park_when_reset_in_past(mocker: MockerFixture) -> None:
    """Past reset means delay <= 0, so no sleep happens."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    past_reset = str(time() - 100)
    ok_exhausted = mocker.MagicMock()
    ok_exhausted.status_code = HTTPStatus.OK
    ok_exhausted.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': past_reset}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=ok_exhausted)
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await session.request('GET', 'https://api.github.com/test')
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_github_session_does_not_park_on_invalid_reset(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    ok_exhausted = mocker.MagicMock()
    ok_exhausted.status_code = HTTPStatus.OK
    ok_exhausted.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': 'invalid'}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=ok_exhausted)
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await session.request('GET', 'https://api.github.com/test')
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_github_session_does_not_park_when_no_reset_header(mocker: MockerFixture) -> None:
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    ok_exhausted = mocker.MagicMock()
    ok_exhausted.status_code = HTTPStatus.OK
    ok_exhausted.headers = {'x-ratelimit-remaining': '0'}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 return_value=ok_exhausted)
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await session.request('GET', 'https://api.github.com/test')
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_github_session_uses_reset_window_when_retry_after_absent(
        mocker: MockerFixture) -> None:
    """429 with no retry-after but remaining=0 + reset → sleep for the reset window."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    future_reset = str(time() + 7)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': future_reset}
    rate_limited.text = ''
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[rate_limited, ok_response])
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK
    assert mock_sleep.call_args_list[0][0][0] > 0


@pytest.mark.asyncio
async def test_github_session_falls_back_to_backoff_on_invalid_reset(mocker: MockerFixture) -> None:
    """429 with non-numeric reset → explicit_wait returns None, backoff path used."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': 'not-a-number'}
    rate_limited.text = ''
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[rate_limited, ok_response])
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK
    assert mock_sleep.call_args_list[0][0][0] == 60.0


@pytest.mark.asyncio
async def test_github_session_falls_back_to_backoff_on_invalid_retry_after(
        mocker: MockerFixture) -> None:
    """429 with non-numeric retry-after → backoff (retry_after_seconds returns None)."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {'retry-after': 'not-a-number'}
    rate_limited.text = ''
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[rate_limited, ok_response])
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK
    assert mock_sleep.call_args_list[0][0][0] == 60.0


@pytest.mark.asyncio
async def test_github_session_backoff_when_no_rate_limit_headers(mocker: MockerFixture) -> None:
    """429 with no rate-limit headers at all → secondary backoff."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    rate_limited = mocker.MagicMock()
    rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
    rate_limited.headers = {}
    rate_limited.text = ''
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[rate_limited, ok_response])
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK
    assert mock_sleep.call_args_list[0][0][0] == 60.0


@pytest.mark.asyncio
async def test_github_session_does_not_retry_plain_403(mocker: MockerFixture) -> None:
    """403 with no rate-limit signals should not trigger a retry."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    forbidden = mocker.MagicMock()
    forbidden.status_code = HTTPStatus.FORBIDDEN
    forbidden.headers = {}
    forbidden.text = 'forbidden'
    mock_request = mocker.patch('niquests_cache.AsyncCachedSession.request',
                                new_callable=AsyncMock,
                                return_value=forbidden)
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.FORBIDDEN
    assert mock_request.call_count == 1


@pytest.mark.parametrize(
    'body',
    ['API rate limit exceeded', 'secondary rate limit triggered', 'abuse detection mechanism'])
@pytest.mark.asyncio
async def test_github_session_retries_on_403_body_hints(mocker: MockerFixture, body: str) -> None:
    """403 whose body contains a rate-limit hint should retry."""
    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    forbidden = mocker.MagicMock()
    forbidden.status_code = HTTPStatus.FORBIDDEN
    forbidden.headers = {'retry-after': '0'}
    forbidden.text = body
    ok_response = mocker.MagicMock()
    ok_response.status_code = HTTPStatus.OK
    ok_response.headers = {}
    mocker.patch('niquests_cache.AsyncCachedSession.request',
                 new_callable=AsyncMock,
                 side_effect=[forbidden, ok_response])
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_github_session_handles_response_with_unreadable_body(mocker: MockerFixture) -> None:
    """A 403 whose .text raises UnicodeDecodeError must be treated as not-rate-limited."""
    class _BadTextResponse:
        status_code = HTTPStatus.FORBIDDEN
        headers: dict[str, Any] = {}

        @property
        def text(self) -> str:
            msg = 'bad'
            raise UnicodeDecodeError('utf-8', b'', 0, 1, msg)

    sem = asyncio.Semaphore(1)
    session = build_github_session(sem)
    mock_request = mocker.patch('niquests_cache.AsyncCachedSession.request',
                                new_callable=AsyncMock,
                                return_value=cast('niquests.Response', _BadTextResponse()))
    mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    result = await session.request('GET', 'https://api.github.com/test')
    assert result.status_code == HTTPStatus.FORBIDDEN
    assert mock_request.call_count == 1
