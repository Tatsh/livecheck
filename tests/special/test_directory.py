from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.directory import get_latest_directory_package

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_directory_package_returns_latest(mocker: MockerFixture) -> None:
    # Arrange
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = """<html>
      <body>
        <a href="foo-1.0.tar.gz">foo-1.0.tar.gz</a>
        <a href="foo-2.0.tar.gz">foo-2.0.tar.gz</a>
        <a href="foo-1.5.tar.gz">foo-1.5.tar.gz</a>
        <a href="bar-1.0.tar.gz">bar-1.0.tar.gz</a>
        <a href="">bad</a>
      </body>
    </html>"""
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension',
                 side_effect=lambda x: x.endswith('.tar.gz'))
    last_version = {'version': '2.0', 'url': '/packages/foo-2.0.tar.gz'}
    mocker.patch('livecheck.special.directory.get_last_version', return_value=last_version)
    version, file_url = get_latest_directory_package(url, ebuild, settings)
    assert version == '2.0'
    assert file_url == '/packages/foo-2.0.tar.gz'


def test_get_latest_directory_get_last_version_falsy(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = '<html><body></body></html>'
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension', return_value=True)
    mocker.patch('livecheck.special.directory.get_last_version', return_value=None)
    version, file_url = get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


def test_get_latest_directory_package_no_results(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = '<html><body></body></html>'
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension', return_value=False)
    mocker.patch('livecheck.special.directory.get_last_version', return_value=None)
    version, file_url = get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


def test_get_latest_directory_package_no_content(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.directory.get_content', return_value=None)
    version, file_url = get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


def test_get_latest_directory_package_no_match_in_url(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    version, file_url = get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url
