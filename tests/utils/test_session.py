# ruff: noqa: EM101, PLC2701, RUF012, RUF069, SLF001
from __future__ import annotations

from http import HTTPStatus
from time import time
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock
import asyncio

from livecheck.utils.session import (
    build_github_session,
    build_retry,
    build_session,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    import niquests


def _fake_response(**attrs: Any) -> niquests.Response:
    return cast('niquests.Response', type('R', (), attrs)())


def test_build_retry_returns_retry_with_expected_status_codes() -> None:
    retry = build_retry()
    assert HTTPStatus.FORBIDDEN in retry.status_forcelist
    assert HTTPStatus.TOO_MANY_REQUESTS in retry.status_forcelist
    assert HTTPStatus.INTERNAL_SERVER_ERROR in retry.status_forcelist
    assert HTTPStatus.BAD_GATEWAY in retry.status_forcelist
    assert HTTPStatus.SERVICE_UNAVAILABLE in retry.status_forcelist
    assert HTTPStatus.GATEWAY_TIMEOUT in retry.status_forcelist


def test_build_retry_backoff_factor() -> None:
    retry = build_retry()
    assert retry.backoff_factor == 2.5


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


def test_rate_limit_sleep_returns_none_for_ok() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.OK, headers={}, text='')
    assert _GitHubSession._rate_limit_sleep(response, 0) is None


def test_rate_limit_sleep_returns_float_for_429_with_retry_after() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.TOO_MANY_REQUESTS,
                              headers={'retry-after': '5'},
                              text='')
    result = _GitHubSession._rate_limit_sleep(response, 0)
    assert result == 5.0


def test_rate_limit_sleep_returns_backoff_for_429_no_retry_after() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.TOO_MANY_REQUESTS, headers={}, text='')
    result = _GitHubSession._rate_limit_sleep(response, 0)
    assert result == 60.0


def test_rate_limit_sleep_returns_float_for_403_with_retry_after() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={'retry-after': '10'},
                              text='')
    result = _GitHubSession._rate_limit_sleep(response, 0)
    assert result == 10.0


def test_rate_limit_sleep_returns_none_for_non_rate_limit_403() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN, headers={}, text='not found')
    assert _GitHubSession._rate_limit_sleep(response, 0) is None


def test_explicit_wait_returns_retry_after() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={'retry-after': '3'})
    assert _GitHubSession._explicit_wait(response) == 3.0


def test_explicit_wait_returns_zero_for_negative_retry_after() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={'retry-after': '-5'})
    assert _GitHubSession._explicit_wait(response) == 0.0


def test_explicit_wait_uses_ratelimit_reset_when_remaining_zero() -> None:
    from livecheck.utils.session import _GitHubSession
    future_time = str(time() + 10)
    response = _fake_response(headers={
        'x-ratelimit-remaining': '0',
        'x-ratelimit-reset': future_time
    })
    result = _GitHubSession._explicit_wait(response)
    assert result is not None
    assert result >= 0.0


def test_explicit_wait_returns_none_for_invalid_reset() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={
        'x-ratelimit-remaining': '0',
        'x-ratelimit-reset': 'not-a-number'
    })
    assert _GitHubSession._explicit_wait(response) is None


def test_explicit_wait_returns_none_when_no_headers() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={})
    assert _GitHubSession._explicit_wait(response) is None


def test_explicit_wait_returns_none_when_remaining_nonzero() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={'x-ratelimit-remaining': '50'})
    assert _GitHubSession._explicit_wait(response) is None


def test_secondary_backoff_attempt_0() -> None:
    from livecheck.utils.session import _GitHubSession
    assert _GitHubSession._secondary_backoff(0) == 60.0


def test_secondary_backoff_attempt_2() -> None:
    from livecheck.utils.session import _GitHubSession
    assert _GitHubSession._secondary_backoff(2) == 240.0


def test_is_rate_limit_403_with_retry_after_header() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={'retry-after': '10'},
                              text='')
    assert _GitHubSession._is_rate_limit_403(response) is True


def test_is_rate_limit_403_with_remaining_zero() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={'x-ratelimit-remaining': '0'},
                              text='')
    assert _GitHubSession._is_rate_limit_403(response) is True


def test_is_rate_limit_403_with_body_hint() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={},
                              text='API rate limit exceeded')
    assert _GitHubSession._is_rate_limit_403(response) is True


def test_is_rate_limit_403_with_secondary_rate_hint() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={},
                              text='secondary rate limit triggered')
    assert _GitHubSession._is_rate_limit_403(response) is True


def test_is_rate_limit_403_with_abuse_detection_hint() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN,
                              headers={},
                              text='abuse detection mechanism')
    assert _GitHubSession._is_rate_limit_403(response) is True


def test_is_rate_limit_403_returns_false_for_regular_403() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(status_code=HTTPStatus.FORBIDDEN, headers={}, text='forbidden')
    assert _GitHubSession._is_rate_limit_403(response) is False


def test_is_rate_limit_403_handles_unicode_decode_error() -> None:
    from livecheck.utils.session import _GitHubSession

    class BadTextResponse:
        status_code = HTTPStatus.FORBIDDEN
        headers: dict[str, Any] = {}

        @property
        def text(self) -> str:
            raise UnicodeDecodeError('utf-8', b'', 0, 1, 'bad')

    assert _GitHubSession._is_rate_limit_403(cast('niquests.Response', BadTextResponse())) is False


@pytest.mark.asyncio
async def test_park_if_depleted_sleeps_when_exhausted(mocker: MockerFixture) -> None:
    from livecheck.utils.session import _GitHubSession
    future_reset = str(time() + 5)
    response = mocker.MagicMock()
    response.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': future_reset}
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await _GitHubSession._park_if_depleted(response)
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] > 0


@pytest.mark.asyncio
async def test_park_if_depleted_returns_when_remaining_nonzero(mocker: MockerFixture) -> None:
    from livecheck.utils.session import _GitHubSession
    response = mocker.MagicMock()
    response.headers = {'x-ratelimit-remaining': '50'}
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await _GitHubSession._park_if_depleted(response)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_park_if_depleted_returns_when_no_reset_header(mocker: MockerFixture) -> None:
    from livecheck.utils.session import _GitHubSession
    response = mocker.MagicMock()
    response.headers = {'x-ratelimit-remaining': '0'}
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await _GitHubSession._park_if_depleted(response)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_park_if_depleted_returns_on_invalid_reset(mocker: MockerFixture) -> None:
    from livecheck.utils.session import _GitHubSession
    response = mocker.MagicMock()
    response.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': 'invalid'}
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await _GitHubSession._park_if_depleted(response)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_park_if_depleted_skips_sleep_when_delay_zero(mocker: MockerFixture) -> None:
    from livecheck.utils.session import _GitHubSession
    past_reset = str(time() - 100)
    response = mocker.MagicMock()
    response.headers = {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': past_reset}
    mock_sleep = mocker.patch('livecheck.utils.session.asyncio.sleep', new_callable=AsyncMock)
    await _GitHubSession._park_if_depleted(response)
    mock_sleep.assert_not_called()


def test_retry_after_seconds_returns_float() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={'retry-after': '42'})
    assert _GitHubSession._retry_after_seconds(response) == 42.0


def test_retry_after_seconds_returns_none_when_missing() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={})
    assert _GitHubSession._retry_after_seconds(response) is None


def test_retry_after_seconds_returns_none_for_invalid_value() -> None:
    from livecheck.utils.session import _GitHubSession
    response = _fake_response(headers={'retry-after': 'not-a-number'})
    assert _GitHubSession._retry_after_seconds(response) is None
