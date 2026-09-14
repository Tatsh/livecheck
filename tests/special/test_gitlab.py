from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from livecheck.special.gitlab import (
    extract_domain_and_namespace,
    get_latest_gitlab,
    get_latest_gitlab_commit,
    get_latest_gitlab_metadata,
    is_gitlab,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

SHA = '476c7fc8cb563364c9eb53d5ad5b4746804b460b'

test_cases = {
    'valid_gitlab_url': {
        'url': 'https://gitlab.com/group/project',
        'expected': ('gitlab.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'invalid_gitlab_url': {
        'url': 'https://notgitlab.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'invalid_gitlab_url2': {
        'url': 'https://gitlab.com',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'invalid_gitlab_url3': {
        'url': 'https://gitlab.com/group/',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_es_url': {
        'url': 'https://gitlab.es/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'example_gitlab_url': {
        'url': 'https://example.gitlab.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_example_url': {
        'url': 'https://gitlab.example.com/group/project',
        'expected': ('gitlab.example.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'example_com_url': {
        'url': 'https://example.com/group/project',
        'expected': ('', '', ''),
        'is_gitlab': False
    },
    'gitlab_merge_request_url': {
        'url': 'https://gitlab.com/group/project/-/merge_requests',
        'expected': ('gitlab.com', 'group/project', 'project'),
        'is_gitlab': True
    },
    'gitlab_subgroup_url': {
        'url': 'https://gitlab.com/group/subgroup/project',
        'expected': ('gitlab.com', 'group/subgroup/project', 'project'),
        'is_gitlab': True
    },
    'sys-apps/udev-usb-sync': {
        'url': 'https://gitlab.manjaro.org/fhdk/udev-usb-sync',
        'expected': ('gitlab.manjaro.org', 'fhdk/udev-usb-sync', 'udev-usb-sync'),
        'is_gitlab': True
    },
    'x11-misc/xdg-utils': {
        'url':
            'https://gitlab.freedesktop.org/xdg/xdg-utils/-/archive/v1.2.1/xdg-utils-1.2.1.tar.bz2',
        'expected': ('gitlab.freedesktop.org', 'xdg/xdg-utils', 'xdg-utils'),
        'is_gitlab':
            True
    },
    'api_archive_url': {
        'url': ('https://gitlab.com/api/v4/projects/cscs%2Fmaxperfwiz/repository/archive.tar.bz2'
                '?sha=476c7fc8cb563364c9eb53d5ad5b4746804b460b'),
        'expected': ('gitlab.com', 'cscs/maxperfwiz', 'maxperfwiz'),
        'is_gitlab': True
    },
    'api_project_url': {
        'url': 'https://gitlab.com/api/v4/projects/group%2Fsubgroup%2Fproject',
        'expected': ('gitlab.com', 'group/subgroup/project', 'project'),
        'is_gitlab': True
    }
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_domain_and_namespace(test_case: dict[str, Any]) -> None:
    assert extract_domain_and_namespace(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_gitlab(test_case: dict[str, Any]) -> None:
    assert is_gitlab(test_case['url']) == test_case['is_gitlab']


@pytest.mark.parametrize(
    ('url', 'ebuild', 'force_sha', 'content_return', 'expected_version', 'expected_hash',
     'expected_date'),
    [('https://gitlab.com/group/project', 'project-1.0.ebuild', False, [{
        'name': 'v2.0',
        'commit': {
            'id': 'abc123'
        }
    }], '2.0', '', ''),
     ('https://gitlab.com/group/project', 'project-1.0.ebuild', True, [{
         'name': 'v2.0',
         'commit': {
             'id': 'abc123'
         }
     }], '2.0', 'abc123', ''),
     ('https://gitlab.com/group/project', 'project-1.0.ebuild', False, [], '', '', '')])
@pytest.mark.asyncio
async def test_get_latest_gitlab(
        mocker: MockerFixture,
        url: str,
        ebuild: str,
        force_sha: bool,  # ruff:ignore[boolean-type-hint-positional-argument]
        content_return: str,
        expected_version: str,
        expected_hash: str,
        expected_date: str) -> None:
    mock_content = mocker.Mock()
    mock_content.json.return_value = content_return
    mocker.patch('livecheck.special.gitlab.get_content', return_value=mock_content)
    if content_return:
        mocker.patch('livecheck.special.gitlab.get_last_version',
                     return_value={
                         'version': '2.0',
                         'id': 'abc123'
                     })
    else:
        mocker.patch('livecheck.special.gitlab.get_last_version', return_value=None)
    mocker.patch('livecheck.utils.is_sha', return_value=False)
    log_unhandled_commit = mocker.patch('livecheck.special.gitlab.log_unhandled_commit')
    result = await get_latest_gitlab(url, ebuild, mocker.Mock(), force_sha=force_sha)
    assert result == (expected_version, expected_hash, expected_date)
    assert not log_unhandled_commit.called


@pytest.mark.asyncio
async def test_get_latest_gitlab_package_archive_url(mocker: MockerFixture) -> None:
    mock_content = mocker.Mock()
    mock_content.json.return_value = []
    mocker.patch('livecheck.special.gitlab.get_content', return_value=mock_content)
    mock_get_last_version = mocker.patch('livecheck.special.gitlab.get_last_version',
                                         return_value=None)
    mocker.patch('livecheck.special.gitlab.is_sha', return_value=False)
    url = 'https://gitlab.freedesktop.org/xdg/xdg-utils/-/archive/v1.2.1/xdg-utils-1.2.1.tar.bz2'
    result = await get_latest_gitlab(url, 'xdg-utils-1.2.1.ebuild', mocker.Mock(), force_sha=False)
    assert result == ('', '', '')
    assert mock_get_last_version.call_args.kwargs.get('version_reference') == 'v1.2.1'


@pytest.mark.asyncio
async def test_get_latest_gitlab_package_no_content(mocker: MockerFixture) -> None:
    url = 'https://gitlab.com/group/project'
    ebuild = 'project-1.0.ebuild'
    mocker.patch('livecheck.special.gitlab.get_content', return_value=None)
    result = await get_latest_gitlab(url, ebuild, mocker.Mock(), force_sha=False)
    assert result == ('', '', '')


@pytest.mark.parametrize(
    'url',
    [
        'https://gitlab.com/group/project/-/archive/' + SHA + f'/project-{SHA}.tar.bz2',
        # The API route carries the commit in the query string instead of the path.
        f'https://gitlab.com/api/v4/projects/group%2Fproject/repository/archive.tar.bz2?sha={SHA}',
    ],
    ids=['web', 'api'])
@pytest.mark.asyncio
async def test_get_latest_gitlab_with_sha(mocker: MockerFixture, url: str) -> None:
    ebuild = 'category/project-20250630'
    mock_commit = mocker.patch('livecheck.special.gitlab.get_latest_gitlab_commit',
                               return_value=(SHA, '20250630'))
    result = await get_latest_gitlab(url,
                                     ebuild,
                                     mocker.Mock(branches={'category/project': 'main'}),
                                     force_sha=False)
    assert result == ('', SHA, '20250630')
    assert mock_commit.call_args.args[1] == 'main'


@pytest.mark.asyncio
async def test_get_latest_gitlab_with_sha_no_commit(mocker: MockerFixture) -> None:
    url = f'https://gitlab.com/group/project/-/archive/{SHA}/project-{SHA}.tar.bz2'
    ebuild = 'category/project-20250630'
    mocker.patch('livecheck.special.gitlab.get_latest_gitlab_commit', return_value=('', ''))
    log_unhandled_commit = mocker.patch('livecheck.special.gitlab.log_unhandled_commit')
    result = await get_latest_gitlab(url, ebuild, mocker.Mock(branches={}), force_sha=False)
    assert result == ('', '', '')
    log_unhandled_commit.assert_called_once_with(ebuild, url)


@pytest.mark.asyncio
async def test_get_latest_gitlab_commit_not_gitlab(mocker: MockerFixture) -> None:
    mock_get_content = mocker.patch('livecheck.special.gitlab.get_content')
    assert await get_latest_gitlab_commit('https://example.com/group/project') == ('', '')
    mock_get_content.assert_not_called()


@pytest.mark.asyncio
async def test_get_latest_gitlab_commit_explicit_branch(mocker: MockerFixture) -> None:
    mock_content = mocker.Mock()
    mock_content.json.return_value = [{'id': SHA, 'created_at': '2025-06-30T03:42:58.000-07:00'}]
    mock_get_content = mocker.patch('livecheck.special.gitlab.get_content',
                                    return_value=mock_content)
    assert await get_latest_gitlab_commit('https://gitlab.com/group/project',
                                          'main') == (SHA, '20250630')
    # The default branch is already known, so only the commits endpoint is requested.
    mock_get_content.assert_called_once_with(
        'https://gitlab.com/api/v4/projects/group%2Fproject/repository/commits'
        '?ref_name=main&per_page=1')


@pytest.mark.asyncio
async def test_get_latest_gitlab_commit_default_branch(mocker: MockerFixture) -> None:
    mock_project = mocker.Mock()
    mock_project.json.return_value = {'default_branch': 'trunk'}
    mock_commits = mocker.Mock()
    mock_commits.json.return_value = [{'id': SHA, 'created_at': '2025-06-30T03:42:58.000-07:00'}]
    mock_get_content = mocker.patch('livecheck.special.gitlab.get_content',
                                    side_effect=[mock_project, mock_commits])
    assert await get_latest_gitlab_commit('https://gitlab.com/group/project') == (SHA, '20250630')
    assert 'ref_name=trunk' in mock_get_content.call_args.args[0]


@pytest.mark.parametrize(('project_json', 'commits_json'), [({}, None),
                                                            ({
                                                                'default_branch': 'main'
                                                            }, [])],
                         ids=['no-default-branch', 'no-commits'])
@pytest.mark.asyncio
async def test_get_latest_gitlab_commit_no_result(mocker: MockerFixture, project_json: dict[str,
                                                                                            str],
                                                  commits_json: list[Any] | None) -> None:
    mock_project = mocker.Mock()
    mock_project.json.return_value = project_json
    mock_commits = mocker.Mock()
    mock_commits.json.return_value = commits_json
    mocker.patch('livecheck.special.gitlab.get_content', side_effect=[mock_project, mock_commits])
    assert await get_latest_gitlab_commit('https://gitlab.com/group/project') == ('', '')


@pytest.mark.parametrize('branch', ['main', ''], ids=['explicit-branch', 'default-branch'])
@pytest.mark.asyncio
async def test_get_latest_gitlab_commit_no_content(mocker: MockerFixture, branch: str) -> None:
    mocker.patch('livecheck.special.gitlab.get_content', return_value=None)
    assert await get_latest_gitlab_commit('https://gitlab.com/group/project', branch) == ('', '')


@pytest.mark.parametrize(
    ('remote', '_type', 'ebuild', 'package_return', 'expected'),
    [('group/project', 'gitlab', 'project-1.0.ebuild', ('2.0', 'abc123'), ('2.0', 'abc123')),
     ('fhdk/udev-usb-sync', 'manjaro-gitlab', 'udev-usb-sync-1.0.ebuild', ('1.5', 'def456'),
      ('1.5', 'def456')),
     ('xdg/xdg-utils', 'freedesktop-gitlab', 'xdg-utils-1.2.1.ebuild', ('', ''), ('', ''))])
@pytest.mark.asyncio
async def test_get_latest_gitlab_metadata(mocker: MockerFixture, remote: str, _type: str,
                                          ebuild: str, package_return: tuple[str, str],
                                          expected: tuple[str, str]) -> None:
    mocker.patch('livecheck.special.gitlab.get_latest_gitlab_package', return_value=package_return)
    result = await get_latest_gitlab_metadata(remote, _type, ebuild, mocker.Mock())
    assert result == expected
