from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.sourceforge import (
    extract_repository,
    get_latest_sourceforge_metadata,
    get_latest_sourceforge_package,
    get_latest_sourceforge_package2,
    is_sourceforge,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
import pytest


@pytest.mark.parametrize(('url', 'expected'), [
    ('https://downloads.sourceforge.net/project/sample_project', 'sample_project'),
    ('https://download.sourceforge.net/project/sample_project', 'sample_project'),
    ('https://download.sourceforge.net/proj/sample_project', 'proj'),
    ('https://sf.net/projects/sample_project', 'sample_project'),
    ('https://sample_project.sourceforge.net', 'sample_project'),
    ('https://sample_project.sourceforge.io', 'sample_project'),
    ('https://sample_project.sourceforge.jp', 'sample_project'),
    ('https://example.com/sample_project', ''),
    ('', ''),
    ('https://sf.net/projectss/sample_project', 'sample_project'),
    ('https://ssourceforge.net/project/sample_project', ''),
])
def test_extract_repository(url: str, expected: str) -> None:
    result = extract_repository(url)
    if expected:
        assert result == expected
    else:
        assert not result


def test_get_latest_sourceforge_package_returns_latest_version(mocker: MockerFixture) -> None:
    # Mock extract_repository to return a repository name
    mocker.patch('livecheck.special.sourceforge.extract_repository', return_value='sample_project')
    # Mock get_content to return a dummy RSS feed
    dummy_rss = """
    <rss>
        <channel>
        <item>
            <title>sample_project-1.2.3.tar.gz</title>
        </item>
        <item>
            <title>sample_project-1.2.2.tar.gz</title>
        </item>
        </channel>
    </rss>
    """
    mock_response = mocker.Mock()
    mock_response.text = dummy_rss
    mocker.patch('livecheck.special.sourceforge.get_content', return_value=mock_response)
    # Mock get_archive_extension to always return True
    mocker.patch('livecheck.special.sourceforge.get_archive_extension', return_value=True)
    # Mock get_last_version to return the latest version dict
    mocker.patch('livecheck.special.sourceforge.get_last_version',
                 return_value={'version': '1.2.3'})
    result = get_latest_sourceforge_package('dummy_url', 'dummy_ebuild', mocker.Mock())
    assert result == '1.2.3'


def test_get_latest_sourceforge_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.extract_repository', return_value='sample_project')
    mocker.patch('livecheck.special.sourceforge.get_content', return_value=None)
    result = get_latest_sourceforge_package('dummy_url', 'dummy_ebuild', mocker.Mock())
    assert not result


def test_get_latest_sourceforge_package_no_versions_found(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.extract_repository', return_value='sample_project')
    dummy_rss = """
    <rss>
        <channel>
        <item>
            <title></title>
        </item>
        </channel>
    </rss>
    """
    mock_response = mocker.Mock()
    mock_response.text = dummy_rss
    mocker.patch('livecheck.special.sourceforge.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.sourceforge.get_archive_extension', return_value=False)
    mocker.patch('livecheck.special.sourceforge.get_last_version', return_value=None)
    result = get_latest_sourceforge_package('dummy_url', 'dummy_ebuild', mocker.Mock())
    assert not result


def test_get_latest_sourceforge_package2_calls_get_last_version(mocker: MockerFixture) -> None:
    dummy_rss = """
    <rss>
        <channel>
        <item>
            <title>sample_project-2.0.0.tar.gz</title>
        </item>
        </channel>
    </rss>
    """
    mock_response = mocker.Mock()
    mock_response.text = dummy_rss
    mocker.patch('livecheck.special.sourceforge.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.sourceforge.get_archive_extension', return_value=True)
    get_last_version = mocker.patch('livecheck.special.sourceforge.get_last_version',
                                    return_value={'version': '2.0.0'})
    result = get_latest_sourceforge_package2('sample_project', 'dummy_ebuild', mocker.Mock())
    assert result == '2.0.0'
    assert get_last_version.called


def test_get_latest_sourceforge_package2_returns_empty_if_no_last_version(
        mocker: MockerFixture) -> None:
    dummy_rss = """
    <rss>
        <channel>
        <item>
            <title>sample_project-2.0.0.tar.gz</title>
        </item>
        </channel>
    </rss>
    """
    mock_response = mocker.Mock()
    mock_response.text = dummy_rss
    mocker.patch('livecheck.special.sourceforge.get_content', return_value=mock_response)
    mocker.patch('livecheck.special.sourceforge.get_archive_extension', return_value=True)
    mocker.patch('livecheck.special.sourceforge.get_last_version', return_value=None)
    result = get_latest_sourceforge_package2('sample_project', 'dummy_ebuild', mocker.Mock())
    assert not result


def test_is_sourceforge_true_for_valid_urls(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.extract_repository', return_value='sample_project')
    assert is_sourceforge('https://downloads.sourceforge.net/project/sample_project')
    assert is_sourceforge('https://sample_project.sourceforge.net')
    assert is_sourceforge('https://sf.net/projects/sample_project')


def test_is_sourceforge_false_for_invalid_urls(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.extract_repository', return_value='')
    assert not is_sourceforge('https://example.com/sample_project')
    assert not is_sourceforge('')
    assert not is_sourceforge('https://not-sourceforge.org/project/sample_project')


def test_get_latest_sourceforge_metadata_calls_get_latest_sourceforge_package2(
        mocker: MockerFixture) -> None:
    mock_get_latest_sourceforge_package2 = mocker.patch(
        'livecheck.special.sourceforge.get_latest_sourceforge_package2', return_value='3.1.4')
    remote = 'sample_project'
    ebuild = 'dummy_ebuild'
    settings = mocker.Mock()
    result = get_latest_sourceforge_metadata(remote, ebuild, settings)
    assert result == '3.1.4'
    mock_get_latest_sourceforge_package2.assert_called_once_with(remote, ebuild, settings)


def test_get_latest_sourceforge_metadata_returns_empty_if_no_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.get_latest_sourceforge_package2', return_value='')
    remote = 'sample_project'
    ebuild = 'dummy_ebuild'
    settings = mocker.Mock()
    result = get_latest_sourceforge_metadata(remote, ebuild, settings)
    assert not result


def test_get_latest_sourceforge_metadata_with_none_return(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourceforge.get_latest_sourceforge_package2', return_value=None)
    remote = 'sample_project'
    ebuild = 'dummy_ebuild'
    settings = mocker.Mock()
    result = get_latest_sourceforge_metadata(remote, ebuild, settings)
    assert result is None
