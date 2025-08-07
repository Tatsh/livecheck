from __future__ import annotations

from typing import TYPE_CHECKING, Any

from defusedxml import ElementTree as ET  # noqa: N817
from livecheck.special.github import (
    extract_owner_repo,
    get_branch,
    get_latest_github,
    get_latest_github_commit,
    get_latest_github_commit2,
    get_latest_github_metadata,
    get_latest_github_package,
    is_github,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pytest_mock import MockerFixture

test_cases = {
    'test_extract_owner_repo_valid_github_com': {
        'url': 'https://github.com/username/repo',
        'expected': ('https://github.com/username/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_valid_github_io': {
        'url': 'https://username.github.io/repo',
        'expected': ('https://username.github.io/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_invalid_url': {
        'url': 'https://example.com/username/repo',
        'expected': ('', '', ''),
        'is_github': False
    },
    'test_extract_owner_repo_no_repo': {
        'url': 'https://github.com/username/',
        'expected': ('', '', ''),
        'is_github': False
    },
    'test_extract_owner_repo_empty_string': {
        'url': '',
        'expected': ('', '', ''),
        'is_github': False
    },
    'test_extract_owner_repo_github_com_with_dot_git': {
        'url': 'https://github.io/username/repo.git',
        'expected': ('https://github.io/username/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_github_com_with_subpath': {
        'url': 'https://github.com/username/repo/subpath',
        'expected': ('https://github.com/username/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_github_com_with_query_params': {
        'url': 'https://github.com/username/repo?param=value',
        'expected': ('https://github.com/username/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_github_com_with_fragment': {
        'url': 'https://github.com/username/repo#section',
        'expected': ('https://github.com/username/repo', 'username', 'repo'),
        'is_github': True
    },
    'test_extract_owner_repo_invalid_url2': {
        'url': 'https://github.org/username/repo.git',
        'expected': ('', '', ''),
        'is_github': False
    },
    'test_extract_owner_repo_invalid_url3': {
        'url': 'https://github.com',
        'expected': ('', '', ''),
        'is_github': False
    },
    'test_extract_owner_repo_invalid_url4': {
        'url': 'https://x.github.com',
        'expected': ('', '', ''),
        'is_github': False
    },
    'www-apps/icingaweb2': {
        'url': 'https://codeload.github.com/Icinga/icingaweb2/tar.gz/v2.9.0',
        'expected': ('https://codeload.github.com/Icinga', 'codeload', 'Icinga'),
        'is_github': True
    },
    'net-libs/neon': {
        'url': 'https://notroj.github.io/neon/neon-0.33.0.tar.gz',
        'expected': ('https://notroj.github.io/neon', 'notroj', 'neon'),
        'is_github': True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_owner_repo(test_case: dict[str, Any]) -> None:
    assert extract_owner_repo(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_github(test_case: dict[str, Any]) -> None:
    assert is_github(test_case['url']) == test_case['is_github']


@pytest.mark.parametrize(
    ('url', 'ebuild', 'owner', 'repo', 'tag', 'sha', 'expected_version', 'expected_sha'),
    [
        ('https://github.com/username/repo', 'category/repo-1.0.0.ebuild', 'username', 'repo',
         'v1.0.0', 'deadbeef1234567890', '1.0.0', 'deadbeef1234567890'),
        ('https://github.com/username/repo', 'category/repo-2.0.0.ebuild', 'username', 'repo', '',
         '', '', ''),
        (
            'https://github.com/username/repo',
            'category/repo-1.0.0.ebuild',
            '',  # owner
            '',  # repo
            '',
            '',
            '',
            ''),
    ])
def test_get_latest_github_package(mocker: MockerFixture, url: str, ebuild: str, owner: str,
                                   repo: str, tag: str, sha: str, expected_version: str,
                                   expected_sha: str) -> None:
    # Patch extract_owner_repo to control owner/repo/domain extraction
    mocker.patch(
        'livecheck.special.github.extract_owner_repo',
        return_value=(f'https://github.com/{owner}/{repo}' if owner and repo else '', owner, repo))

    # Patch get_content for the tags.atom and tag sha requests
    mock_get_content = mocker.patch('livecheck.special.github.get_content')
    # Patch get_last_version to simulate version extraction
    mock_get_last_version = mocker.patch('livecheck.special.github.get_last_version')

    if owner and repo and tag:
        # Simulate tags.atom XML response
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>https://github.com/{owner}/{repo}/releases/tag/{tag}</id>
            </entry>
            <entry>
                <id />
            </entry>
        </feed>
        """
        mock_response_tags = mocker.Mock()
        mock_response_tags.text = xml
        # Simulate tag sha API response
        mock_response_sha = mocker.Mock()
        mock_response_sha.json.return_value = {'object': {'sha': sha}}
        # get_content returns tags.atom response first, then sha response
        mock_get_content.side_effect = [mock_response_tags, mock_response_sha]
        # get_last_version returns a dict with version and id
        mock_get_last_version.return_value = {'version': expected_version, 'id': tag}
    elif owner and repo and not tag:
        # Simulate tags.atom XML response with no entries
        xml = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        mock_response_tags = mocker.Mock()
        mock_response_tags.text = xml
        mock_get_content.return_value = mock_response_tags
        mock_get_last_version.return_value = None

    result = get_latest_github_package(url, ebuild, mocker.Mock(branches={}))
    assert result == (expected_version, expected_sha)


def test_get_latest_github_package_no_response(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.github.get_content', return_value=None)
    mocker.patch('livecheck.special.github.extract_owner_repo',
                 return_value=('domain', 'owner', 'repo'))
    result = get_latest_github_package('', 'category/repo-1.0.0.ebuild', mocker.Mock(branches={}))
    assert result == ('', '')


def test_get_latest_github_package_xml_parse_error(mocker: MockerFixture) -> None:
    # Patch extract_owner_repo to return valid values
    mocker.patch('livecheck.special.github.extract_owner_repo',
                 return_value=('https://github.com/owner/repo', 'owner', 'repo'))
    # Patch get_content to return a mock response with any text
    mock_response = mocker.Mock()
    mock_response.text = '<invalid><xml>'
    mocker.patch('livecheck.special.github.get_content', return_value=mock_response)
    # Patch ET.fromstring to raise ParseError
    mocker.patch('livecheck.special.github.ET.fromstring', side_effect=ET.ParseError)
    result = get_latest_github_package('https://github.com/owner/repo', 'cat/repo-1.0.0.ebuild',
                                       mocker.Mock())
    assert result == ('', '')


def test_get_latest_github_package_no_response_2(mocker: MockerFixture) -> None:
    xml = '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    mocker.patch('livecheck.special.github.get_content', side_effect=[mocker.Mock(text=xml), None])
    mocker.patch('livecheck.special.github.extract_owner_repo',
                 return_value=('domain', 'owner', 'repo'))
    mocker.patch('livecheck.special.github.get_last_version',
                 return_value={
                     'version': 'version',
                     'id': 'id'
                 })
    result = get_latest_github_package('', 'category/repo-1.0.0.ebuild', mocker.Mock(branches={}))
    assert result == ('version', '')


@pytest.mark.parametrize(
    ('url', 'branch', 'owner', 'repo', 'commit_sha', 'commit_date', 'expected'),
    [
        (
            'https://github.com/username/repo',
            'main',
            'username',
            'repo',
            'abc123def456',
            '2024-06-01T12:34:56Z',
            ('abc123def456', '20240601'),
        ),
        (
            'https://github.com/username/repo',
            'develop',
            'username',
            'repo',
            'cafebabe',
            '2023-12-31T23:59:59Z',
            ('cafebabe', '20231231'),
        ),
        (
            'https://github.com/username/repo',
            'main',
            '',  # owner
            '',  # repo
            '',  # commit_sha
            '',  # commit_date
            ('', ''),
        ),
    ])
def test_get_latest_github_commit(mocker: MockerFixture, url: str, branch: str, owner: str,
                                  repo: str, commit_sha: str, commit_date: str,
                                  expected: tuple[str, str]) -> None:
    # Patch extract_owner_repo to control owner/repo extraction
    mocker.patch('livecheck.special.github.extract_owner_repo',
                 return_value=('', owner, repo) if owner and repo else ('', '', ''))
    # Patch get_latest_github_commit2 to control commit hash and date
    mock_commit2 = mocker.patch('livecheck.special.github.get_latest_github_commit2')
    if owner and repo:
        mock_commit2.return_value = (commit_sha, commit_date[:10].replace('-', ''))
    else:
        mock_commit2.return_value = ('', '')

    result = get_latest_github_commit(url, branch)
    assert result == expected


@pytest.mark.parametrize(
    ('owner', 'repo', 'branch', 'commit_sha', 'commit_date', 'expected_sha', 'expected_date'),
    [
        (
            'username',
            'repo',
            'main',
            'abc123def456',
            '2024-06-01T12:34:56Z',
            'abc123def456',
            '20240601',
        ),
        (
            'username',
            'repo',
            'main',
            'cafebabe',
            '2023-12-31T23:59:59Z',
            'cafebabe',
            '20231231',
        ),
        (
            'username',
            'repo',
            'main',
            'cafebabe123456',
            '2022-01-15T00:00:00Z',
            'cafebabe123456',
            '20220115',
        ),
        # Test with invalid date format (should fallback to first 10 chars)
        (
            'username',
            'repo',
            'main',
            'bad',
            'not-a-date',
            'bad',
            'not-a-date',
        ),
    ],
)
def test_get_latest_github_commit2_success(mocker: MockerFixture, owner: str, repo: str,
                                           branch: str, commit_sha: str, commit_date: str,
                                           expected_sha: str, expected_date: str) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        'commit': {
            'sha': commit_sha,
            'commit': {
                'committer': {
                    'date': commit_date
                }
            }
        }
    }
    mocker.patch('livecheck.special.github.get_content', return_value=mock_response)
    result = get_latest_github_commit2(owner, repo, branch)
    assert result == (expected_sha, expected_date)


def test_get_latest_github_commit2_no_response(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.github.get_content', return_value=None)
    result = get_latest_github_commit2('owner', 'repo', 'main')
    assert result == ('', '')


def test_get_latest_github_commit2_missing_commit_key(mocker: MockerFixture) -> None:
    mock_response = mocker.Mock()
    mock_response.json.return_value = {}
    mocker.patch('livecheck.special.github.get_content', return_value=mock_response)
    with pytest.raises(KeyError):
        get_latest_github_commit2('owner', 'repo', 'main')


@pytest.mark.parametrize(
    ('url', 'ebuild', 'branches_dict', 'expected_branch'),
    [
        # URL with /commits/<branch>
        ('https://github.com/user/repo/commits/main.atom', 'cat/pkg-1.0.0.ebuild', {}, 'main'),
        ('https://github.com/user/repo/commits/dev.atom', 'cat/pkg-1.0.0.ebuild', {}, 'dev'),
        # Branch from settings
        ('https://github.com/user/repo', 'cat/pkg-1.0.0.ebuild', {
            'cat/pkg': 'feature'
        }, 'feature'),
        # Default to master if is_sha returns True
        ('https://github.com/user/repo/abcdef', 'cat/pkg-1.0.0.ebuild', {}, 'master'),
        # No branch found
        ('https://github.com/user/repo', 'cat/pkg-1.0.0.ebuild', {}, ''),
    ])
def test_get_branch(mocker: MockerFixture, url: str, ebuild: str, branches_dict: Mapping[str, str],
                    expected_branch: str) -> None:
    mocker.patch('livecheck.special.github.catpkg_catpkgsplit',
                 return_value=('cat/pkg', None, None, None))
    if url.endswith('/abcdef'):
        mocker.patch('livecheck.special.github.is_sha', return_value=True)
    else:
        mocker.patch('livecheck.special.github.is_sha', return_value=False)
    settings = mocker.Mock()
    settings.branches = branches_dict
    assert get_branch(url, ebuild, settings) == expected_branch


@pytest.mark.parametrize(
    ('url', 'ebuild', 'branch', 'force_sha', 'last_version', 'top_hash', 'hash_date', 'expected'),
    [
        # Case: branch found, get_latest_github_commit returns values, force_sha True
        (
            'https://github.com/user/repo',
            'cat/repo-1.0.0.ebuild',
            'main',
            True,
            '',  # last_version
            'abc123',
            '20240601',
            ('', 'abc123', '20240601'),
        ),
        # Case: branch found, get_latest_github_commit returns values, force_sha False
        (
            'https://github.com/user/repo',
            'cat/repo-1.0.0.ebuild',
            'main',
            False,
            '',  # last_version
            'abc123',
            '20240601',
            ('', '', '20240601'),
        ),
        # Case: no branch, get_latest_github_package returns values, force_sha True
        (
            'https://github.com/user/repo',
            'cat/repo-2.0.0.ebuild',
            '',
            True,
            '2.0.0',
            'deadbeef',
            '',
            ('2.0.0', 'deadbeef', ''),
        ),
        # Case: no branch, get_latest_github_package returns values, force_sha False
        (
            'https://github.com/user/repo',
            'cat/repo-2.0.0.ebuild',
            '',
            False,
            '2.0.0',
            'deadbeef',
            '',
            ('2.0.0', '', ''),
        ),
        # Case: branch found, get_latest_github_commit returns empty, force_sha True
        (
            'https://github.com/user/repo',
            'cat/repo-3.0.0.ebuild',
            'dev',
            True,
            '',
            '',
            '',
            ('', '', ''),
        ),
        # Case: no branch, get_latest_github_package returns empty, force_sha True
        (
            'https://github.com/user/repo',
            'cat/repo-4.0.0.ebuild',
            '',
            True,
            '',
            '',
            '',
            ('', '', ''),
        ),
    ])
def test_get_latest_github(
        mocker: MockerFixture,
        url: str,
        ebuild: str,
        branch: str,
        force_sha: bool,  # noqa: FBT001
        last_version: str,
        top_hash: str,
        hash_date: str,
        expected: tuple[str, str, str]) -> None:
    mocker.patch('livecheck.special.github.get_branch', return_value=branch)
    mock_commit = mocker.patch('livecheck.special.github.get_latest_github_commit')
    mock_package = mocker.patch('livecheck.special.github.get_latest_github_package')
    if branch:
        mock_commit.return_value = (top_hash, hash_date)
    else:
        mock_package.return_value = (last_version, top_hash)
    settings = mocker.Mock()
    result = get_latest_github(url, ebuild, settings, force_sha=force_sha)
    assert result == expected


@pytest.mark.parametrize(
    ('remote', 'ebuild', 'owner', 'repo', 'expected_version', 'expected_sha'),
    [
        (
            'username/repo',
            'cat/repo-1.0.0.ebuild',
            'username',
            'repo',
            '1.0.0',
            'deadbeef1234567890',
        ),
        (
            'username/repo',
            'cat/repo-2.0.0.ebuild',
            '',  # owner
            '',  # repo
            '',  # expected_version
            '',  # expected_sha
        ),
    ])
def test_get_latest_github_metadata(mocker: MockerFixture, remote: str, ebuild: str, owner: str,
                                    repo: str, expected_version: str, expected_sha: str) -> None:
    mock_get_latest_github_package = mocker.patch(
        'livecheck.special.github.get_latest_github_package')
    mock_settings = mocker.Mock()
    mock_url = f'https://github.com/{remote}'
    if owner and repo:
        mock_get_latest_github_package.return_value = (expected_version, expected_sha)
    else:
        mock_get_latest_github_package.return_value = ('', '')
    result = get_latest_github_metadata(remote, ebuild, mock_settings)
    assert result == (expected_version, expected_sha)
    mock_get_latest_github_package.assert_called_once_with(mock_url, ebuild, mock_settings)
