"""Configuration for Pytest."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn
import asyncio
import contextlib
import os

from click.testing import CliRunner
from livecheck.utils.requests import close_sessions, init_sessions
from niquests_cache.session import CacheMixin
from niquests_mock import MockRouter
from niquests_mock.router import build_response
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from niquests import Response
    from niquests.models import PreparedRequest

if os.getenv('_PYTEST_RAISE', '0') != '0':  # pragma no cover

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[None]) -> NoReturn:
        assert call.excinfo is not None
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[BaseException]) -> NoReturn:
        raise excinfo.value


class NiquestsMocker:
    """Thin ``requests_mock``-style shim backed by :py:class:`~niquests_mock.MockRouter`."""
    def __init__(self, router: MockRouter) -> None:
        """
        Initialise the mocker.

        Parameters
        ----------
        router : MockRouter
            The underlying niquests-mock router.
        """
        self._router = router

    def _register(self, method: str, url: Any, args: tuple[Any, ...], kwargs: dict[str,
                                                                                   Any]) -> None:
        if args and isinstance(args[0], list):
            specs = args[0]
            route = self._router.request(method, url=url)
            idx = 0

            def side_effect(request: PreparedRequest) -> Response:
                nonlocal idx
                spec = specs[min(idx, len(specs) - 1)]
                idx += 1
                return build_response(request, **spec)

            route.mock(side_effect=side_effect)
            return
        route = self._router.request(method, url=url)
        route.respond(**kwargs)

    def get(self, url: Any, *args: Any, **kwargs: Any) -> None:
        """Register a ``GET`` mock response."""
        self._register('GET', url, args, kwargs)

    def head(self, url: Any, *args: Any, **kwargs: Any) -> None:
        """Register a ``HEAD`` mock response."""
        self._register('HEAD', url, args, kwargs)

    def post(self, url: Any, *args: Any, **kwargs: Any) -> None:
        """Register a ``POST`` mock response."""
        self._register('POST', url, args, kwargs)


@pytest.fixture
def requests_mock(monkeypatch: pytest.MonkeyPatch) -> Iterator[NiquestsMocker]:
    """
    Install a niquests-mock router and expose a requests_mock-style API.

    Caching is disabled so mock responses are never stored or replayed by
    :py:class:`~niquests_cache.AsyncCachedSession`.

    Yields
    ------
    NiquestsMocker
        A mock adapter wrapping the router.
    """
    orig_init = CacheMixin.__init__

    def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        orig_init(self, *args, **kwargs)
        self.settings.disabled = True

    monkeypatch.setattr(CacheMixin, '__init__', _patched_init)
    with MockRouter(assert_all_mocked=False, assert_all_called=False) as router:
        yield NiquestsMocker(router)


@pytest.fixture(autouse=True)
def _init_test_sessions() -> Iterator[None]:
    """Bootstrap the session infrastructure for every test."""
    init_sessions(asyncio.Semaphore(1))
    yield
    with contextlib.suppress(RuntimeError):
        asyncio.run(close_sessions())


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
