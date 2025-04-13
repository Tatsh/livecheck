from livecheck.settings import LivecheckSettings
from livecheck.special.sourcehut import extract_owner_repo, get_branch

EBUILD = 'app-portage/livecheck-1.0'
settings = LivecheckSettings()


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
    assert get_branch(url, EBUILD, settings) == 'master'


def test_get_branch_from_settings() -> None:
    url = 'https://git.sr.ht/~owner/repo/log/develop/rss.xml'
    assert get_branch(url, EBUILD, settings) == 'develop'


def test_get_branch_default_master() -> None:
    url = 'https://git.sr.ht/~owner/repo/log/master/rss.xml'
    assert get_branch(url, EBUILD, settings) == 'master'


def test_get_branch_invalid_url() -> None:
    url = 'https://example.com/~owner/repo'
    assert not get_branch(url, EBUILD, settings)
