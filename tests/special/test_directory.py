from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.directory import get_latest_directory_package
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.asyncio


async def test_get_latest_directory_package_returns_latest(mocker: MockerFixture) -> None:
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
                 side_effect=lambda x: '.tar.gz' if x.endswith('.tar.gz') else '')
    last_version = {'version': '2.0', 'url': '/packages/foo-2.0.tar.gz'}
    mocker.patch('livecheck.special.directory.get_last_version', return_value=last_version)
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert version == '2.0'
    assert file_url == '/packages/foo-2.0.tar.gz'


async def test_get_latest_directory_get_last_version_falsy(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = '<html><body></body></html>'
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension', return_value='.tar.gz')
    mocker.patch('livecheck.special.directory.get_last_version', return_value=None)
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


async def test_get_latest_directory_package_no_results(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = '<html><body></body></html>'
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension', return_value='')
    mocker.patch('livecheck.special.directory.get_last_version', return_value=None)
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


async def test_get_latest_directory_package_no_content(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    mocker.patch('livecheck.special.directory.get_content', return_value=None)
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url


async def test_get_latest_directory_package_strips_archive_extension_from_reference(
        mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    html = '<html><body></body></html>'
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.directory.get_archive_extension',
                 side_effect=lambda x: '.tar.gz' if x.endswith('.tar.gz') else '')
    mock_get_last_version = mocker.patch('livecheck.special.directory.get_last_version',
                                         return_value=None)
    await get_latest_directory_package(url, ebuild, settings)
    assert mock_get_last_version.call_args.kwargs.get('version_reference') == 'foo-1.0'


async def test_get_latest_directory_package_accepts_release_with_different_archive_extension(
        mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/foo-1.0.tar.gz'
    ebuild = 'cat/foo-1.0'
    html = """<html>
      <body>
        <a href="foo-1.0.tar.gz">foo-1.0.tar.gz</a>
        <a href="foo-1.1.zip">foo-1.1.zip</a>
      </body>
    </html>"""
    mock_response = mocker.Mock()
    mock_response.text = html
    mocker.patch('livecheck.special.directory.get_content', return_value=mock_response)
    settings = mocker.Mock()
    settings.regex_version = {}
    settings.restrict_version = {}
    settings.restrict_version_process = ''
    settings.stable_version = {}
    settings.transformations = {}
    settings.is_devel = lambda _: False
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert version == '1.1'
    assert file_url == '/packages/foo-1.1.zip'


async def test_get_latest_directory_package_no_match_in_url(mocker: MockerFixture) -> None:
    url = 'https://example.com/packages/'
    ebuild = 'foo-1.0.ebuild'
    settings = mocker.Mock()
    version, file_url = await get_latest_directory_package(url, ebuild, settings)
    assert not version
    assert not file_url
