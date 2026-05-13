from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from livecheck.dist_github import (
    DistGitHubSettings,
    asset_exists,
    parse_repository,
    upload_dist_archive,
)
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _fake_response(status_code: int = HTTPStatus.OK, body: dict[str, Any] | None = None) -> Any:
    response = AsyncMock()
    response.status_code = status_code
    response.ok = HTTPStatus.OK <= status_code < HTTPStatus.MULTIPLE_CHOICES
    response.json = lambda: body or {}
    return response


def _fake_session(mocker: MockerFixture,
                  *,
                  get: Any = None,
                  post: Any = None,
                  delete: Any = None) -> Any:
    session = mocker.Mock()
    session.get = AsyncMock(return_value=get or _fake_response())
    session.post = AsyncMock(return_value=post or _fake_response())
    session.delete = AsyncMock(return_value=delete or _fake_response())
    return session


def test_parse_repository_valid() -> None:
    assert parse_repository('Tatsh/livecheck') == ('Tatsh', 'livecheck')


@pytest.mark.parametrize('spec', ['', 'Tatsh', 'Tatsh/', '/livecheck', 'a/b/c'])
def test_parse_repository_invalid(spec: str) -> None:
    with pytest.raises(ValueError, match='Invalid GitHub repository specifier'):
        parse_repository(spec)


@pytest.mark.asyncio
async def test_asset_exists_true(mocker: MockerFixture) -> None:
    session = _fake_session(
        mocker, get=_fake_response(body={'assets': [{
            'name': 'foo-1.0.0-nuget.tar.xz',
            'id': 42
        }]}))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo-1.0.0-nuget.tar.xz') is True


@pytest.mark.asyncio
async def test_asset_exists_false_when_assets_field_missing(mocker: MockerFixture) -> None:
    session = _fake_session(mocker, get=_fake_response(body={'name': 'release-without-assets'}))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo') is False


@pytest.mark.asyncio
async def test_asset_exists_skips_non_matching_assets(mocker: MockerFixture) -> None:
    session = _fake_session(
        mocker,
        get=_fake_response(body={
            'assets': [{
                'name': 'other.tar.xz',
                'id': 1
            }, {
                'name': 'foo-1.0.0-nuget.tar.xz',
                'id': 2
            }]
        }))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo-1.0.0-nuget.tar.xz') is True


@pytest.mark.asyncio
async def test_asset_exists_false_when_release_missing(mocker: MockerFixture) -> None:
    session = _fake_session(mocker, get=_fake_response(status_code=HTTPStatus.NOT_FOUND))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo-1.0.0-nuget.tar.xz') is False


@pytest.mark.asyncio
async def test_asset_exists_false_when_asset_missing(mocker: MockerFixture) -> None:
    session = _fake_session(mocker, get=_fake_response(body={'assets': []}))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo-1.0.0-nuget.tar.xz') is False


@pytest.mark.asyncio
async def test_asset_exists_invalid_repository_logs_and_returns_false(
        mocker: MockerFixture) -> None:
    mocker.patch('livecheck.dist_github.session_init')
    settings = DistGitHubSettings(repository='invalid', release='dist')
    assert await asset_exists(settings, 'whatever') is False


@pytest.mark.asyncio
async def test_upload_dist_archive_happy_path(mocker: MockerFixture, tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    release_body = {
        'assets': [],
        'upload_url': 'https://uploads.github.com/repos/Tatsh/livecheck/releases/1/assets{?name}'
    }
    session = _fake_session(mocker, get=_fake_response(body=release_body))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is True
    session.post.assert_awaited_once()
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_dist_archive_replaces_existing(mocker: MockerFixture, tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    release_body = {
        'assets': [{
            'name': 'foo-1.0.0-nuget.tar.xz',
            'id': 99
        }],
        'upload_url': 'https://uploads.github.com/repos/Tatsh/livecheck/releases/1/assets{?name}'
    }
    session = _fake_session(mocker, get=_fake_response(body=release_body))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is True
    session.delete.assert_awaited_once()
    session.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_dist_archive_creates_draft_release(mocker: MockerFixture,
                                                         tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    session = _fake_session(
        mocker,
        get=_fake_response(status_code=HTTPStatus.NOT_FOUND),
        post=_fake_response(
            status_code=HTTPStatus.CREATED,
            body={
                'assets': [],
                'upload_url':
                    'https://uploads.github.com/repos/Tatsh/livecheck/releases/1/assets{?name}',
            },
        ))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is True
    assert session.post.await_count == 2


@pytest.mark.asyncio
async def test_upload_dist_archive_returns_false_when_file_missing(mocker: MockerFixture,
                                                                   tmp_path: Path) -> None:
    mocker.patch('livecheck.dist_github.session_init')
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, tmp_path / 'missing.tar.xz') is False


@pytest.mark.asyncio
async def test_asset_exists_false_on_bad_status(mocker: MockerFixture) -> None:
    session = _fake_session(mocker, get=_fake_response(status_code=HTTPStatus.SERVICE_UNAVAILABLE))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await asset_exists(settings, 'foo') is False


@pytest.mark.asyncio
async def test_upload_dist_archive_invalid_repository_returns_false(mocker: MockerFixture,
                                                                    tmp_path: Path) -> None:
    mocker.patch('livecheck.dist_github.session_init')
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    settings = DistGitHubSettings(repository='invalid', release='dist')
    assert await upload_dist_archive(settings, archive) is False


@pytest.mark.asyncio
async def test_upload_dist_archive_returns_false_when_create_release_fails(
        mocker: MockerFixture, tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    session = _fake_session(mocker,
                            get=_fake_response(status_code=HTTPStatus.NOT_FOUND),
                            post=_fake_response(status_code=HTTPStatus.FORBIDDEN))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is False


@pytest.mark.asyncio
async def test_upload_dist_archive_returns_false_when_upload_url_missing(
        mocker: MockerFixture, tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    session = _fake_session(mocker, get=_fake_response(body={'assets': [], 'upload_url': ''}))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is False


@pytest.mark.asyncio
async def test_upload_dist_archive_returns_false_on_upload_failure(mocker: MockerFixture,
                                                                   tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    release_body = {
        'assets': [],
        'upload_url': 'https://uploads.github.com/repos/Tatsh/livecheck/releases/1/assets{?name}',
    }
    session = _fake_session(
        mocker,
        get=_fake_response(body=release_body),
        post=_fake_response(status_code=HTTPStatus.SERVICE_UNAVAILABLE),
    )
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is False


@pytest.mark.asyncio
async def test_upload_dist_archive_returns_false_on_delete_failure(mocker: MockerFixture,
                                                                   tmp_path: Path) -> None:
    archive = tmp_path / 'foo-1.0.0-nuget.tar.xz'
    archive.write_bytes(b'payload')
    release_body = {
        'assets': [{
            'name': 'foo-1.0.0-nuget.tar.xz',
            'id': 99
        }],
        'upload_url': 'https://uploads.github.com/repos/Tatsh/livecheck/releases/1/assets{?name}'
    }
    session = _fake_session(mocker,
                            get=_fake_response(body=release_body),
                            delete=_fake_response(status_code=HTTPStatus.FORBIDDEN))
    mocker.patch('livecheck.dist_github.session_init', return_value=session)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await upload_dist_archive(settings, archive) is False
