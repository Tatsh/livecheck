# ruff: noqa: S108
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from livecheck.special.yarn import (
    check_yarn_requirements,
    create_project,
    update_yarn_ebuild,
    yarn_pkgs,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_create_project_runs_yarn_commands(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.special.yarn.sp.run')
    mock_get_project_path = mocker.patch('livecheck.special.yarn.get_project_path',
                                         return_value=Path('/tmp/project'))
    base_package = 'foo'
    yarn_packages = {'bar', 'baz'}
    result = create_project(base_package, yarn_packages)
    assert result == Path('/tmp/project')
    assert mock_get_project_path.call_count == 1
    assert mock_run.call_count == 3
    assert mock_run.call_args_list[0][0][0][:4] == ('yarn', 'config', 'set', 'ignore-engines')
    add_args = mock_run.call_args_list[1][0][0]
    assert add_args[0:2] == ('yarn', 'add')
    assert base_package in add_args
    assert all(pkg in add_args for pkg in yarn_packages)
    assert mock_run.call_args_list[2][0][0][:2] == ('yarn', 'upgrade')


def test_yarn_pkgs_returns_expected_packages(mocker: MockerFixture) -> None:
    mock_project_path = mocker.MagicMock()
    mocker.patch('livecheck.special.yarn.sp.run')
    mocker.patch('livecheck.special.yarn.json.loads',
                 return_value={
                     'foo@^1.0.0': {
                         'version': '1.2.3',
                         'resolved': 'https://example.com/foo-1.2.3.tgz',
                         'integrity': 'sha512-...',
                         'dependencies': {
                             'bar': '^2.0.0'
                         }
                     },
                     '@scope/bar@^2.0.0': {
                         'version': '2.3.4',
                         'resolved': 'https://example.com/bar-2.3.4.tgz',
                         'integrity': 'sha512-...',
                     },
                     'baz-cjs@^3.0.0': {
                         'version': '3.4.5',
                         'resolved': 'https://example.com/baz-3.4.5.tgz',
                         'integrity': 'sha512-...',
                     }
                 })
    pkgs = list(yarn_pkgs(mock_project_path))
    assert 'foo-1.2.3' in pkgs
    assert '@scope/bar-2.3.4' in pkgs
    assert all(not pkg.startswith('baz-cjs') for pkg in pkgs)
    assert len(pkgs) == 2


def test_update_yarn_ebuild_replaces_yarn_pkgs_section(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = {'bar', 'baz'}
    mocker.patch('pathlib.Path.chmod')
    mock_create_project = mocker.patch('livecheck.special.yarn.create_project',
                                       return_value=Path('/tmp/project'))
    mock_yarn_pkgs = mocker.patch('livecheck.special.yarn.yarn_pkgs',
                                  return_value=['foo-1.2.3', 'bar-2.3.4'])
    mock_copyfile = mocker.patch('livecheck.special.yarn.copyfile')
    mock_ebuild_temp_file = mocker.patch('livecheck.special.yarn.EbuildTempFile')
    mock_temp_file = mock_ebuild_temp_file.return_value
    mock_temp_file.__enter__.return_value = mock_temp_file
    mock_temp_file.open.return_value.__enter__.return_value = mocker.MagicMock()
    mock_temp_file.exists.return_value = True
    mock_temp_file.stat.return_value.st_size = 10
    ebuild_content = ['EAPI=8\n', 'YARN_PKGS=(\n', '    old-pkg-0.1.0\n', ')\n', 'SRC_URI=...\n']
    mocker.patch('pathlib.Path.open', mocker.mock_open(read_data=''.join(ebuild_content)))
    tf_mock = mock_temp_file.open.return_value.__enter__.return_value
    update_yarn_ebuild(ebuild_path, yarn_base_package, pkg, yarn_packages)
    mock_create_project.assert_called_once_with(yarn_base_package, yarn_packages)
    mock_yarn_pkgs.assert_called_once()
    mock_ebuild_temp_file.assert_called_once_with(ebuild_path)
    tf_mock.write.assert_any_call('YARN_PKGS=(\n')
    tf_mock.write.assert_any_call('\tbar-2.3.4\n')
    tf_mock.write.assert_any_call('\tfoo-1.2.3\n')
    tf_mock.write.assert_any_call(')\n')
    mock_copyfile.assert_any_call(
        Path('/tmp/project') / 'package.json',
        Path('/tmp/test.ebuild').parent / 'files' / 'foo-package.json')
    mock_copyfile.assert_any_call(
        Path('/tmp/project') / 'yarn.lock',
        Path('/tmp/test.ebuild').parent / 'files' / 'foo-yarn.lock')


def test_update_yarn_ebuild_raises_on_malformed_section(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = None
    mocker.patch('livecheck.special.yarn.create_project', return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.yarn_pkgs', return_value=['foo-1.2.3'])
    mocker.patch('livecheck.special.yarn.copyfile')
    mock_ebuild_temp_file = mocker.patch('livecheck.special.yarn.EbuildTempFile')
    mock_temp_file = mock_ebuild_temp_file.return_value
    mock_temp_file.__enter__.return_value = mock_temp_file
    mock_temp_file.open.return_value.__enter__.return_value = mocker.MagicMock()
    mock_temp_file.exists.return_value = False
    mock_temp_file.stat.return_value.st_size = 0
    ebuild_content = ['YARN_PKGS=(\n', 'YARN_PKGS=(\n', ')\n']
    mocker.patch('pathlib.Path.open', mocker.mock_open(read_data=''.join(ebuild_content)))
    with pytest.raises(RuntimeError):
        update_yarn_ebuild(ebuild_path, yarn_base_package, pkg, yarn_packages)


def test_check_yarn_requirements_all_installed(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.yarn.check_program',
                                      side_effect=[True, True])
    assert check_yarn_requirements() is True
    assert mock_check_program.call_count == 2
    mock_check_program.assert_any_call('yarn', ['--version'])
    mock_check_program.assert_any_call('node', ['--version'])


def test_check_yarn_requirements_yarn_missing(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.yarn.check_program',
                                      side_effect=[False, True])
    mock_logger = mocker.patch('livecheck.special.yarn.logger')
    assert check_yarn_requirements() is False
    mock_logger.error.assert_called_once_with('yarn is not installed')
    assert mock_check_program.call_count == 1


def test_check_yarn_requirements_node_missing(mocker: MockerFixture) -> None:
    mock_check_program = mocker.patch('livecheck.special.yarn.check_program',
                                      side_effect=[True, False])
    mock_logger = mocker.patch('livecheck.special.yarn.logger')
    assert check_yarn_requirements() is False
    mock_logger.error.assert_called_once_with('yarn is not installed')
    assert mock_check_program.call_count == 2
