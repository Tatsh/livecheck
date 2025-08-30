# ruff: noqa: FBT001
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from livecheck.special.bitbucket import (
    extract_workspace_and_repository,
    get_latest_bitbucket,
    get_latest_bitbucket_metadata,
    get_latest_bitbucket_package,
    is_bitbucket,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

test_cases = {
    'atlassian': {
        'url': 'https://bitbucket.org/atlassian/python-bitbucket',
        'expected': ('atlassian', 'python-bitbucket'),
        'is_bitbucket': True
    },
    'atlassian_master': {
        'url': 'https://bitbucket.org/atlassian/python-bitbucket/src/master/',
        'expected': ('atlassian', 'python-bitbucket'),
        'is_bitbucket': True
    },
    'bad_url': {
        'url': 'https://bitbucket.org/',
        'expected': ('', ''),
        'is_bitbucket': False
    },
    'bad_url2': {
        'url': 'https://github.io/username/repo.git',
        'expected': ('', ''),
        'is_bitbucket': False
    },
    'bad_url3': {
        'url': 'https://bitbucket.org/atlassian/',
        'expected': ('', ''),
        'is_bitbucket': False
    },
    'bitbucket_repo_git': {
        'url': 'https://bitbucket.org/atlassian/python-bitbucket.git',
        'expected': ('atlassian', 'python-bitbucket'),
        'is_bitbucket': True
    },
    'media-plugins/vdr-dvbhddevice': {
        'url': 'https://bitbucket.org/powARman/dvbhddevice/get/20170225.tar.bz2',
        'expected': ('powARman', 'dvbhddevice'),
        'is_bitbucket': True
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_extract_owner_repo(test_case: dict[str, Any]) -> None:
    assert extract_workspace_and_repository(test_case['url']) == test_case['expected']


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_is_github(test_case: dict[str, Any]) -> None:
    assert is_bitbucket(test_case['url']) == test_case['is_bitbucket']


def make_mock_response(json_data: Any, *, ok: bool = True) -> Any:
    @dataclass
    class MockResponse:
        ok: bool = True

        def json(self) -> Any:  # noqa: PLR6301
            return json_data

    return MockResponse(ok=ok)


def test_get_latest_bitbucket_package_tags_only(mocker: MockerFixture) -> None:
    # Simulate tags response with two tags
    tags_json = {
        'values': [
            {
                'name': 'v1.0.0',
                'target': {
                    'hash': 'abc123'
                }
            },
            {
                'name': 'v2.0.0',
                'target': {
                    'hash': 'def456'
                }
            },
        ]
    }
    downloads_json: dict[str, Any] = {'values': []}
    mock_get_content = mocker.patch(
        'livecheck.special.bitbucket.get_content',
        side_effect=[
            make_mock_response(tags_json),  # tags
            make_mock_response(downloads_json),  # downloads
        ])
    mock_get_last_version = mocker.patch('livecheck.special.bitbucket.get_last_version',
                                         return_value={
                                             'version': 'v2.0.0',
                                             'id': 'def456'
                                         })
    url = 'https://bitbucket.org/atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-2.0.0'
    version, commit = get_latest_bitbucket_package(url, cpv, mocker.Mock())
    assert version == 'v2.0.0'
    assert commit == 'def456'
    assert mock_get_content.call_count == 2
    assert mock_get_last_version.called


def test_get_latest_bitbucket_package_downloads(mocker: MockerFixture) -> None:
    tags_json: dict[str, Any] = {'values': []}
    downloads_json = {
        'values': [
            {
                'name': 'python-bitbucket-3.0.0.tar.gz'
            },
            {
                'name': 'python-bitbucket-2.5.0.zip'
            },
        ],
        'next': None
    }
    mock_get_content = mocker.patch(
        'livecheck.special.bitbucket.get_content',
        side_effect=[
            make_mock_response(tags_json),  # tags
            make_mock_response(downloads_json),  # downloads
        ])
    mock_get_last_version = mocker.patch('livecheck.special.bitbucket.get_last_version',
                                         return_value={
                                             'version': '3.0.0',
                                             'id': ''
                                         })
    url = 'https://bitbucket.org/atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-3.0.0'
    version, commit = get_latest_bitbucket_package(url, cpv, mocker.Mock())
    assert version == '3.0.0'
    assert not commit
    assert mock_get_content.call_count == 2
    assert mock_get_last_version.called


def test_get_latest_bitbucket_package_response_not_ok(mocker: MockerFixture) -> None:
    tags_json: dict[str, Any] = {'values': []}
    mock_get_content = mocker.patch(
        'livecheck.special.bitbucket.get_content',
        side_effect=[
            make_mock_response(tags_json),  # tags
            make_mock_response({}, ok=False),  # downloads
        ])
    mock_get_last_version = mocker.patch('livecheck.special.bitbucket.get_last_version',
                                         return_value={
                                             'version': '3.0.0',
                                             'id': ''
                                         })
    url = 'https://bitbucket.org/atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-3.0.0'
    version, commit = get_latest_bitbucket_package(url, cpv, mocker.Mock())
    assert version == '3.0.0'
    assert not commit
    assert mock_get_content.call_count == 2
    assert mock_get_last_version.called


def test_get_latest_bitbucket_package_no_tags_no_downloads(mocker: MockerFixture) -> None:
    tags_json: dict[str, Any] = {'values': []}
    downloads_json: dict[str, Any] = {'values': [], 'next': None}
    mock_get_content = mocker.patch(
        'livecheck.special.bitbucket.get_content',
        side_effect=[
            make_mock_response(tags_json),  # tags
            make_mock_response(downloads_json),  # downloads
        ])
    mock_get_last_version = mocker.patch('livecheck.special.bitbucket.get_last_version',
                                         return_value=None)
    url = 'https://bitbucket.org/atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-0.0.1'
    version, commit = get_latest_bitbucket_package(url, cpv, mocker.Mock())
    assert not version
    assert not commit
    assert mock_get_content.call_count == 2
    assert mock_get_last_version.called


def test_get_latest_bitbucket_package_get_content_fails(mocker: MockerFixture) -> None:
    mock_get_content = mocker.patch('livecheck.special.bitbucket.get_content', return_value=None)
    url = 'https://bitbucket.org/atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-0.0.1'
    version, commit = get_latest_bitbucket_package(url, cpv, mocker.Mock())
    assert not version
    assert not commit
    mock_get_content.assert_called_once()


@pytest.mark.parametrize(
    ('url', 'cpv', 'force_sha', 'is_sha_return', 'expected_version', 'expected_top_hash',
     'expected_hash_date'),
    [
        (
            'https://bitbucket.org/atlassian/python-bitbucket',
            'dev-python/bitbucket-2.0.0',
            False,
            False,
            'v2.0.0',
            '',
            '',
        ),
        (
            'https://bitbucket.org/atlassian/python-bitbucket',
            'dev-python/bitbucket-2.0.0',
            True,
            False,
            'v2.0.0',
            'def456',
            '',
        ),
        (
            'https://bitbucket.org/atlassian/python-bitbucket/commit/abc123',
            'dev-python/bitbucket-2.0.0',
            False,
            True,
            '',
            '',
            '',
        ),
    ],
)
def test_get_latest_bitbucket(mocker: MockerFixture, url: str, cpv: str, force_sha: bool,
                              is_sha_return: bool, expected_version: str, expected_top_hash: str,
                              expected_hash_date: str) -> None:
    # Patch is_sha to control commit detection
    mocker.patch('livecheck.special.bitbucket.is_sha', return_value=is_sha_return)
    mock_log_unhandled_commit = mocker.patch('livecheck.special.bitbucket.log_unhandled_commit')
    mock_get_latest_bitbucket_package = mocker.patch(
        'livecheck.special.bitbucket.get_latest_bitbucket_package',
        return_value=('v2.0.0', 'def456'),
    )

    version, top_hash, hash_date = get_latest_bitbucket(url,
                                                        cpv,
                                                        mocker.Mock(),
                                                        force_sha=force_sha)

    if is_sha_return:
        mock_log_unhandled_commit.assert_called_once_with(cpv, url)
        mock_get_latest_bitbucket_package.assert_not_called()
        assert not version
        assert not top_hash
        assert hash_date == expected_hash_date
    else:
        mock_log_unhandled_commit.assert_not_called()
        mock_get_latest_bitbucket_package.assert_called_once_with(url, cpv, mocker.ANY)
        assert version == expected_version
        assert top_hash == expected_top_hash
        assert hash_date == expected_hash_date


def test_get_latest_bitbucket_metadata(mocker: MockerFixture) -> None:
    mock_get_latest_bitbucket_package = mocker.patch(
        'livecheck.special.bitbucket.get_latest_bitbucket_package',
        return_value=('v2.0.0', 'def456'),
    )
    remote = 'atlassian/python-bitbucket'
    cpv = 'dev-python/bitbucket-2.0.0'
    version, commit = get_latest_bitbucket_metadata(remote, cpv, mocker.Mock())
    assert version == 'v2.0.0'
    assert commit == 'def456'
    mock_get_latest_bitbucket_package.assert_called_once_with(f'https://bitbucket.org/{remote}',
                                                              cpv, mocker.ANY)
