from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.pypi import (
    extract_project,
    get_latest_pypi_metadata,
    get_latest_pypi_package,
    get_url,
    is_pypi,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from pytest_mock import MockerFixture

test_cases = [{
    'url': 'https://pypi.org/project/source/s/someproject/1.0.0/',
    'expected': 'someproject'
}, {
    'url': 'https://pypi.org/project/someproject-1.0.0/',
    'expected': ''
}, {
    'url': 'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
    'expected': 'someproject'
}, {
    'url': 'https://pypi.io/packages/source/s/someproject/someproject-1.0.0.tar.gz',
    'expected': 'someproject'
}, {
    'url': 'https://example.com/project/someproject-1.0.0/',
    'expected': ''
}, {
    'url': 'https://pypi.org/project/someproject/',
    'expected': ''
}, {
    'url': 'https://pypi/project/source/s/someproject/1.0.0/',
    'expected': 'someproject'
}, {
    'url': 'https://pypi.io/project/source/s/someproject/1.0.0/',
    'expected': 'someproject'
}, {
    'url': 'https://1pypi.io/project/source/someproject/1.0.0/',
    'expected': ''
}, {
    'url': 'https://www.pythonhosted.org/project/source/someproject/1.0.0/',
    'expected': ''
}, {
    'url': 'mirror://pypi/project/source/s/someproject/1.0.0/',
    'expected': 'someproject'
}, {
    'url':
        'https://files.pythonhosted.org/packages/15/1f/ca74b65b19798895d63a6e92874162f44233467c9e7c1ed8afd19016ebe9/chevron-0.14.0.tar.gz',
    'expected':
        'chevron'
}]


@pytest.mark.parametrize('case', test_cases)
def test_extract_project(case: dict[str, str]) -> None:
    assert extract_project(case['url']) == case['expected']


@pytest.mark.parametrize(
    ('ext', 'item', 'expected'),
    [
        # Test: url with matching extension
        ('.tar.gz', [{
            'url':
                'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz'
        }, {
            'url':
                'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.zip'
        }], 'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz'
         ),
        # Test: no url with matching extension, but one with archive extension
        ('.whl', [{
            'url':
                'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz'
        }, {
            'url':
                'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.zip'
        }], 'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz'
         ),
        # Test: no url with matching extension, no archive extension
        ('.exe', [{
            'url':
                'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.txt'
        }], ''),
        # Test: empty item list
        ('.tar.gz', [], '')
    ])
def test_get_url(mocker: MockerFixture, ext: str, item: Collection[Mapping[str, str]],
                 expected: str) -> None:
    def fake_get_archive_extension(url: str) -> str:
        if url.endswith(('.tar.gz', '.zip')):
            return '.tar.gz' if url.endswith('.tar.gz') else '.zip'
        return ''

    mocker.patch('livecheck.special.pypi.get_archive_extension',
                 side_effect=fake_get_archive_extension)
    assert get_url(ext, item) == expected


@pytest.mark.parametrize(
    ('src_uri', 'project_name', 'latest_version', 'latest_url'),
    [('https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
      'someproject', '2.0.0',
      'https://files.pythonhosted.org/packages/source/s/someproject/someproject-2.0.0.tar.gz'),
     ('https://files.pythonhosted.org/packages/source/s/another/another-0.1.0.zip', 'another',
      '0.2.0', 'https://files.pythonhosted.org/packages/source/s/another/another-0.2.0.zip')])
@pytest.mark.asyncio
async def test_get_latest_pypi_package_success(mocker: MockerFixture, src_uri: str,
                                               project_name: str, latest_version: str,
                                               latest_url: str) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value=project_name)
    ext = '.tar.gz' if src_uri.endswith('.tar.gz') else '.zip'
    mocker.patch('livecheck.special.pypi.get_archive_extension', return_value=ext)
    releases = {latest_version: [{'url': latest_url}], '1.0.0': [{'url': src_uri}]}
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'releases': releases}
    mocker.patch('livecheck.special.pypi.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.pypi.get_last_version',
                 return_value={
                     'version': latest_version,
                     'url': latest_url
                 })

    version, url = await get_latest_pypi_package(src_uri, 'dummy.ebuild', mocker.Mock())
    assert version == latest_version
    assert url == latest_url


@pytest.mark.asyncio
async def test_get_latest_pypi_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value='someproject')
    mocker.patch('livecheck.special.pypi.get_archive_extension', return_value='.tar.gz')
    mocker.patch('livecheck.special.pypi.get_content', return_value=None)
    version, url = await get_latest_pypi_package(
        'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
        'dummy.ebuild', mocker.Mock())
    assert not version
    assert not url


@pytest.mark.asyncio
async def test_get_latest_pypi_package_no_last_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value='someproject')
    mocker.patch('livecheck.special.pypi.get_archive_extension', return_value='.tar.gz')
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'releases': {'1.0.0': [{'url': 'url'}]}}
    mocker.patch('livecheck.special.pypi.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.pypi.get_last_version', return_value=None)
    version, url = await get_latest_pypi_package(
        'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
        'dummy.ebuild', mocker.Mock())
    assert not version
    assert not url


@pytest.mark.asyncio
async def test_get_latest_pypi_package_reference_without_archive_extension(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value='myapp')
    mocker.patch('livecheck.special.pypi.get_archive_extension', return_value='')
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'releases': {'1.0.0': [{'url': 'irrelevant'}]}}
    mocker.patch('livecheck.special.pypi.get_content', return_value=mock_response)
    mock_get_last_version = mocker.patch('livecheck.special.pypi.get_last_version',
                                         return_value=None)
    await get_latest_pypi_package('https://pypi.org/project/myapp/', 'cat/myapp-1.0.0',
                                  mocker.Mock())
    assert mock_get_last_version.call_args.kwargs.get('version_reference') == 'myapp'


@pytest.mark.asyncio
async def test_get_latest_pypi_package_strips_archive_extension_from_reference(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value='myapp')
    mocker.patch('livecheck.special.pypi.get_archive_extension',
                 side_effect=lambda u: ('.tar.gz' if u.endswith('.tar.gz') else
                                        ('.zip' if u.endswith('.zip') else '')))
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'releases': {'1.0.0': [{'url': 'irrelevant'}]}}
    mocker.patch('livecheck.special.pypi.get_content', return_value=mock_response)
    mock_get_last_version = mocker.patch('livecheck.special.pypi.get_last_version',
                                         return_value=None)
    src_uri = 'https://files.pythonhosted.org/packages/source/m/myapp/myapp-1.0.0.tar.gz'
    await get_latest_pypi_package(src_uri, 'cat/myapp-1.0.0', mocker.Mock())
    assert mock_get_last_version.call_args.kwargs.get('version_reference') == 'myapp-1.0.0'


@pytest.mark.asyncio
async def test_get_latest_pypi_package_accepts_release_with_different_archive_extension(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.extract_project', return_value='myapp')
    src_uri = 'https://files.pythonhosted.org/packages/source/m/myapp/myapp-1.0.0.tar.gz'
    new_url = 'https://files.pythonhosted.org/packages/source/m/myapp/myapp-1.1.0.zip'
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        'releases': {
            '1.0.0': [{
                'url': src_uri
            }],
            '1.1.0': [{
                'url': new_url
            }]
        }
    }
    mocker.patch('livecheck.special.pypi.get_content', return_value=mock_response)
    settings = mocker.Mock()
    settings.regex_version = {}
    settings.restrict_version = {}
    settings.restrict_version_process = ''
    settings.stable_version = {}
    settings.transformations = {}
    settings.is_devel = lambda _: False
    version, url = await get_latest_pypi_package(src_uri, 'cat/myapp-1.0.0', settings)
    assert version == '1.1.0'
    assert url == new_url


@pytest.mark.parametrize(
    ('url', 'extract_project_return', 'expected'),
    [('https://pypi.org/project/source/s/someproject/1.0.0/', 'someproject', True),
     ('https://pypi.org/project/someproject-1.0.0/', '', False),
     ('https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
      'someproject', True), ('https://example.com/project/someproject-1.0.0/', '', False),
     ('mirror://pypi/project/source/s/someproject/1.0.0/', 'someproject', True),
     ('https://pypi.io/project/source/s/someproject/1.0.0/', 'someproject', True),
     ('https://1pypi.io/project/source/someproject/1.0.0/', '', False), ('', '', False)])
def test_is_pypi(mocker: MockerFixture, url: str, extract_project_return: str,
                 expected: bool) -> None:  # noqa: FBT001
    mocker.patch('livecheck.special.pypi.extract_project', return_value=extract_project_return)
    assert is_pypi(url) is expected


@pytest.mark.parametrize(
    ('remote', 'ebuild', 'latest_version', 'latest_url'),
    [('someproject', 'dummy.ebuild', '2.0.0',
      'https://files.pythonhosted.org/packages/source/s/someproject/someproject-2.0.0.tar.gz'),
     ('another', 'another.ebuild', '0.2.0',
      'https://files.pythonhosted.org/packages/source/s/another/another-0.2.0.zip')])
@pytest.mark.asyncio
async def test_get_latest_pypi_metadata_success(mocker: MockerFixture, remote: str, ebuild: str,
                                                latest_version: str, latest_url: str) -> None:
    mocker.patch('livecheck.special.pypi.get_latest_pypi_package2',
                 return_value=(latest_version, latest_url))
    version, url = await get_latest_pypi_metadata(remote, ebuild, mocker.Mock())
    assert version == latest_version
    assert url == latest_url


@pytest.mark.asyncio
async def test_get_latest_pypi_metadata_empty(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.pypi.get_latest_pypi_package2', return_value=('', ''))
    version, url = await get_latest_pypi_metadata('remote', 'ebuild', mocker.Mock())
    assert not version
    assert not url
