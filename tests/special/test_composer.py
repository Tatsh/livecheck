# ruff: noqa: S108
from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.composer import (
    check_composer_requirements,
    remove_composer_url,
    update_composer_ebuild,
)

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


def test_update_composer_ebuild_no_composer_path(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild')
    mock_search_ebuild.return_value = (None, None)
    mock_sp_run = mocker.patch('livecheck.special.composer.sp.run')
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress')

    update_composer_ebuild('ebuild', 'path', {})
    mock_sp_run.assert_not_called()
    mock_build_compress.assert_not_called()


def test_update_composer_ebuild_success(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild')
    composer_path = '/tmp/composer'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (composer_path, temp_dir)
    mock_sp_run = mocker.patch('livecheck.special.composer.sp.run')
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress')

    fetchlist = {'foo': ('bar',)}
    update_composer_ebuild('ebuild', 'path', fetchlist)

    mock_sp_run.assert_called_once_with(('composer', '--no-interaction', '--no-scripts', 'install'),
                                        cwd=composer_path,
                                        check=True)
    mock_build_compress.assert_called_once_with(temp_dir, composer_path, 'vendor', '-vendor.tar.xz',
                                                fetchlist)


def test_update_composer_ebuild_sp_run_raises(mocker: MockerFixture) -> None:
    mock_search_ebuild = mocker.patch('livecheck.special.composer.search_ebuild')
    composer_path = '/tmp/composer'
    temp_dir = '/tmp/temp'
    mock_search_ebuild.return_value = (composer_path, temp_dir)
    mock_sp_run = mocker.patch('livecheck.special.composer.sp.run')
    mock_sp_run.side_effect = __import__('subprocess').CalledProcessError(1, 'composer')
    mock_build_compress = mocker.patch('livecheck.special.composer.build_compress')
    mock_log = mocker.patch('livecheck.special.composer.log')

    update_composer_ebuild('ebuild', 'path', {})

    mock_sp_run.assert_called_once()
    mock_build_compress.assert_not_called()
    assert mock_log.exception.called


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
