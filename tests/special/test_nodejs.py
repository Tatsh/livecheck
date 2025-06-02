# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess as sp

from livecheck.special.nodejs import (
    check_nodejs_requirements,
    remove_nodejs_url,
    update_nodejs_ebuild,
)

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


def test_update_nodejs_ebuild_success(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild')
    mock_run = mocker.patch('livecheck.special.nodejs.sp.run')
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress')

    ebuild = 'dummy.ebuild'
    path = '/some/path'
    fetchlist = {'foo': ('bar',)}
    package_path = '/tmp/pkg'
    temp_dir = '/tmp/tmpdir'

    mock_search_ebuild.return_value = (package_path, temp_dir)

    update_nodejs_ebuild(ebuild, path, fetchlist)

    mock_search_ebuild.assert_called_once_with(ebuild, 'package.json', path)
    mock_run.assert_called_once_with(('npm', 'install', '--audit false', '--color false',
                                      '--progress false', '--ignore-scripts'),
                                     cwd=package_path,
                                     check=True)
    mock_build_compress.assert_called_once_with(temp_dir, package_path, 'node_modules',
                                                '-node_modules.tar.xz', fetchlist)


def test_update_nodejs_ebuild_no_package_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild')
    mock_run = mocker.patch('livecheck.special.nodejs.sp.run')
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress')

    mock_search_ebuild.return_value = (None, None)

    update_nodejs_ebuild('dummy.ebuild', None, {})

    mock_search_ebuild.assert_called_once()
    mock_run.assert_not_called()
    mock_build_compress.assert_not_called()


def test_update_nodejs_ebuild_npm_install_fails(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.nodejs.search_ebuild')
    mock_run = mocker.patch('livecheck.special.nodejs.sp.run')
    mock_build_compress = mocker.patch('livecheck.special.nodejs.build_compress')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')

    package_path = '/tmp/pkg'
    temp_dir = '/tmp/tmpdir'
    mock_search_ebuild.return_value = (package_path, temp_dir)
    mock_run.side_effect = sp.CalledProcessError(1, 'npm')

    update_nodejs_ebuild('dummy.ebuild', None, {})

    mock_run.assert_called_once()
    mock_build_compress.assert_not_called()
    assert mock_logger.exception.call_count == 1


def test_check_nodejs_requirements_success(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.nodejs.check_program')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_check_program.return_value = True

    result = check_nodejs_requirements()

    mock_check_program.assert_called_once_with('npm', ['--version'])
    assert result is True
    mock_logger.error.assert_not_called()


def test_check_nodejs_requirements_failure(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.nodejs.check_program')
    mock_logger = mocker.patch('livecheck.special.nodejs.logger')
    mock_check_program.return_value = False

    result = check_nodejs_requirements()

    mock_check_program.assert_called_once_with('npm', ['--version'])
    assert result is False
    mock_logger.error.assert_called_once_with('npm is not installed')
