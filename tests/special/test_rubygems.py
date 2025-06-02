from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special import rubygems

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_rubygems_package_returns_latest_version(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.special.rubygems.catpkg_catpkgsplit')
    mock_get_content = mocker.patch('livecheck.special.rubygems.get_content')
    mock_get_last_version = mocker.patch('livecheck.special.rubygems.get_last_version')
    mock_catpkgsplit.return_value = ('dev-ruby', None, 'rails', None)
    mock_response = mocker.Mock()
    mock_response.json.return_value = [
        {
            'number': '7.0.0',
            'prerelease': False
        },
        {
            'number': '7.1.0.beta',
            'prerelease': True
        },
    ]
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = {'version': '7.0.0'}
    result = rubygems.get_latest_rubygems_package(
        'dev-ruby/rails', mocker.Mock(is_devel=mocker.Mock(return_value=False)))
    assert result == '7.0.0'
    mock_get_content.assert_called_once_with('https://rubygems.org/api/v1/versions/rails.json')
    mock_get_last_version.assert_called_once()
    # Called once in get_latest_rubygems_package and get_latest_rubygems_package2
    mock_catpkgsplit.assert_any_call('dev-ruby/rails')


def test_get_latest_rubygems_package_returns_empty_on_no_content(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.special.rubygems.catpkg_catpkgsplit')
    mock_get_content = mocker.patch('livecheck.special.rubygems.get_content')
    mock_get_content.return_value = None
    mock_catpkgsplit.return_value = ('dev-ruby', None, 'rails', None)
    result = rubygems.get_latest_rubygems_package(
        'dev-ruby/rails', mocker.Mock(is_devel=mocker.Mock(return_value=False)))
    assert not result


def test_get_latest_rubygems_package_returns_empty_on_no_last_version(
        mocker: MockerFixture) -> None:
    mock_get_last_version = mocker.patch('livecheck.special.rubygems.get_last_version')
    mock_catpkgsplit = mocker.patch('livecheck.special.rubygems.catpkg_catpkgsplit')
    mock_get_content = mocker.patch('livecheck.special.rubygems.get_content')
    mock_catpkgsplit.return_value = ('dev-ruby', None, 'rails', None)
    mock_response = mocker.Mock()
    mock_response.json.return_value = [{'number': '7.0.0', 'prerelease': False}]
    mock_get_content.return_value = mock_response
    mock_get_last_version.return_value = None
    result = rubygems.get_latest_rubygems_package(
        'dev-ruby/rails', mocker.Mock(is_devel=mocker.Mock(return_value=False)))
    assert not result
    mocker.patch('livecheck.special.rubygems.get_last_version')


def test_get_latest_rubygems_metadata_calls_package2_and_returns_version(
        mocker: MockerFixture) -> None:
    mock_get_latest_rubygems_package2 = mocker.patch(
        'livecheck.special.rubygems.get_latest_rubygems_package2')
    mock_get_latest_rubygems_package2.return_value = '8.0.0'
    remote = 'rails'
    ebuild = 'dev-ruby/rails'
    settings = mocker.Mock()
    result = rubygems.get_latest_rubygems_metadata(remote, ebuild, settings)
    assert result == '8.0.0'
    mock_get_latest_rubygems_package2.assert_called_once_with(remote, ebuild, settings)


def test_get_latest_rubygems_metadata_returns_empty_string_when_package2_returns_empty(
        mocker: MockerFixture) -> None:
    mock_get_latest_rubygems_package2 = mocker.patch(
        'livecheck.special.rubygems.get_latest_rubygems_package2')
    mock_get_latest_rubygems_package2.return_value = ''
    remote = 'rails'
    ebuild = 'dev-ruby/rails'
    settings = mocker.Mock()
    result = rubygems.get_latest_rubygems_metadata(remote, ebuild, settings)
    assert not result
    mock_get_latest_rubygems_package2.assert_called_once_with(remote, ebuild, settings)
