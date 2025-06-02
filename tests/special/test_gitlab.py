from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.special.gitlab import (
    extract_domain_and_namespace,
    get_latest_gitlab,
    get_latest_gitlab_metadata,
    is_gitlab,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

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
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_domain_and_namespace(test_case: dict[str, Any]) -> None:
    assert extract_domain_and_namespace(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_gitlab(test_case: dict[str, Any]) -> None:
    assert is_gitlab(test_case['url']) == test_case['is_gitlab']


@pytest.mark.parametrize(('url', 'ebuild', 'force_sha', 'content_return', 'expected_version',
                          'expected_hash', 'expected_date'), [
                              (
                                  'https://gitlab.com/group/project',
                                  'project-1.0.ebuild',
                                  False,
                                  [{
                                      'name': 'v2.0',
                                      'commit': {
                                          'id': 'abc123'
                                      }
                                  }],
                                  '2.0',
                                  '',
                                  '',
                              ),
                              (
                                  'https://gitlab.com/group/project',
                                  'project-1.0.ebuild',
                                  True,
                                  [{
                                      'name': 'v2.0',
                                      'commit': {
                                          'id': 'abc123'
                                      }
                                  }],
                                  '2.0',
                                  'abc123',
                                  '',
                              ),
                              (
                                  'https://gitlab.com/group/project',
                                  'project-1.0.ebuild',
                                  False,
                                  [],
                                  '',
                                  '',
                                  '',
                              ),
                          ])
def test_get_latest_gitlab(
        mocker: MockerFixture,
        url: str,
        ebuild: str,
        force_sha: bool,  # noqa: FBT001
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
    result = get_latest_gitlab(url, ebuild, mocker.Mock(), force_sha=force_sha)
    assert result == (expected_version, expected_hash, expected_date)
    assert not log_unhandled_commit.called


def test_get_latest_gitlab_package_no_content(mocker: MockerFixture) -> None:
    url = 'https://gitlab.com/group/project'
    ebuild = 'project-1.0.ebuild'
    mocker.patch('livecheck.special.gitlab.get_content', return_value=None)
    result = get_latest_gitlab(url, ebuild, mocker.Mock(), force_sha=False)
    assert result == ('', '', '')


def test_get_latest_gitlab_with_sha(mocker: MockerFixture) -> None:
    url = 'https://gitlab.com/group/project/commit/abc123'
    ebuild = 'project-1.0.ebuild'
    mocker.patch('livecheck.special.gitlab.is_sha', return_value=True)
    log_unhandled_commit = mocker.patch('livecheck.special.gitlab.log_unhandled_commit')
    result = get_latest_gitlab(url, ebuild, mocker.Mock(), force_sha=False)
    assert result == ('', '', '')
    log_unhandled_commit.assert_called_once_with(ebuild, url)


@pytest.mark.parametrize(
    ('remote', '_type', 'ebuild', 'package_return', 'expected'),
    [
        (
            'group/project',
            'gitlab',
            'project-1.0.ebuild',
            ('2.0', 'abc123'),
            ('2.0', 'abc123'),
        ),
        (
            'fhdk/udev-usb-sync',
            'manjaro-gitlab',
            'udev-usb-sync-1.0.ebuild',
            ('1.5', 'def456'),
            ('1.5', 'def456'),
        ),
        (
            'xdg/xdg-utils',
            'freedesktop-gitlab',
            'xdg-utils-1.2.1.ebuild',
            ('', ''),
            ('', ''),
        ),
    ],
)
def test_get_latest_gitlab_metadata(mocker: MockerFixture, remote: str, _type: str, ebuild: str,
                                    package_return: tuple[str, str], expected: tuple[str,
                                                                                     str]) -> None:
    mocker.patch(
        'livecheck.special.gitlab.get_latest_gitlab_package',
        return_value=package_return,
    )
    result = get_latest_gitlab_metadata(remote, _type, ebuild, mocker.Mock())
    assert result == expected
