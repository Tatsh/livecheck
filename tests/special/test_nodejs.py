# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from livecheck.special.nodejs import (
    check_nodejs_requirements,
    remove_nodejs_url,
    update_nodejs_ebuild,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
async def test_update_nodejs_ebuild_success(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress',
                                       new_callable=AsyncMock)

    package_path = '/tmp/pkg'
    temp_dir = '/tmp/tmpdir'
    mock_search_ebuild.return_value = (package_path, temp_dir)

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)

    fetchlist = {'foo': ('bar',)}
    await update_nodejs_ebuild('dummy.ebuild', '/some/path', fetchlist)

    mock_search_ebuild.assert_called_once_with('dummy.ebuild', 'package.json', '/some/path')
    mock_build_compress.assert_called_once_with(temp_dir, package_path, 'node_modules',
                                                '-node_modules.tar.xz', fetchlist)


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_no_package_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress',
                                       new_callable=AsyncMock)
    mock_create = mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock)

    mock_search_ebuild.return_value = (None, None)

    await update_nodejs_ebuild('dummy.ebuild', None, {})

    mock_search_ebuild.assert_called_once()
    mock_create.assert_not_called()
    mock_build_compress.assert_not_called()


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_npm_install_fails(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress',
                                       new_callable=AsyncMock)
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')

    package_path = '/tmp/pkg'
    temp_dir = '/tmp/tmpdir'
    mock_search_ebuild.return_value = (package_path, temp_dir)

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)

    await update_nodejs_ebuild('dummy.ebuild', None, {})

    mock_build_compress.assert_not_called()
    assert mock_logger.error.call_count == 1


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_subprocess_raises_os_error(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress',
                                       new_callable=AsyncMock)
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_search_ebuild.return_value = ('/tmp/pkg', '/tmp/tmpdir')
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=OSError('npm failed'))
    await update_nodejs_ebuild('dummy.ebuild', None, {})
    mock_build_compress.assert_not_called()
    assert mock_logger.exception.called


@pytest.mark.asyncio
async def test_update_nodejs_ebuild_other_package_manager(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild',
                                      new_callable=AsyncMock)
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress',
                                       new_callable=AsyncMock)

    mock_search_ebuild.return_value = ('/tmp/pkg', '/tmp/tmpdir')

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('livecheck.special.nodejs.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)

    await update_nodejs_ebuild('dummy.ebuild', None, {}, package_manager='yarn')

    mock_build_compress.assert_called_once()


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
