from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from livecheck.special.jetbrains import (
    get_latest_jetbrains_package,
    is_jetbrains,
    update_jetbrains_ebuild,
)
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_get_latest_jetbrains_package_returns_latest(mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mock_settings.is_devel.return_value = False

    # Mock catpkg_catpkgsplit to return expected values
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'pycharm-community', None))

    # Mock get_content to return a mock response with .json()
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{
        'name':
            'PyCharm Community Edition',
        'releases': [
            {
                'type': 'release',
                'version': '2023.1',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'eap',
                'version': '2023.2',
                'downloads': {
                    'linux': {}
                }
            },
        ]
    }]
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=mock_response)

    # Mock get_last_version to return the latest version dict
    mocker.patch('livecheck.special.jetbrains.get_last_version', return_value={'tag': '2023.1'})

    result = await get_latest_jetbrains_package('dev-util/pycharm-community', mock_settings)
    assert result == '2023.1'


@pytest.mark.asyncio
async def test_get_latest_jetbrains_package_no_content(mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'clion', None))
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=None)
    result = await get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert not result


@pytest.mark.asyncio
async def test_get_latest_jetbrains_package_no_matching_product(mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mock_settings.is_devel.return_value = False
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'unknown-product', None))
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{'name': 'PyCharm Community Edition', 'releases': []}]
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.jetbrains.get_last_version', return_value=None)
    result = await get_latest_jetbrains_package('dev-util/unknown-product', mock_settings)
    assert not result


@pytest.mark.asyncio
async def test_get_latest_jetbrains_package_skips_eap_and_rc_if_not_devel(
        mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mock_settings.is_devel.return_value = False
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'clion', None))
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{
        'name':
            'CLion',
        'releases': [
            {
                'type': 'eap',
                'version': '2023.2',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'rc',
                'version': '2023.3',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'release',
                'version': '2023.1',
                'downloads': {
                    'linux': {}
                }
            },
        ]
    }]
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.jetbrains.get_last_version', return_value={'tag': '2023.1'})
    result = await get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert result == '2023.1'


@pytest.mark.asyncio
async def test_get_latest_jetbrains_package_includes_eap_and_rc_if_devel(
        mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mock_settings.is_devel.return_value = True
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'clion', None))
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{
        'name':
            'CLion',
        'releases': [
            {
                'type': 'eap',
                'version': '2023.2',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'rc',
                'version': '2023.3',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'release',
                'version': '2023.1',
                'downloads': {
                    'linux': {}
                }
            },
            {
                'type': 'release',
                'version': '2023.1',
                'downloads': {
                    'mac': {}
                }
            },
        ]
    }]
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.jetbrains.get_last_version', return_value={'tag': '2023.3'})
    result = await get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert result == '2023.3'


def _patch_jetbrains_temp_file(mocker: MockerFixture, ebuild_path: Path,
                               initial: str) -> dict[str, str]:
    ebuild_path.write_text(initial, encoding='utf-8')
    written: dict[str, str] = {}

    class _FakeTempFile:
        def __init__(self, _ebuild: str) -> None:
            self._path = ebuild_path

        async def __aenter__(self) -> Path:
            return self._path

        async def __aexit__(self, *_: object) -> None:
            written['text'] = await AnyioPath(ebuild_path).read_text(encoding='utf-8')

    mocker.patch('livecheck.special.jetbrains.EbuildTempFile', _FakeTempFile)
    return written


async def test_update_jetbrains_ebuild_updates_my_pv_line(mocker: MockerFixture,
                                                          tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    fake_version = '2024.1'
    fake_package_path = f'/some/path/product-{fake_version}'
    mocker.patch('livecheck.special.jetbrains.search_ebuild',
                 return_value=(fake_package_path, None))
    written = _patch_jetbrains_temp_file(mocker, ebuild_path, 'MY_PV="old"\nSOME=other\n')
    await update_jetbrains_ebuild(str(ebuild_path))
    assert f'MY_PV="{fake_version}"\n' in written['text']
    assert 'SOME=other\n' in written['text']


async def test_update_jetbrains_ebuild_no_version_found(mocker: MockerFixture,
                                                        tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    mocker.patch('livecheck.special.jetbrains.search_ebuild', return_value=('', None))
    mock_logger = mocker.patch('livecheck.special.jetbrains.logger')
    mocker.patch('livecheck.special.jetbrains.EbuildTempFile')
    await update_jetbrains_ebuild(str(ebuild_path))
    mock_logger.warning.assert_called_once_with('No version found in the tar.gz file.')


async def test_update_jetbrains_ebuild_handles_no_my_pv_line(mocker: MockerFixture,
                                                             tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    fake_version = '2024.2'
    fake_package_path = f'/some/path/product-{fake_version}'
    mocker.patch('livecheck.special.jetbrains.search_ebuild',
                 return_value=(fake_package_path, None))
    written = _patch_jetbrains_temp_file(mocker, ebuild_path, 'SOME=other\n')
    await update_jetbrains_ebuild(str(ebuild_path))
    assert 'SOME=other\n' in written['text']


def test_is_jetbrains_true_for_download_url(mocker: MockerFixture) -> None:
    url = 'https://download.jetbrains.com/python/pycharm-community-2023.1.tar.gz'
    assert is_jetbrains(url)
