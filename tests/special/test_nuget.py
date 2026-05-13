from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special import nuget
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_EXTRACT_CASES = [
    ('https://www.nuget.org/packages/Newtonsoft.Json/13.0.1', 'newtonsoft.json'),
    ('https://www.nuget.org/packages/Newtonsoft.Json', 'newtonsoft.json'),
    ('https://www.nuget.org/api/v2/package/Newtonsoft.Json/13.0.1', 'newtonsoft.json'),
    ('https://api.nuget.org/v3-flatcontainer/newtonsoft.json/index.json', 'newtonsoft.json'),
    ('https://api.nuget.org/v3-flatcontainer/newtonsoft.json/13.0.1/newtonsoft.json.13.0.1.nupkg',
     'newtonsoft.json'),
    ('https://api.nuget.org/v3-flatcontainer/newtonsoft.json', 'newtonsoft.json'),
    ('https://example.com/packages/Newtonsoft.Json/13.0.1', ''),
    ('', ''),
    ('https://www.nuget.org/', ''),
    ('https://www.nuget.org/profiles/somebody', ''),
]


@pytest.mark.parametrize(('url', 'expected'), _EXTRACT_CASES)
def test_extract_project(url: str, expected: str) -> None:
    assert nuget.extract_project(url) == expected


@pytest.mark.parametrize(('url', 'expected'), [
    ('https://www.nuget.org/packages/A.B/1.0.0', True),
    ('https://api.nuget.org/v3-flatcontainer/a.b/index.json', True),
    ('https://github.com/Tatsh/livecheck', False),
])
def test_is_nuget(url: str, expected: bool) -> None:  # noqa: FBT001
    assert nuget.is_nuget(url) is expected


@pytest.mark.asyncio
async def test_get_latest_nuget_package_returns_latest_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    response = mocker.Mock()
    response.json.return_value = {'versions': ['1.0.0', '1.1.0', '2.0.0-beta']}
    mocker.patch('livecheck.special.nuget.get_content', return_value=response)
    mocker.patch('livecheck.special.nuget.get_last_version', return_value={'version': '1.1.0'})
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=False))
    version, url = await nuget.get_latest_nuget_package(
        'https://www.nuget.org/packages/Newtonsoft.Json/1.0.0', 'cat/pkg-1.0.0', settings)
    assert version == '1.1.0'
    assert url.endswith('/newtonsoft.json/1.1.0/newtonsoft.json.1.1.0.nupkg')


@pytest.mark.asyncio
async def test_get_latest_nuget_package_returns_empty_when_not_nuget(mocker: MockerFixture) -> None:
    settings = mocker.Mock()
    version, url = await nuget.get_latest_nuget_package('https://github.com/Tatsh/livecheck',
                                                        'cat/pkg-1.0.0', settings)
    assert not version
    assert not url


@pytest.mark.asyncio
async def test_get_latest_nuget_package_returns_empty_on_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    mocker.patch('livecheck.special.nuget.get_content', return_value=None)
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=False))
    version, url = await nuget.get_latest_nuget_package(
        'https://www.nuget.org/packages/Newtonsoft.Json', 'cat/pkg-1.0.0', settings)
    assert not version
    assert not url


@pytest.mark.asyncio
async def test_get_latest_nuget_package_returns_empty_on_no_last_version(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    response = mocker.Mock()
    response.json.return_value = {'versions': ['1.0.0']}
    mocker.patch('livecheck.special.nuget.get_content', return_value=response)
    mocker.patch('livecheck.special.nuget.get_last_version', return_value=None)
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=False))
    version, url = await nuget.get_latest_nuget_package(
        'https://www.nuget.org/packages/Newtonsoft.Json', 'cat/pkg-1.0.0', settings)
    assert not version
    assert not url


@pytest.mark.asyncio
async def test_get_latest_nuget_package_filters_prereleases_when_not_devel(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    response = mocker.Mock()
    response.json.return_value = {'versions': ['1.0.0', '2.0.0-beta', '1.1.0-rc1']}
    mocker.patch('livecheck.special.nuget.get_content', return_value=response)
    captured: dict[str, object] = {}

    def fake_get_last(results: list[dict[str, str]], *args: object,
                      **kwargs: object) -> dict[str, str]:
        captured['results'] = results
        return {'version': '1.0.0'}

    mocker.patch('livecheck.special.nuget.get_last_version', side_effect=fake_get_last)
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=False))
    await nuget.get_latest_nuget_package('https://www.nuget.org/packages/Pkg', 'cat/pkg-1.0.0',
                                         settings)
    assert captured['results'] == [{'tag': '1.0.0'}]


@pytest.mark.asyncio
async def test_get_latest_nuget_package_includes_prereleases_when_devel(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    response = mocker.Mock()
    response.json.return_value = {'versions': ['1.0.0', '2.0.0-beta']}
    mocker.patch('livecheck.special.nuget.get_content', return_value=response)
    captured: dict[str, object] = {}

    def fake_get_last(results: list[dict[str, str]], *args: object,
                      **kwargs: object) -> dict[str, str]:
        captured['results'] = results
        return {'version': '2.0.0-beta'}

    mocker.patch('livecheck.special.nuget.get_last_version', side_effect=fake_get_last)
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=True))
    await nuget.get_latest_nuget_package('https://www.nuget.org/packages/Pkg', 'cat/pkg-1.0.0',
                                         settings)
    assert captured['results'] == [{'tag': '1.0.0'}, {'tag': '2.0.0-beta'}]


@pytest.mark.asyncio
async def test_get_latest_nuget_metadata_lowercases_and_returns_version(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nuget.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, 'pkg', None))
    response = mocker.Mock()
    response.json.return_value = {'versions': ['9.9.9']}
    captured_url = mocker.patch('livecheck.special.nuget.get_content', return_value=response)
    mocker.patch('livecheck.special.nuget.get_last_version', return_value={'version': '9.9.9'})
    settings = mocker.Mock(is_devel=mocker.Mock(return_value=False))
    version, _ = await nuget.get_latest_nuget_metadata('Newtonsoft.Json', 'cat/pkg-1.0.0', settings)
    assert version == '9.9.9'
    captured_url.assert_called_once_with(
        'https://api.nuget.org/v3-flatcontainer/newtonsoft.json/index.json')
