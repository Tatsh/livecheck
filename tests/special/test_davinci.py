from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.davinci import get_latest_davinci_package
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_davinci_package_success(mocker: MockerFixture) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        'linux': {
            'releaseId': 'a6e2bbb59c294d728d131fa21d18676b',
            'downloadId': '407110f9045e410996bb9ff3ad6956d5',
            'major': 18,
            'minor': 5,
            'releaseNum': 1,
            'build': 49
        }
    }
    mock_get_content = mocker.patch('livecheck.special.davinci.get_content',
                                    return_value=mock_response)
    result = get_latest_davinci_package('davinci')
    assert result == '18.5.1'
    mock_response.json.return_value = {
        'linux': {
            'releaseId': 'a6e2bbb59c294d728d131fa21d18676b',
            'downloadId': '407110f9045e410996bb9ff3ad6956d5',
            'major': 20,
            'minor': 0,
            'releaseNum': 0,
            'build': 49
        }
    }
    mock_get_content = mocker.patch('livecheck.special.davinci.get_content',
                                    return_value=mock_response)
    result = get_latest_davinci_package('davinci')
    assert result == '20.0'

    mock_get_content.assert_called_once_with(
        'https://www.blackmagicdesign.com/api/support/latest-stable-version/davinci/linux')


def test_get_latest_davinci_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.davinci.get_content', return_value=None)
    result = get_latest_davinci_package('davinci')
    assert not result


def test_get_latest_davinci_package_missing_linux_key(mocker: MockerFixture) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {}
    mocker.patch('livecheck.special.davinci.get_content', return_value=mock_response)
    with pytest.raises(KeyError):
        get_latest_davinci_package('davinci')


def test_get_latest_davinci_package_partial_linux_data(mocker: MockerFixture) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        'linux': {
            'releaseId': 'a6e2bbb59c294d728d131fa21d18676b',
            'downloadId': '407110f9045e410996bb9ff3ad6956d5',
            'major': 18,
            'minor': 1,
            'build': 49
        }
    }
    mocker.patch('livecheck.special.davinci.get_content', return_value=mock_response)
    with pytest.raises(KeyError):
        get_latest_davinci_package('davinci')
