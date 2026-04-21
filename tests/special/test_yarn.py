# ruff: noqa: S108
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from anyio import Path as AnyioPath
from livecheck.special.yarn import (
    Lockfile,
    check_yarn_requirements,
    create_project,
    parse_lockfile,
    update_yarn_ebuild,
    yarn_pkgs,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_create_project_runs_yarn_commands(mocker: MockerFixture) -> None:
    mock_get_project_path = mocker.patch('livecheck.special.yarn.get_project_path',
                                         return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.which', return_value='/usr/bin/yarn')

    mock_proc = mocker.MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_create = mocker.patch('livecheck.special.yarn.asyncio.create_subprocess_exec',
                               new_callable=AsyncMock,
                               return_value=mock_proc)

    base_package = 'foo'
    yarn_packages = {'bar', 'baz'}
    result = await create_project(base_package, yarn_packages)
    assert result == Path('/tmp/project')
    assert mock_get_project_path.call_count == 1
    assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_create_project_raises_when_yarn_missing(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.yarn.get_project_path', return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.which', return_value=None)
    with pytest.raises(FileNotFoundError, match="'yarn' not found in PATH"):
        await create_project('foo')


@pytest.mark.asyncio
async def test_parse_lockfile_parses_json_output(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.yarn.which', return_value='/usr/bin/node')
    mock_create_project = mocker.patch('livecheck.special.yarn.create_project',
                                       new_callable=AsyncMock,
                                       return_value=Path('/tmp/lockfile-project'))
    lockfile_data = '{"foo@^1.0.0": {"version": "1.2.3", "resolved": "url", "integrity": "sha"}}'
    mock_proc = mocker.MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(lockfile_data.encode(), b''))
    mocker.patch('livecheck.special.yarn.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    result = await parse_lockfile(Path('/tmp/project'))
    assert 'foo@^1.0.0' in result
    assert result['foo@^1.0.0']['version'] == '1.2.3'
    mock_create_project.assert_called_once_with('@yarnpkg/lockfile')


def test_yarn_pkgs_returns_expected_packages() -> None:
    lockfile: Lockfile = {
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
    }
    pkgs = list(yarn_pkgs(lockfile))
    assert 'foo-1.2.3' in pkgs
    assert '@scope/bar-2.3.4' in pkgs
    assert all(not pkg.startswith('baz-cjs') for pkg in pkgs)
    assert len(pkgs) == 2


def _patch_yarn_temp_file(mocker: MockerFixture, ebuild_path: Path, initial: str) -> dict[str, str]:
    ebuild_path.write_text(initial, encoding='utf-8')
    written: dict[str, str] = {}

    class _FakeTempFile:
        def __init__(self, _ebuild: str) -> None:
            self._path = ebuild_path

        async def __aenter__(self) -> Path:
            return self._path

        async def __aexit__(self, *_: object) -> None:
            written['text'] = await AnyioPath(ebuild_path).read_text(encoding='utf-8')

    mocker.patch('livecheck.special.yarn.EbuildTempFile', _FakeTempFile)
    return written


async def test_update_yarn_ebuild_replaces_yarn_pkgs_section(mocker: MockerFixture,
                                                             tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = {'bar', 'baz'}
    mock_create_project = mocker.patch('livecheck.special.yarn.create_project',
                                       new_callable=AsyncMock,
                                       return_value=Path('/tmp/project'))
    mock_parse_lockfile = mocker.patch('livecheck.special.yarn.parse_lockfile',
                                       new_callable=AsyncMock,
                                       return_value={
                                           'foo@^1.0.0': {
                                               'version': '1.2.3',
                                               'resolved': 'https://example.com/foo-1.2.3.tgz',
                                               'integrity': 'sha512-...'
                                           },
                                           'bar@^2.0.0': {
                                               'version': '2.3.4',
                                               'resolved': 'https://example.com/bar-2.3.4.tgz',
                                               'integrity': 'sha512-...'
                                           }
                                       })
    mock_copyfile = mocker.patch('livecheck.special.yarn.copyfile')
    written = _patch_yarn_temp_file(mocker, ebuild_path,
                                    'EAPI=8\nYARN_PKGS=(\n    old-pkg-0.1.0\n)\nSRC_URI=...\n')
    mocker.patch('pathlib.Path.chmod')
    await update_yarn_ebuild(str(ebuild_path), yarn_base_package, pkg, yarn_packages)
    mock_create_project.assert_called_once_with(yarn_base_package, yarn_packages)
    mock_parse_lockfile.assert_called_once()
    assert 'YARN_PKGS=(\n' in written['text']
    assert '\tbar-2.3.4\n' in written['text']
    assert '\tfoo-1.2.3\n' in written['text']
    assert ')\n' in written['text']
    mock_copyfile.assert_any_call(
        Path('/tmp/project') / 'package.json', ebuild_path.parent / 'files' / 'foo-package.json')
    mock_copyfile.assert_any_call(
        Path('/tmp/project') / 'yarn.lock', ebuild_path.parent / 'files' / 'foo-yarn.lock')


@pytest.mark.asyncio
async def test_update_yarn_ebuild_raises_on_malformed_section(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = None
    mocker.patch('livecheck.special.yarn.create_project',
                 new_callable=AsyncMock,
                 return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.parse_lockfile',
                 new_callable=AsyncMock,
                 return_value={
                     'foo@^1.0.0': {
                         'version': '1.2.3',
                         'resolved': 'https://example.com/foo-1.2.3.tgz',
                         'integrity': 'sha512-...'
                     }
                 })
    mocker.patch('livecheck.special.yarn.copyfile')
    mock_ebuild_temp_file = mocker.patch('livecheck.special.yarn.EbuildTempFile')
    mock_temp_file = mock_ebuild_temp_file.return_value
    mock_temp_file.__aenter__ = AsyncMock(return_value=mock_temp_file)
    mock_temp_file.__aexit__ = AsyncMock(return_value=False)
    mock_tf_writer = mocker.MagicMock()
    mock_open_cm = mocker.MagicMock()
    mock_open_cm.__enter__ = mocker.MagicMock(return_value=mock_tf_writer)
    mock_open_cm.__exit__ = mocker.MagicMock(return_value=False)
    mock_temp_file.open = mocker.MagicMock(return_value=mock_open_cm)
    mock_temp_file.exists.return_value = False
    mock_temp_file.stat.return_value.st_size = 0
    ebuild_content = ['YARN_PKGS=(\n', 'YARN_PKGS=(\n', ')\n']
    mocker.patch('pathlib.Path.open', mocker.mock_open(read_data=''.join(ebuild_content)))
    with pytest.raises(RuntimeError):
        await update_yarn_ebuild(ebuild_path, yarn_base_package, pkg, yarn_packages)


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


async def test_update_yarn_ebuild_with_multiple_old_packages(mocker: MockerFixture,
                                                             tmp_path: Path) -> None:
    """Test that multiple old packages are replaced correctly without duplication."""
    ebuild_path = tmp_path / 'test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = None
    mocker.patch('pathlib.Path.chmod')
    mocker.patch('livecheck.special.yarn.create_project',
                 new_callable=AsyncMock,
                 return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.parse_lockfile',
                 new_callable=AsyncMock,
                 return_value={
                     'foo@^1.0.0': {
                         'version': '1.2.3',
                         'resolved': 'https://example.com/foo-1.2.3.tgz',
                         'integrity': 'sha512-...'
                     },
                     'bar@^2.0.0': {
                         'version': '2.3.4',
                         'resolved': 'https://example.com/bar-2.3.4.tgz',
                         'integrity': 'sha512-...'
                     }
                 })
    mocker.patch('livecheck.special.yarn.copyfile')
    written = _patch_yarn_temp_file(mocker, ebuild_path, ('EAPI=8\n'
                                                          'YARN_PKGS=(\n'
                                                          '\told-pkg-1-0.1.0\n'
                                                          '\told-pkg-2-0.2.0\n'
                                                          '\told-pkg-3-0.3.0\n'
                                                          ')\n'
                                                          'SRC_URI=...\n'))
    await update_yarn_ebuild(str(ebuild_path), yarn_base_package, pkg, yarn_packages)
    text = written['text']
    assert text.count('\tbar-2.3.4\n') == 1
    assert text.count('\tfoo-1.2.3\n') == 1
    assert '\told-pkg-1-0.1.0\n' not in text
    assert '\told-pkg-2-0.2.0\n' not in text
    assert '\told-pkg-3-0.3.0\n' not in text


async def test_update_yarn_ebuild_with_empty_yarn_pkgs(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    """Test handling of empty YARN_PKGS section."""
    ebuild_path = tmp_path / 'test.ebuild'
    yarn_base_package = 'foo'
    pkg = 'cat/foo'
    yarn_packages = None
    mocker.patch('pathlib.Path.chmod')
    mocker.patch('livecheck.special.yarn.create_project',
                 new_callable=AsyncMock,
                 return_value=Path('/tmp/project'))
    mocker.patch('livecheck.special.yarn.parse_lockfile',
                 new_callable=AsyncMock,
                 return_value={
                     'foo@^1.0.0': {
                         'version': '1.2.3',
                         'resolved': 'https://example.com/foo-1.2.3.tgz',
                         'integrity': 'sha512-...'
                     },
                     'bar@^2.0.0': {
                         'version': '2.3.4',
                         'resolved': 'https://example.com/bar-2.3.4.tgz',
                         'integrity': 'sha512-...'
                     }
                 })
    mocker.patch('livecheck.special.yarn.copyfile')
    written = _patch_yarn_temp_file(mocker, ebuild_path, 'EAPI=8\nYARN_PKGS=(\n)\nSRC_URI=...\n')
    await update_yarn_ebuild(str(ebuild_path), yarn_base_package, pkg, yarn_packages)
    assert '\tbar-2.3.4\n' in written['text']
    assert '\tfoo-1.2.3\n' in written['text']
