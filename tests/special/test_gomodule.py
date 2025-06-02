# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess as sp

from livecheck.special.gomodule import remove_gomodule_url, update_gomodule_ebuild

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


def test_update_gomodule_ebuild_success(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               return_value=('/some/path', '/tmp/dir'))
    mock_run = mocker.patch('livecheck.special.gomodule.sp.run', return_value=None)
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress')
    ebuild = 'dummy.ebuild'
    path = '/some/path'
    fetchlist = {'foo': ('bar',)}
    update_gomodule_ebuild(ebuild, path, fetchlist)
    mock_search.assert_called_once_with(ebuild, 'go.mod', path)
    mock_run.assert_called_once_with(('go', 'mod', 'vendor'), cwd='/some/path', check=True)
    mock_build.assert_called_once_with('/tmp/dir', '/some/path', 'vendor', '-vendor.tar.xz',
                                       fetchlist)


def test_update_gomodule_ebuild_no_go_mod_path(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               return_value=(None, None))
    mock_run = mocker.patch('livecheck.special.gomodule.sp.run')
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress')
    update_gomodule_ebuild('ebuild', None, {})
    mock_search.assert_called_once()
    mock_run.assert_not_called()
    mock_build.assert_not_called()


def test_update_gomodule_ebuild_subprocess_error(mocker: MockerFixture) -> None:
    mock_search = mocker.patch('livecheck.special.gomodule.search_ebuild',
                               return_value=('/some/path', '/tmp/dir'))
    mock_run = mocker.patch('livecheck.special.gomodule.sp.run',
                            side_effect=sp.CalledProcessError(1, 'go mod vendor'))
    mock_build = mocker.patch('livecheck.special.gomodule.build_compress')
    update_gomodule_ebuild('ebuild', '/some/path', {})
    mock_search.assert_called_once()
    mock_run.assert_called_once()
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
