# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from livecheck.special.composer import (
    check_composer_requirements,
    remove_composer_url,
    update_composer_ebuild,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_remove_composer_url_calls_remove_url_ebuild(mocker: MockerFixture) -> None:
    mock_remove_url_ebuild = mocker.patch('livecheck.special.composer.remove_url_ebuild')
    mock_remove_url_ebuild.return_value = 'result'
    ebuild_content = 'SOME CONTENT'
    result = remove_composer_url(ebuild_content)
    mock_remove_url_ebuild.assert_called_once_with(ebuild_content, '-vendor.tar.xz')
    assert result == 'result'


def test_remove_composer_url_returns_expected_value(mocker: MockerFixture) -> None:
    expected = 'cleaned content'
    mocker.patch('livecheck.special.composer.remove_url_ebuild', return_value=expected)
    assert remove_composer_url('dummy') == expected


@pytest.mark.asyncio
async def test_update_composer_ebuild_composer_not_on_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = ('/tmp/composer', '/tmp/temp')
    mocker.patch('livecheck.special.composer.which', return_value=None)
    mock_create = mocker.patch('livecheck.special.composer.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.composer.log')
    await update_composer_ebuild('ebuild', 'path', {})
    mock_create.assert_not_called()
    mock_build_compress.assert_not_called()
    mock_log.error.assert_called_once_with('composer executable not found in PATH')


@pytest.mark.asyncio
async def test_update_composer_ebuild_no_composer_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = (None, None)
    mock_create = mocker.patch('livecheck.special.composer.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress',
                                       new_callable=AsyncMock)

    await update_composer_ebuild('ebuild', 'path', {})
    mock_create.assert_not_called()
    mock_build_compress.assert_not_called()


@pytest.mark.asyncio
async def test_update_composer_ebuild_success(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild',
                                      new_callable=AsyncMock)
    composer_path = '/tmp/composer'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (composer_path, temp_dir)
    composer_exe = '/usr/bin/composer'
    mocker.patch('livecheck.special.composer.which', return_value=composer_exe)

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.composer.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress',
                                       new_callable=AsyncMock)

    fetchlist = {'foo': ('bar',)}
    await update_composer_ebuild('ebuild', 'path', fetchlist)

    mock_build_compress.assert_called_once_with(temp_dir, composer_path, 'vendor', '-vendor.tar.xz',
                                                fetchlist)


@pytest.mark.asyncio
async def test_update_composer_ebuild_sp_run_raises(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild',
                                      new_callable=AsyncMock)
    composer_path = '/tmp/composer'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (composer_path, temp_dir)
    mocker.patch('livecheck.special.composer.which', return_value='/usr/bin/composer')

    mocker.patch('livecheck.special.composer.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=OSError('composer failed'))
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.composer.log')

    await update_composer_ebuild('ebuild', 'path', {})

    mock_build_compress.assert_not_called()
    assert mock_log.exception.called


@pytest.mark.asyncio
async def test_update_composer_ebuild_nonzero_returncode(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild',
                                      new_callable=AsyncMock)
    mock_search_ebuild.return_value = ('/tmp/composer', '/tmp/temp')
    mocker.patch('livecheck.special.composer.which', return_value='/usr/bin/composer')
    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mocker.patch('livecheck.special.composer.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress',
                                       new_callable=AsyncMock)
    mock_log = mocker.patch('livecheck.special.composer.log')
    await update_composer_ebuild('ebuild', 'path', {})
    mock_build_compress.assert_not_called()
    mock_log.error.assert_called_once_with("Error running 'composer'.")


def test_check_composer_requirements_returns_true_when_installed(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.composer.check_program', return_value=True)
    mock_log = mocker.patch('livecheck.special.composer.log')
    assert check_composer_requirements() is True
    mock_check_program.assert_called_once_with('composer', ['--version'])
    mock_log.error.assert_not_called()


def test_check_composer_requirements_returns_false_when_not_installed(
        mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.composer.check_program',
                                      return_value=False)
    mock_log = mocker.patch('livecheck.special.composer.log')
    assert check_composer_requirements() is False
    mock_check_program.assert_called_once_with('composer', ['--version'])
    mock_log.error.assert_called_once_with('composer is not installed')
