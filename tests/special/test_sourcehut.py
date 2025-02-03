from livecheck.settings import LivecheckSettings
from livecheck.special.sourcehut import extract_owner_repo, get_branch

ebuild = "app-portage/livecheck-1.0"
settings = LivecheckSettings(branches={},
                             checksum_livechecks=None,
                             custom_livechecks=None,
                             dotnet_projects=None,
                             go_sum_uri=None,
                             type_packages=None,
                             no_auto_update=None,
                             semver=None,
                             sha_sources=None,
                             transformations=None,
                             yarn_base_packages=None,
                             yarn_packages=None,
                             jetbrains_packages=None,
                             keep_old=None,
                             gomodule_packages=None,
                             gomodule_path=None,
                             nodejs_packages=None,
                             nodejs_path=None,
                             development=None,
                             composer_packages=None,
                             composer_path=None,
                             regex_version=None,
                             restrict_version=None,
                             sync_version=None,
                             stable_version=None)


def test_extract_owner_repo_valid_git_url():
    url = "https://git.sr.ht/~owner/repo"
    expected = ("git.sr.ht", "~owner", "repo")
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_valid_hg_url():
    url = "https://hg.sr.ht/~owner/repo"
    expected = ("hg.sr.ht", "~owner", "repo")
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_invalid_url():
    url = "https://example.com/~owner/repo"
    expected = ("", "", "")
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_missing_owner_repo():
    url = "https://git.sr.ht/"
    expected = ("", "", "")
    assert extract_owner_repo(url) == expected


def test_extract_owner_repo_no_protocol():
    url = "git.sr.ht/~owner/repo/log/master/rss.xml"
    expected = ("git.sr.ht", "~owner", "repo")
    assert extract_owner_repo(url) == expected


def test_get_branch_from_url():
    url = "https://git.sr.ht/~owner/repo/log/master/rss.xml"
    assert get_branch(url, ebuild, settings) == "master"


def test_get_branch_from_settings():
    url = "https://git.sr.ht/~owner/repo/log/develop/rss.xml"
    assert get_branch(url, ebuild, settings) == "develop"


def test_get_branch_default_master():
    url = "https://git.sr.ht/~owner/repo/log/master/rss.xml"
    assert get_branch(url, ebuild, settings) == "master"


def test_get_branch_invalid_url():
    url = "https://example.com/~owner/repo"
    assert get_branch(url, ebuild, settings) == ""
