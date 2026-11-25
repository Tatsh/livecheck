# ruff:file-ignore[hardcoded-temp-file]
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import tarfile

import pytest

from livecheck.dist_github import DistGitHubSettings
from livecheck.special.nodejs import (
    check_nodejs_requirements,
    remove_nodejs_url,
    update_nodejs_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from pytest_mock import MockerFixture


def _package(root: Path, lockfile: str | None = 'pnpm-lock.yaml') -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / 'package.json').write_text('{}', encoding='utf-8')
    if lockfile:
        (root / lockfile).write_text('lockfileVersion: 9\n', encoding='utf-8')
    return root


def _patch_install(mocker: MockerFixture, returncode: int = 0) -> AsyncMock:
    def _create(*_args: str, cwd: Path, env: Mapping[str, str] | None) -> MagicMock:
        (cwd / 'node_modules' / 'dep').mkdir(parents=True, exist_ok=True)
        (cwd / 'node_modules' / 'dep' / 'index.js').write_text('', encoding='utf-8')
        proc: MagicMock = mocker.MagicMock()
        proc.wait = AsyncMock(return_value=returncode)
        return proc

    return mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                        new_callable=AsyncMock,
                        side_effect=_create)


def _patch_unpack(mocker: MockerFixture, package: Path, workdir: Path, distdir: Path) -> AsyncMock:
    distdir.mkdir(exist_ok=True)
    mocker.patch('livecheck.special.nodejs.get_distdir', return_value=distdir)
    mocker.patch('livecheck.special.utils.get_distdir', return_value=distdir)
    return mocker.patch('livecheck.special.nodejs.search_ebuild',
                        new_callable=AsyncMock,
                        return_value=(str(package), str(workdir)))


def _members(archive: Path) -> list[str]:
    with tarfile.open(archive) as tar:
        return tar.getnames()


def test_remove_nodejs_url_removes_node_modules_line() -> None:
    ebuild_content = """
SRC_URI="https://example.com/foo.tar.gz
https://example.com/foo-node_modules.tar.xz"
"""
    result = remove_nodejs_url(ebuild_content)
    assert '-node_modules.tar.xz' not in result
    assert 'foo.tar.gz' in result


def test_remove_nodejs_url_no_node_modules_line() -> None:
    ebuild_content = """
SRC_URI="https://example.com/foo.tar.gz"
"""
    result = remove_nodejs_url(ebuild_content)
    assert result == ebuild_content


def test_remove_nodejs_url_multiple_node_modules_lines() -> None:
    ebuild_content = """
SRC_URI="https://example.com/foo-node_modules.tar.xz
https://example.com/bar-node_modules.tar.xz
https://example.com/baz.tar.gz"
"""
    result = remove_nodejs_url(ebuild_content)
    assert '-node_modules.tar.xz' not in result
    assert 'baz.tar.gz' in result


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_version_archive(mocker: MockerFixture, tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0', lockfile=None)
    search = _patch_unpack(mocker, package, workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild', '/some/path',
                                        {'foo-1.0.tar.gz': ('https://example.com',)})

    assert result is None
    search.assert_called_once_with('foo/foo-1.0.ebuild', 'package.json', '/some/path')
    create.assert_called_once()
    assert create.call_args.kwargs['env'] is None
    assert _members(tmp_path / 'distfiles' / 'foo-1.0-node_modules.tar.xz') == [
        'foo-1.0/node_modules', 'foo-1.0/node_modules/dep', 'foo-1.0/node_modules/dep/index.js'
    ]


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_workspaces_single_archive(mocker: MockerFixture,
                                                              tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    _package(package / 'mobile')
    (package / 'vendor' / 'node_modules').mkdir(parents=True)
    _patch_unpack(mocker, package, workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                               None, {'foo-1.0.tar.gz': ('https://example.com',)},
                               'pnpm',
                               workspaces=('mobile',))

    assert [call.kwargs['cwd'] for call in create.call_args_list] == [package, package / 'mobile']
    members = _members(tmp_path / 'distfiles' / 'foo-1.0-node_modules.tar.xz')
    assert 'foo-1.0/mobile/node_modules/dep/index.js' in members
    assert 'foo-1.0/node_modules/dep/index.js' in members
    assert not any(member.startswith('foo-1.0/vendor') for member in members)


@pytest.mark.asyncio
@pytest.mark.parametrize(('lockfile', 'flag'), [('pnpm-lock.yaml', '--frozen-lockfile'),
                                                (None, '--no-frozen-lockfile')])
async def test_update_nodejs_ebuild_pnpm_install(mocker: MockerFixture, tmp_path: Path,
                                                 lockfile: str | None, flag: str) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0', lockfile), workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'foo-1.0.tar.gz': ('x',)}, 'pnpm')

    assert create.call_args.args[-1] == flag
    assert create.call_args.kwargs['env']['CI'] == 'true'


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_archive(mocker: MockerFixture, tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    _package(package / 'mobile')
    distdir = tmp_path / 'distfiles'
    _patch_unpack(mocker, package, workdir, distdir)
    create = _patch_install(mocker)

    digest = await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                                        None, {},
                                        'pnpm',
                                        archive_mode='lockfile',
                                        workspaces=('mobile',))

    assert digest is not None
    assert len(digest) == 16
    assert create.call_count == 2
    assert _members(distdir / f'foo-{digest}-node_modules.tar.xz') == [
        'mobile/node_modules', 'mobile/node_modules/dep', 'mobile/node_modules/dep/index.js',
        'node_modules', 'node_modules/dep', 'node_modules/dep/index.js'
    ]


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_digest_ignores_manifest(mocker: MockerFixture,
                                                                     tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    _patch_unpack(mocker, package, workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    first = await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {}, archive_mode='lockfile')
    (package / 'package.json').write_text('{"version": "1.1"}', encoding='utf-8')
    second = await update_nodejs_ebuild('foo/foo-1.1.ebuild', None, {}, archive_mode='lockfile')
    (package / 'pnpm-lock.yaml').write_text('lockfileVersion: 10\n', encoding='utf-8')
    third = await update_nodejs_ebuild('foo/foo-1.2.ebuild', None, {}, archive_mode='lockfile')

    assert first == second
    assert third not in {None, first}
    assert create.call_count == 2


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_reuses_previous_digest(mocker: MockerFixture,
                                                                    tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    distdir = tmp_path / 'distfiles'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, distdir)
    create = _patch_install(mocker)
    digest = await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {}, archive_mode='lockfile')
    (distdir / f'foo-{digest}-node_modules.tar.xz').unlink()

    result = await update_nodejs_ebuild('foo/foo-1.1.ebuild',
                                        None, {},
                                        archive_mode='lockfile',
                                        previous_digest=digest)

    assert result == digest
    assert create.call_count == 1
    assert not (distdir / f'foo-{digest}-node_modules.tar.xz').exists()


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_needs_lockfile(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    _package(package / 'mobile', lockfile=None)
    _patch_unpack(mocker, package, workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)
    logger = mocker.patch('livecheck.special.nodejs.logger')

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                                        None, {},
                                        archive_mode='lockfile',
                                        workspaces=('mobile',))

    assert result is None
    create.assert_not_called()
    logger.error.assert_called_once_with('There is no lockfile in `%s`.', package / 'mobile')


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_workspace_without_package_json(mocker: MockerFixture,
                                                                   tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    (package / 'mobile').mkdir()
    _patch_unpack(mocker, package, workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)
    logger = mocker.patch('livecheck.special.nodejs.logger')

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {}, workspaces=('mobile',))

    assert result is None
    create.assert_not_called()
    logger.error.assert_called_once_with('There is no `package.json` in the workspace `%s`.',
                                         'mobile')


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_rejects_external_links(mocker: MockerFixture,
                                                           tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    distdir = tmp_path / 'distfiles'
    _patch_unpack(mocker, package, workdir, distdir)
    logger = mocker.patch('livecheck.special.nodejs.logger')

    def _create(*_args: str, cwd: Path, env: Mapping[str, str] | None) -> MagicMock:
        (cwd / 'node_modules').mkdir()
        (cwd / 'node_modules' / 'dep').symlink_to(tmp_path / 'store' / 'dep')
        proc: MagicMock = mocker.MagicMock()
        proc.wait = AsyncMock(return_value=0)
        return proc

    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=_create)

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'foo-1.0.tar.gz': ('x',)})

    assert result is None
    assert not (distdir / 'foo-1.0-node_modules.tar.xz').exists()
    logger.error.assert_called_once_with(
        '`%s` links to `%s` outside of the archive.', 'foo-1.0/node_modules/dep',
        str(tmp_path / 'store' / 'dep'))


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_archives_internal_links(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    package = _package(workdir / 'foo-1.0')
    (package / 'packages' / 'bar').mkdir(parents=True)
    distdir = tmp_path / 'distfiles'
    _patch_unpack(mocker, package, workdir, distdir)

    def _create(*_args: str, cwd: Path, env: Mapping[str, str] | None) -> MagicMock:
        (cwd / 'node_modules').mkdir()
        (cwd / 'node_modules' / 'bar').symlink_to('../packages/bar')
        proc: MagicMock = mocker.MagicMock()
        proc.wait = AsyncMock(return_value=0)
        return proc

    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=_create)

    await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'foo-1.0.tar.gz': ('x',)})

    with tarfile.open(distdir / 'foo-1.0-node_modules.tar.xz') as tar:
        assert tar.getmember('foo-1.0/node_modules/bar').linkname == '../packages/bar'


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_uploads_archive(mocker: MockerFixture, tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    _patch_install(mocker)
    mocker.patch('livecheck.special.nodejs.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=False)
    upload = mocker.patch('livecheck.special.nodejs.upload_dist_archive',
                          new_callable=AsyncMock,
                          return_value=True)
    settings = DistGitHubSettings(force=False, release='dist', repository='owner/repo')

    await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                               None, {'foo-1.0.tar.gz': ('x',)},
                               dist_settings=settings)

    upload.assert_called_once_with(settings, tmp_path / 'distfiles' / 'foo-1.0-node_modules.tar.xz')


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_upload_fails(mocker: MockerFixture,
                                                          tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    _patch_install(mocker)
    mocker.patch('livecheck.special.utils.asset_exists', new_callable=AsyncMock, return_value=False)
    mocker.patch('livecheck.special.utils.upload_dist_archive',
                 new_callable=AsyncMock,
                 return_value=False)
    settings = DistGitHubSettings(force=False, release='dist', repository='owner/repo')

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                                        None, {},
                                        archive_mode='lockfile',
                                        dist_settings=settings)

    assert result is None


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_lockfile_reuses_published_archive(mocker: MockerFixture,
                                                                      tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    distdir = tmp_path / 'distfiles'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, distdir)
    create = _patch_install(mocker)
    asset_exists = mocker.patch('livecheck.special.utils.asset_exists',
                                new_callable=AsyncMock,
                                return_value=True)
    upload = mocker.patch('livecheck.special.utils.upload_dist_archive', new_callable=AsyncMock)
    settings = DistGitHubSettings(force=True, release='dist', repository='owner/repo')

    digest = await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                                        None, {},
                                        archive_mode='lockfile',
                                        dist_settings=settings)

    assert digest is not None
    asset_exists.assert_awaited_once_with(settings, f'foo-{digest}-node_modules.tar.xz')
    create.assert_not_called()
    upload.assert_not_called()
    assert not list(distdir.iterdir())


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_skips_when_archive_uploaded(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.nodejs.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=True)
    search = mocker.patch('livecheck.special.nodejs.search_ebuild', new_callable=AsyncMock)
    await update_nodejs_ebuild('ebuild', 'path', {'foo': ('bar',)})
    search.assert_not_called()


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_no_package_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock,
                                      return_value=('', ''))
    mock_create = mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)

    assert await update_nodejs_ebuild('dummy.ebuild', None, {}) is None

    mock_search_ebuild.assert_called_once()
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_npm_install_fails(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    _patch_install(mocker, returncode=1)
    logger = mocker.patch('livecheck.special.nodejs.logger')

    result = await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'foo-1.0.tar.gz': ('x',)})

    assert result is None
    assert not (tmp_path / 'distfiles' / 'foo-1.0-node_modules.tar.xz').exists()
    logger.error.assert_called_once_with("Error running '%s install'.", 'npm')


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_subprocess_raises_os_error(mocker: MockerFixture,
                                                               tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    logger = mocker.patch('livecheck.special.nodejs.logger')
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=OSError('npm failed'))

    assert await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'f.tar.gz': ('x',)}) is None
    assert logger.exception.called


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_no_archive_name(mocker: MockerFixture, tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    assert await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {}) is None
    create.assert_not_called()


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_vendor_not_created(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    logger = mocker.patch('livecheck.special.nodejs.logger')
    proc = mocker.MagicMock()
    proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=proc)

    assert await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'f.tar.gz': ('x',)}) is None
    logger.warning.assert_called_once_with('The directory vendor was not created.')


@pytest.mark.asyncio
@pytest.mark.parametrize(('package_manager', 'flag'), [('npm', '--omit=dev'),
                                                       ('yarn', '--production'),
                                                       ('pnpm', '--prod')])
async def test_update_nodejs_ebuild_omit_dev(mocker: MockerFixture, tmp_path: Path,
                                             package_manager: str, flag: str) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    await update_nodejs_ebuild('foo/foo-1.0.ebuild',
                               None, {'foo-1.0.tar.gz': ('x',)},
                               package_manager=package_manager,
                               omit_dev=True)

    assert create.call_args.args[-1] == flag


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_keeps_dev_by_default(mocker: MockerFixture,
                                                         tmp_path: Path) -> None:
    workdir = tmp_path / 'work'
    _patch_unpack(mocker, _package(workdir / 'foo-1.0'), workdir, tmp_path / 'distfiles')
    create = _patch_install(mocker)

    await update_nodejs_ebuild('foo/foo-1.0.ebuild', None, {'foo-1.0.tar.gz': ('x',)})

    assert '--omit=dev' not in create.call_args.args


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_invalid_package_manager(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_create = mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)

    mock_search_ebuild.return_value = ('/tmp/pkg', '/tmp/tmpdir')

    await update_nodejs_ebuild('dummy.ebuild', None, {}, package_manager='invalid')

    mock_create.assert_not_called()
    mock_logger.error.assert_called_once_with('Unsupported package manager: %s', 'invalid')


def test_check_nodejs_requirements_success(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.nodejs.check_program')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_check_program.return_value = True

    result = check_nodejs_requirements('pnpm')

    mock_check_program.assert_called_once_with('pnpm', ['--version'])
    assert result is True
    mock_logger.error.assert_not_called()


def test_check_nodejs_requirements_failure(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.nodejs.check_program')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_check_program.return_value = False

    result = check_nodejs_requirements()

    mock_check_program.assert_called_once_with('npm', ['--version'])
    assert result is False
    mock_logger.error.assert_called_once_with('%s is not installed', 'npm')


def test_check_nodejs_requirements_invalid_manager(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.nodejs.check_program')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')

    result = check_nodejs_requirements('invalid')

    assert result is False
    mock_check_program.assert_not_called()
    mock_logger.error.assert_called_once_with('Unsupported package manager: %s', 'invalid')
