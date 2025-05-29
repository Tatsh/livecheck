from __future__ import annotations

from typing import TYPE_CHECKING
import logging

from livecheck.utils.credentials import get_api_credentials

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture
    from pytest_mock import MockerFixture


def test_get_api_credentials_returns_token(mocker: MockerFixture) -> None:
    mocker.patch('keyring.get_password', return_value='secret-token')
    token = get_api_credentials('my-repo')
    assert token == 'secret-token'


def test_get_api_credentials_logs_warning_and_returns_none(mocker: MockerFixture,
                                                           caplog: LogCaptureFixture) -> None:
    mocker.patch('keyring.get_password', return_value=None)
    with caplog.at_level(logging.WARNING):
        token = get_api_credentials('my-repo2')
    assert token is None
    assert 'No my-repo2 API token found in your secret store.' in caplog.text
