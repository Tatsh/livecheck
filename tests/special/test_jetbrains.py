from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.jetbrains import (
    get_latest_jetbrains_package,
    is_jetbrains,
    update_jetbrains_ebuild,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_get_latest_jetbrains_package_returns_latest(mocker: MockerFixture) -> None:
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

    result = get_latest_jetbrains_package('dev-util/pycharm-community', mock_settings)
    assert result == '2023.1'


def test_get_latest_jetbrains_package_no_content(mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'clion', None))
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=None)
    result = get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert not result


def test_get_latest_jetbrains_package_no_matching_product(mocker: MockerFixture) -> None:
    mock_settings = mocker.Mock()
    mock_settings.is_devel.return_value = False
    mocker.patch('livecheck.special.jetbrains.catpkg_catpkgsplit',
                 return_value=('dev-util', None, 'unknown-product', None))
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{'name': 'PyCharm Community Edition', 'releases': []}]
    mocker.patch('livecheck.special.jetbrains.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.jetbrains.get_last_version', return_value=None)
    result = get_latest_jetbrains_package('dev-util/unknown-product', mock_settings)
    assert not result


def test_get_latest_jetbrains_package_skips_eap_and_rc_if_not_devel(mocker: MockerFixture) -> None:
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
    result = get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert result == '2023.1'


def test_get_latest_jetbrains_package_includes_eap_and_rc_if_devel(mocker: MockerFixture) -> None:
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
    result = get_latest_jetbrains_package('dev-util/clion', mock_settings)
    assert result == '2023.3'


def test_update_jetbrains_ebuild_updates_my_pv_line(mocker: MockerFixture, tmp_path: Path) -> None:
    # Setup
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    fake_version = '2024.1'
    fake_package_path = f'/some/path/product-{fake_version}'
    # Patch search_ebuild to return a path containing the version
    mocker.patch('livecheck.special.jetbrains.search_ebuild',
                 return_value=(fake_package_path, None))
    # Patch EbuildTempFile context manager
    mock_temp_file = mocker.MagicMock()
    mock_temp_file.__enter__.return_value = mock_temp_file
    mock_temp_file.__exit__.return_value = None
    mocker.patch('livecheck.special.jetbrains.EbuildTempFile', return_value=mock_temp_file)
    # Patch open for both temp_file and Path(ebuild)
    mock_write = mocker.mock_open()
    mock_read = mocker.mock_open(read_data='MY_PV="old"\nSOME=other\n')
    mocker.patch('pathlib.Path.open', mock_read)
    mock_temp_file.open = mock_write
    # Run
    update_jetbrains_ebuild(str(ebuild_path))
    # Assert
    handle = mock_write()
    handle.write.assert_any_call(f'MY_PV="{fake_version}"\n')
    handle.write.assert_any_call('SOME=other\n')


def test_update_jetbrains_ebuild_no_version_found(mocker: MockerFixture, tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    mocker.patch('livecheck.special.jetbrains.search_ebuild', return_value=('', None))
    mock_logger = mocker.patch('livecheck.special.jetbrains.logger')
    mocker.patch('livecheck.special.jetbrains.EbuildTempFile')
    update_jetbrains_ebuild(str(ebuild_path))
    mock_logger.warning.assert_called_once_with('No version found in the tar.gz file.')


def test_update_jetbrains_ebuild_handles_no_my_pv_line(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'fake-ebuild.ebuild'
    fake_version = '2024.2'
    fake_package_path = f'/some/path/product-{fake_version}'
    mocker.patch('livecheck.special.jetbrains.search_ebuild',
                 return_value=(fake_package_path, None))
    mock_temp_file = mocker.MagicMock()
    mock_temp_file.__enter__.return_value = mock_temp_file
    mock_temp_file.__exit__.return_value = None
    mocker.patch('livecheck.special.jetbrains.EbuildTempFile', return_value=mock_temp_file)
    mock_write = mocker.mock_open()
    mock_read = mocker.mock_open(read_data='SOME=other\n')
    mocker.patch('pathlib.Path.open', mock_read)
    mock_temp_file.open = mock_write
    update_jetbrains_ebuild(str(ebuild_path))
    handle = mock_write()
    handle.write.assert_any_call('SOME=other\n')


def test_is_jetbrains_true_for_download_url(mocker: MockerFixture) -> None:
    url = 'https://download.jetbrains.com/python/pycharm-community-2023.1.tar.gz'
    assert is_jetbrains(url)
