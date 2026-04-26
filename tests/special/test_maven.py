"""Tests for Maven helpers."""
# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from livecheck.special.maven import check_maven_requirements, remove_maven_url, update_maven_ebuild
import pytest

if TYPE_CHECKING:
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

    mock_build_compress.assert_called_once_with(temp_dir, maven_path, '.m2', '-mvn.tar.xz',
                                                fetchlist)


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
