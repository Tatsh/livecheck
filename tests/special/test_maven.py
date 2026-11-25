"""Tests for Maven helpers."""
# ruff:file-ignore[hardcoded-temp-file]
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import tarfile

import pytest

from livecheck.special.maven import check_maven_requirements, remove_maven_url, update_maven_ebuild

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_remove_maven_url_calls_remove_url_ebuild(mocker: MockerFixture) -> None:
    mock_remove_url_ebuild = mocker.patch('livecheck.special.maven.remove_url_ebuild')
    mock_remove_url_ebuild.return_value = 'result'
    ebuild_content = 'SOME CONTENT'
    result = remove_maven_url(ebuild_content)
    mock_remove_url_ebuild.assert_called_once_with(ebuild_content, '-mvn.tar.xz')
    assert result == 'result'


def test_remove_maven_url_returns_expected_value(mocker: MockerFixture) -> None:
    expected = 'cleaned content'
    mocker.patch('livecheck.special.maven.remove_url_ebuild', return_value=expected)
    assert remove_maven_url('dummy') == expected


@pytest.mark.asyncio
async def test_update_maven_ebuild_mvn_not_on_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.maven.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = ('/tmp/maven', '/tmp/temp')
    mocker.patch('livecheck.special.maven.which', return_value=None)
    mock_create = mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.maven.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.maven.log')
    await update_maven_ebuild('ebuild', 'path', {})
    mock_create.assert_not_called()
    mock_build_compress.assert_not_called()
    mock_log.error.assert_called_once_with('mvn is not installed')


@pytest.mark.asyncio
async def test_update_maven_ebuild_no_maven_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.maven.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = (None, None)
    mock_create = mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.maven.build_compress',
                                       new_callable=AsyncMock)

    await update_maven_ebuild('ebuild', 'path', {})
    mock_create.assert_not_called()
    mock_build_compress.assert_not_called()


@pytest.mark.asyncio
async def test_update_maven_ebuild_success(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.maven.search_ebuild',
                                      new_callable=AsyncMock)
    maven_path = '/tmp/maven'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (maven_path, temp_dir)
    mvn_exe = '/usr/bin/mvn'
    mocker.patch('livecheck.special.maven.which', return_value=mvn_exe)

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build_compress = mocker.patch('livecheck.special.maven.build_compress',
                                       new_callable=AsyncMock)

    fetchlist = {'foo': ('bar',)}
    await update_maven_ebuild('ebuild', 'path', fetchlist)

    mock_build_compress.assert_called_once_with(temp_dir,
                                                maven_path,
                                                '.m2',
                                                '-mvn.tar.xz',
                                                fetchlist,
                                                dist_settings=None)


@pytest.mark.asyncio
async def test_update_maven_ebuild_skips_when_archive_uploaded(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.maven.dist_archive_already_uploaded',
                 new_callable=AsyncMock,
                 return_value=True)
    search = mocker.patch('livecheck.special.maven.search_ebuild', new_callable=AsyncMock)
    await update_maven_ebuild('ebuild', 'path', {'foo': ('bar',)})
    search.assert_not_called()


@pytest.mark.asyncio
async def test_update_maven_ebuild_nonzero_returncode(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.maven.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = ('/tmp/maven', '/tmp/temp')
    mocker.patch('livecheck.special.maven.which', return_value='/usr/bin/mvn')
    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build_compress = mocker.patch('livecheck.special.maven.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.maven.log')
    await update_maven_ebuild('ebuild', 'path', {})
    mock_build_compress.assert_not_called()
    mock_log.error.assert_called_once_with("Error running 'mvn'.")


@pytest.mark.asyncio
async def test_update_maven_ebuild_sp_run_raises(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.maven.search_ebuild',
                                      new_callable=AsyncMock)
    maven_path = '/tmp/maven'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (maven_path, temp_dir)
    mocker.patch('livecheck.special.maven.which', return_value='/usr/bin/mvn')

    mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=OSError('mvn failed'))
    mock_build_compress = mocker.patch('livecheck.special.maven.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.maven.log')

    await update_maven_ebuild('ebuild', 'path', {})

    mock_build_compress.assert_not_called()
    assert mock_log.exception.called


def test_check_maven_requirements_returns_true_when_installed(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.maven.check_program', return_value=True)
    mock_log = mocker.patch('livecheck.special.maven.log')
    assert check_maven_requirements() is True
    mock_check_program.assert_called_once_with('mvn', ['--version'])
    mock_log.error.assert_not_called()


def test_check_maven_requirements_returns_false_when_not_installed(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.maven.check_program', return_value=False)
    mock_log = mocker.patch('livecheck.special.maven.log')
    assert check_maven_requirements() is False
    mock_check_program.assert_called_once_with('mvn', ['--version'])
    mock_log.error.assert_called_once_with('mvn is not installed')


@pytest.mark.asyncio
async def test_update_maven_ebuild_lockfile_ignores_resolver_records(mocker: MockerFixture,
                                                                     tmp_path: Path) -> None:
    distdir = tmp_path / 'distfiles'
    distdir.mkdir()
    mocker.patch('livecheck.special.utils.get_distdir', return_value=distdir)
    mocker.patch('livecheck.special.maven.which', return_value='/usr/bin/mvn')
    runs = iter(('Mon Nov 23', 'Tue Nov 24'))

    def _create(*_args: str, cwd: str) -> MagicMock:
        time = next(runs)
        artifact = tmp_path / cwd / '.m2' / 'org' / 'x' / '1.0'
        artifact.mkdir(parents=True)
        (artifact / 'x-1.0.jar').write_text('jar', encoding='utf-8')
        (artifact / '_remote.repositories').write_text(f'#{time}\n', encoding='utf-8')
        (artifact.parent / 'maven-metadata-central.xml').write_text(time, encoding='utf-8')
        (artifact / 'x-1.0.pom.lastUpdated').write_text(time, encoding='utf-8')
        (tmp_path / cwd / '.m2' / 'resolver-status.properties').write_text(time, encoding='utf-8')
        proc: MagicMock = mocker.MagicMock()
        proc.wait = AsyncMock(return_value=0)
        return proc

    mocker.patch('livecheck.special.maven.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=_create)
    digests = []
    for version in ('1.0', '1.1'):
        mocker.patch('livecheck.special.maven.search_ebuild',
                     new_callable=AsyncMock,
                     return_value=(str(tmp_path / f'foo-{version}'), str(tmp_path)))
        digests.append(await update_maven_ebuild(f'cat/foo/foo-{version}.ebuild',
                                                 None, {},
                                                 archive_mode='lockfile'))

    assert digests[0] is not None
    assert digests[1] == digests[0]
    with tarfile.open(distdir / f'foo-{digests[0]}-mvn.tar.xz') as tar:
        assert '.m2/org/x/1.0/x-1.0.jar' in tar.getnames()
