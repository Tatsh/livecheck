from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.settings import LivecheckSettings
from livecheck.special import sourcehut
from livecheck.special.sourcehut import extract_owner_repo, get_branch

if TYPE_CHECKING:
    from collections.abc import Collection

    from pytest_mock import MockerFixture

EBUILD = 'app-portage/livecheck-1.0'


def test_extract_owner_repo_valid_git_url() -> None:
    url = 'https://git.sr.ht/~owner/repo'
    expected = ('git.sr.ht', '~owner', 'repo')
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_valid_hg_url() -> None:
    url = 'https://hg.sr.ht/~owner/repo'
    expected = ('hg.sr.ht', '~owner', 'repo')
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_invalid_url() -> None:
    url = 'https://example.com/~owner/repo'
    expected = ('', '', '')
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_missing_owner_repo() -> None:
    url = 'https://git.sr.ht/'
    expected = ('', '', '')
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_no_protocol() -> None:
    url = 'git.sr.ht/~owner/repo/log/master/rss.xml'
    expected = ('git.sr.ht', '~owner', 'repo')
    assert extract_owner_repo(url) == expected


def test_get_branch_from_url() -> None:
    url = 'https://git.sr.ht/~owner/repo/log/master/rss.xml'
    assert get_branch(url, EBUILD, LivecheckSettings()) == 'master'


def test_get_branch_from_settings() -> None:
    url = 'https://git.sr.ht/~owner/repo/log/develop/rss.xml'
    assert get_branch(url, EBUILD, LivecheckSettings()) == 'develop'


def test_get_branch_default_master() -> None:
    url = 'https://git.sr.ht/~owner/repo/log/master/rss.xml'
    assert get_branch(url, EBUILD, LivecheckSettings()) == 'master'


def test_get_branch_invalid_url() -> None:
    url = 'https://example.com/~owner/repo'
    assert not get_branch(url, EBUILD, LivecheckSettings())


def test_get_branch_url_with_no_log_segment() -> None:
    url = 'https://git.sr.ht/~owner/repo/tree/master'
    assert not get_branch(url, EBUILD, LivecheckSettings())


def test_get_branch_settings_priority() -> None:
    url = 'https://git.sr.ht/~owner/repo'
    s = LivecheckSettings()
    s.branches['app-portage/livecheck'] = 'custom-branch'
    assert get_branch(url, EBUILD, s) == 'custom-branch'


def test_get_branch_is_sha(mocker: MockerFixture) -> None:
    url = 'https://git.sr.ht/~owner/repo/abcdef1234567890'
    mocker.patch('livecheck.utils.is_sha', return_value=True)
    assert get_branch(url, EBUILD, LivecheckSettings()) == 'master'


def make_rss_xml(tags: Collection[str]) -> str:
    items = ''
    for tag in tags:
        items += f"""
        <item>
            <guid>https://git.sr.ht/~owner/repo/{tag}</guid>
        </item>
        """
    return f"""<?xml version="1.0"?>
    <rss>
        <channel>
        {items}
        </channel>
    </rss>
    """


def test_get_latest_sourcehut_package_returns_latest(mocker: MockerFixture) -> None:
    tags = ['v1.0.0', 'v1.2.0', 'v1.1.0']
    xml = make_rss_xml(tags)
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    mocker.patch('livecheck.special.sourcehut.get_last_version', return_value={'version': 'v1.2.0'})
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_package(url, ebuild, settings)
    assert result == 'v1.2.0'


def test_get_latest_sourcehut_package_no_owner_repo(mocker: MockerFixture) -> None:
    url = 'https://example.com/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_package(url, ebuild, settings)
    assert not result


def test_get_latest_sourcehut_package_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=None)
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_package(url, ebuild, settings)
    assert not result


def test_get_latest_sourcehut_package_no_versions(mocker: MockerFixture) -> None:
    xml = make_rss_xml([])
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    mocker.patch('livecheck.special.sourcehut.get_last_version', return_value=None)
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_package(url, ebuild, settings)
    assert not result


def test_get_latest_sourcehut_package_guid_missing(mocker: MockerFixture) -> None:
    xml = """<?xml version="1.0"?>
    <rss>
        <channel>
        <item>
            <title>Some title</title>
        </item>
        </channel>
    </rss>
    """
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    mocker.patch('livecheck.special.sourcehut.get_last_version', return_value=None)
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_package(url, ebuild, settings)
    assert not result


def test_get_latest_sourcehut_branch_returns_commit_and_date(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_branch', return_value='main')
    mock_commit = 'abcdef1234567890'
    mock_date = '20240601'
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_commit',
                 return_value=(mock_commit, mock_date))
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut(url, ebuild, settings, force_sha=True)
    assert result == ('', mock_commit, mock_date)


def test_get_latest_sourcehut_branch_force_sha_false(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_branch', return_value='main')
    mock_commit = 'abcdef1234567890'
    mock_date = '20240601'
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_commit',
                 return_value=(mock_commit, mock_date))
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut(url, ebuild, settings, force_sha=False)
    assert result == ('', '', mock_date)


def test_get_latest_sourcehut_no_branch_returns_last_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_branch', return_value='')
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package', return_value='v2.0.0')
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut(url, ebuild, settings, force_sha=True)
    assert result == ('v2.0.0', '', '')


def test_get_latest_sourcehut_no_branch_no_version(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_branch', return_value='')
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package', return_value='')
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut(url, ebuild, settings, force_sha=True)
    assert result == ('', '', '')


def test_get_latest_sourcehut_branch_commit_empty(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_branch', return_value='main')
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_commit', return_value=('', ''))
    url = 'https://git.sr.ht/~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut(url, ebuild, settings, force_sha=True)
    assert result == ('', '', '')


def test_get_latest_sourcehut_metadata_git_success(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package',
                 side_effect=['v3.1.0', ''])
    remote = '~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_metadata(remote, ebuild, settings)
    assert result == 'v3.1.0'


def test_get_latest_sourcehut_metadata_git_empty_hg_success(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package',
                 side_effect=['', 'v2.5.0'])
    remote = '~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_metadata(remote, ebuild, settings)
    assert result == 'v2.5.0'


def test_get_latest_sourcehut_metadata_both_empty(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package', side_effect=['', ''])
    remote = '~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    result = sourcehut.get_latest_sourcehut_metadata(remote, ebuild, settings)
    assert not result


def test_get_latest_sourcehut_metadata_calls_with_correct_urls(mocker: MockerFixture) -> None:
    get_latest = mocker.patch('livecheck.special.sourcehut.get_latest_sourcehut_package',
                              side_effect=['', ''])
    remote = '~owner/repo'
    ebuild = 'app-portage/livecheck-1.0'
    settings = mocker.Mock()
    sourcehut.get_latest_sourcehut_metadata(remote, ebuild, settings)
    get_latest.assert_any_call('https://git.sr.ht/~owner/repo', ebuild, settings)
    get_latest.assert_any_call('https://hg.sr.ht/~owner/repo', ebuild, settings)


def make_commit_rss_xml(commit: str, pubdate: str) -> str:
    return f"""<?xml version="1.0"?>
    <rss>
        <channel>
            <item>
                <guid>https://git.sr.ht/~owner/repo/{commit}</guid>
                <pubDate>{pubdate}</pubDate>
            </item>
        </channel>
    </rss>
    """


def test_get_latest_sourcehut_commit_returns_commit_and_date(mocker: MockerFixture) -> None:
    commit = 'abcdef1234567890'
    pubdate = 'Sat, 01 Jun 2024 12:34:56 +0000'
    xml = make_commit_rss_xml(commit, pubdate)
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == (commit, '20240601')


def test_get_latest_sourcehut_commit_invalid_url(mocker: MockerFixture) -> None:
    url = 'https://example.com/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == ('', '')


def test_get_latest_sourcehut_commit_no_content(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=None)
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == ('', '')


def test_get_latest_sourcehut_commit_missing_guid_and_pubdate(mocker: MockerFixture) -> None:
    xml = """<?xml version="1.0"?>
    <rss>
        <channel>
            <item>
                <title>Some title</title>
            </item>
        </channel>
    </rss>
    """
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == ('', '')


def test_get_latest_sourcehut_commit_invalid_date_format(mocker: MockerFixture) -> None:
    commit = 'abcdef1234567890'
    pubdate = 'not a date'
    xml = make_commit_rss_xml(commit, pubdate)
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == (commit, '')


def test_get_latest_sourcehut_commit_guid_missing_text(mocker: MockerFixture) -> None:
    xml = """<?xml version="1.0"?>
    <rss>
        <channel>
            <item>
                <guid></guid>
                <pubDate>Sat, 01 Jun 2024 12:34:56 +0000</pubDate>
            </item>
        </channel>
    </rss>
    """
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == ('', '20240601')


def test_get_latest_sourcehut_commit_pubdate_missing_text(mocker: MockerFixture) -> None:
    commit = 'abcdef1234567890'
    xml = f"""<?xml version="1.0"?>
    <rss>
        <channel>
            <item>
                <guid>https://git.sr.ht/~owner/repo/{commit}</guid>
                <pubDate></pubDate>
            </item>
        </channel>
    </rss>
    """
    mocker.patch('livecheck.special.sourcehut.get_content', return_value=mocker.MagicMock(text=xml))
    url = 'https://git.sr.ht/~owner/repo'
    result = sourcehut.get_latest_sourcehut_commit(url, branch='main')
    assert result == (commit, '')
