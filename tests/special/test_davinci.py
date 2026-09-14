from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from niquests_mock import MockRouter
import pytest

from livecheck.special.davinci import get_latest_davinci_package

pytestmark = pytest.mark.asyncio

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


async def test_get_latest_davinci_package_success(mocker: MockerFixture) -> None:
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
    result = await get_latest_davinci_package('davinci')
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
    result = await get_latest_davinci_package('davinci')
    assert result == '20.0'

    mock_get_content.assert_called_once_with(
        'https://www.blackmagicdesign.com/api/support/latest-stable-version/davinci/linux')


async def test_get_latest_davinci_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.davinci.get_content', return_value=None)
    result = await get_latest_davinci_package('davinci')
    assert not result


@pytest.mark.parametrize(('status_code', 'expected'), [(HTTPStatus.OK, '21.1'),
                                                       (HTTPStatus.NOT_MODIFIED, '21.0.4')])
async def test_get_latest_davinci_package_revalidates_cache(mocker: MockerFixture, tmp_path: Path,
                                                            status_code: HTTPStatus,
                                                            expected: str) -> None:
    mocker.patch('livecheck.utils.session.platformdirs.user_cache_path', return_value=tmp_path)
    url = ('https://www.blackmagicdesign.com/api/support/latest-stable-version/'
           'davinci-resolve-studio/linux')
    with MockRouter() as router:
        route = router.get(url).respond(headers={
            'Cache-Control': 'public, max-age=14400',
            'ETag': '"previous"'
        },
                                        json={'linux': {
                                            'major': 21,
                                            'minor': 0,
                                            'releaseNum': 4
                                        }})
        assert await get_latest_davinci_package('davinci-resolve-studio') == '21.0.4'

        route.respond(json={'linux': {
            'major': 21,
            'minor': 1,
            'releaseNum': 0
        }},
                      status_code=status_code)
        assert await get_latest_davinci_package('davinci-resolve-studio') == expected
        assert route.call_count == 2
        headers = route.calls[-1].request.headers
        assert headers is not None
        assert headers['If-None-Match'] == '"previous"'


async def test_get_latest_davinci_package_missing_linux_key(mocker: MockerFixture) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {}
    mocker.patch('livecheck.special.davinci.get_content', return_value=mock_response)
    with pytest.raises(KeyError):
        await get_latest_davinci_package('davinci')


async def test_get_latest_davinci_package_partial_linux_data(mocker: MockerFixture) -> None:
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
        await get_latest_davinci_package('davinci')
