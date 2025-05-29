from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.special import repology
import pytest

if TYPE_CHECKING:
    from unittest.mock import Mock

    from pytest_mock import MockerFixture


@pytest.fixture
def mock_settings(mocker: MockerFixture) -> Any:
    settings = mocker.Mock()
    settings.is_devel.return_value = False
    return settings


@pytest.fixture
def mock_catpkg_catpkgsplit(mocker: MockerFixture) -> Any:
    return mocker.patch('livecheck.special.repology.catpkg_catpkgsplit',
                        return_value=('cat/pkg', None, 'pkg', None))


@pytest.fixture
def mock_get_last_version(mocker: MockerFixture) -> Any:
    return mocker.patch('livecheck.special.repology.get_last_version')


def test_get_latest_repology_success(mock_catpkg_catpkgsplit: Mock, mocker: MockerFixture,
                                     mock_get_last_version: Mock, mock_settings: Mock) -> None:
    # Mock the response from get_content
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'srcname': 'pkg',
            'status': 'stable',
            'version': '1.2.3'
        },
        {
            'srcname': 'pkg',
            'status': 'devel',
            'version': '2.0.0'
        },
        {
            'srcname': 'other',
            'status': 'stable',
            'version': '9.9.9'
        },
    ]
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = {'version': '1.2.3'}

    result = repology.get_latest_repology('cat/pkg', mock_settings)
    assert result == '1.2.3'
    mock_get_content.assert_called_once()
    mock_get_last_version.assert_called_once()


def test_get_latest_repology_with_package_param(mock_catpkg_catpkgsplit: Mock,
                                                mocker: MockerFixture, mock_get_last_version: Mock,
                                                mock_settings: Mock) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'srcname': 'custom-pkg',
            'status': 'stable',
            'version': '4.5.6'
        },
    ]
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = {'version': '4.5.6'}

    result = repology.get_latest_repology('cat/pkg', mock_settings, package='custom-pkg')
    assert result == '4.5.6'
    mock_get_content.assert_called_once()
    mock_get_last_version.assert_called_once()


def test_get_latest_repology_fallback_url(mock_catpkg_catpkgsplit: Mock, mocker: MockerFixture,
                                          mock_get_last_version: Mock, mock_settings: Mock) -> None:
    # First call returns None, second call returns a valid response
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'srcname': 'pkg',
            'status': 'stable',
            'version': '7.8.9'
        },
    ]
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.side_effect = [None, mock_response]
    mock_get_last_version.return_value = {'version': '7.8.9'}

    result = repology.get_latest_repology('cat/pkg', mock_settings)
    assert result == '7.8.9'
    assert mock_get_content.call_count == 2
    mock_get_last_version.assert_called_once()


def test_get_latest_repology_no_content(mock_catpkg_catpkgsplit: Mock, mocker: MockerFixture,
                                        mock_settings: Mock) -> None:
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.side_effect = [None, None]
    result = repology.get_latest_repology('cat/pkg', mock_settings)
    assert not result


def test_get_latest_repology_no_matching_release(mock_catpkg_catpkgsplit: Mock,
                                                 mocker: MockerFixture, mock_get_last_version: Mock,
                                                 mock_settings: Mock) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'srcname': 'other',
            'status': 'stable',
            'version': '0.0.1'
        },
    ]
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = None

    result = repology.get_latest_repology('cat/pkg', mock_settings)
    assert not result


def test_get_latest_repology_devel_status_allowed(mock_catpkg_catpkgsplit: Mock,
                                                  mocker: MockerFixture,
                                                  mock_get_last_version: Mock,
                                                  mock_settings: Mock) -> None:
    mock_settings.is_devel.return_value = True
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'srcname': 'pkg',
            'status': 'devel',
            'version': '3.3.3'
        },
    ]
    mock_get_content = mocker.patch('livecheck.special.repology.get_content')
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = {'version': '3.3.3'}

    result = repology.get_latest_repology('cat/pkg', mock_settings)
    assert result == '3.3.3'
