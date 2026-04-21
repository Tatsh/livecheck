# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from livecheck.special.gomodule import remove_gomodule_url, update_gomodule_ebuild
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
from livecheck.special import gomodule


def test_remove_gomodule_url_removes_vendor_line(mocker: MockerFixture) -> None:
    mock_remove = mocker.patch('livecheck.special.gomodule.remove_url_ebuild',
                               return_value='filtered content')
    ebuild_content = 'SRC_URI="https://example.com/foo-vendor.tar.xz"\n'
    result = remove_gomodule_url(ebuild_content)
    mock_remove.assert_called_once_with(ebuild_content, '-vendor.tar.xz')
    assert result == 'filtered content'


def test_remove_gomodule_url_no_vendor_line(mocker: MockerFixture) -> None:
    mock_remove = mocker.patch('livecheck.special.gomodule.remove_url_ebuild',
                               side_effect=lambda content, _: content)
    ebuild_content = 'SRC_URI="https://example.com/foo.tar.gz"\n'
    result = remove_gomodule_url(ebuild_content)
    mock_remove.assert_called_once_with(ebuild_content, '-vendor.tar.xz')
    assert result == ebuild_content


@pytest.mark.asyncio
async def test_update_gomodule_ebuild_success(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               new_callable=AsyncMock,
                               return_value=('/some/path', '/tmp/dir'))
    go_exe = '/usr/bin/go'
    mocker.patch('livecheck.special.gomodule.which', return_value=go_exe)

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.gomodule.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress', new_callable=AsyncMock)

    ebuild = 'dummy.ebuild'
    path = '/some/path'
    fetchlist = {'foo': ('bar',)}
    await update_gomodule_ebuild(ebuild, path, fetchlist)
    mock_search.assert_called_once_with(ebuild, 'go.mod', path)
    mock_build.assert_called_once_with('/tmp/dir', '/some/path', 'vendor', '-vendor.tar.xz',
                                       fetchlist)


@pytest.mark.asyncio
async def test_update_gomodule_ebuild_no_go_mod_path(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               new_callable=AsyncMock,
                               return_value=(None, None))
    mock_create = mocker.patch('livecheck.special.gomodule.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress', new_callable=AsyncMock)
    await update_gomodule_ebuild('ebuild', None, {})
    mock_search.assert_called_once()
    mock_create.assert_not_called()
    mock_build.assert_not_called()


@pytest.mark.asyncio
async def test_update_gomodule_ebuild_go_not_on_path(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.gomodule.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=('/some/path', '/tmp/dir'))
    mocker.patch('livecheck.special.gomodule.which', return_value=None)
    mock_create = mocker.patch('livecheck.special.gomodule.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress', new_callable=AsyncMock)
    mock_logger = mocker.patch('livecheck.special.gomodule.logger')
    await update_gomodule_ebuild('ebuild', '/some/path', {})
    mock_create.assert_not_called()
    mock_build.assert_not_called()
    mock_logger.error.assert_called_once_with('go executable not found in PATH')


@pytest.mark.asyncio
async def test_update_gomodule_ebuild_nonzero_returncode(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.gomodule.search_ebuild',
                 new_callable=AsyncMock,
                 return_value=('/some/path', '/tmp/dir'))
    mocker.patch('livecheck.special.gomodule.which', return_value='/usr/bin/go')
    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mocker.patch('livecheck.special.gomodule.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress', new_callable=AsyncMock)
    mock_logger = mocker.patch('livecheck.special.gomodule.logger')
    await update_gomodule_ebuild('ebuild', '/some/path', {})
    mock_build.assert_not_called()
    mock_logger.error.assert_called_once_with("Error running 'go mod vendor'.")


@pytest.mark.asyncio
async def test_update_gomodule_ebuild_subprocess_error(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               new_callable=AsyncMock,
                               return_value=('/some/path', '/tmp/dir'))
    mocker.patch('livecheck.special.gomodule.which', return_value='/usr/bin/go')
    mocker.patch('livecheck.special.gomodule.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=OSError('go mod vendor failed'))
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress', new_callable=AsyncMock)
    await update_gomodule_ebuild('ebuild', '/some/path', {})
    mock_search.assert_called_once()
    mock_build.assert_not_called()


def test_check_gomodule_requirements_success(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.gomodule.check_program', return_value=True)
    result = gomodule.check_gomodule_requirements()
    mock_check_program.assert_called_once_with('go', ['version'])
    assert result is True


def test_check_gomodule_requirements_failure(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.gomodule.check_program',
                                      return_value=False)
    mock_logger = mocker.patch('livecheck.special.gomodule.logger')
    result = gomodule.check_gomodule_requirements()
    mock_check_program.assert_called_once_with('go', ['version'])
    mock_logger.error.assert_called_once_with('go is not installed')
    assert result is False
