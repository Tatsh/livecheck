from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING
import os
import tarfile

import pytest

from livecheck.special.crates import (
    check_crates_requirements,
    remove_crates_url,
    remove_native_crates,
    update_crates_ebuild,
    update_native_crates_ebuild,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

REGISTRY_LOCK = ('version = 3\n\n[[package]]\nname = "example"\nversion = "1.0.0"\n'
                 'source = "registry+https://github.com/rust-lang/crates.io-index"\n')


def test_remove_crates_url_preserves_source() -> None:
    content = 'SRC_URI="https://example.com/${P}.tar.gz\nhttps://example.com/${P}-crates.tar.xz"\n'
    assert remove_crates_url(content) == 'SRC_URI="https://example.com/${P}.tar.gz\n"\n'


@pytest.mark.parametrize('available', [True, False])
def test_check_crates_requirements(mocker: MockerFixture, *, available: bool) -> None:
    check_program = mocker.patch('livecheck.special.crates.check_program', return_value=available)
    assert check_crates_requirements() is available
    check_program.assert_called_once_with('cargo', ['--version'])


@pytest.mark.asyncio
async def test_update_crates_ebuild_creates_gentoo_archive(mocker: MockerFixture,
                                                           tmp_path: Path) -> None:
    mocker.patch.dict(os.environ, {
        'CARGO_HOME': '/caller/cargo',
        'CARGO_NET_OFFLINE': 'true',
        'HTTPS_PROXY': 'http://proxy:8080'
    })
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    (source / 'Cargo.lock').write_text(REGISTRY_LOCK, encoding='utf-8')
    vendor = tmp_path / 'cargo_home' / 'gentoo' / 'example-1.0.0'
    vendor.mkdir(parents=True)
    (vendor / '.cargo-checksum.json').write_text('{"files": {}}', encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=(str(source), str(tmp_path)))
    mocker.patch('livecheck.special.crates.which', return_value='/usr/bin/cargo')
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    proc = mocker.AsyncMock()
    proc.wait.return_value = 0
    run = mocker.patch('livecheck.special.crates.asyncio.create_subprocess_exec', return_value=proc)
    await update_crates_ebuild('example.ebuild', None, {'example-1.0.tar.gz': ()})
    assert run.call_args.args == ('/usr/bin/cargo', 'vendor', '--config', 'net.offline=false',
                                  '--locked', '--versioned-dirs',
                                  str(tmp_path / 'cargo_home' / 'gentoo'))
    assert run.call_args.kwargs['cwd'] == str(source)
    assert run.call_args.kwargs['env']['CARGO_HOME'] == str(tmp_path / 'cargo_home')
    assert run.call_args.kwargs['env']['HTTPS_PROXY'] == 'http://proxy:8080'
    assert os.environ['CARGO_HOME'] == '/caller/cargo'
    assert os.environ['CARGO_NET_OFFLINE'] == 'true'
    with tarfile.open(tmp_path / 'example-1.0-crates.tar.xz') as archive:
        assert 'cargo_home/gentoo/example-1.0.0/.cargo-checksum.json' in archive.getnames()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['unpacked', 'lock', 'source', 'cargo', 'download', 'archive'])
async def test_update_crates_ebuild_reports_failures(mocker: MockerFixture, tmp_path: Path,
                                                     failure: str) -> None:
    (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    if failure not in {'lock', 'unpacked'}:
        lock = ('[[package]]\nsource = "git+https://example.com/repo"\n'
                if failure == 'source' else 'version = 3\n')
        (tmp_path / 'Cargo.lock').write_text(lock, encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=('' if failure == 'unpacked' else str(tmp_path), str(tmp_path)))
    mocker.patch('livecheck.special.crates.which',
                 return_value=None if failure == 'cargo' else '/usr/bin/cargo')
    proc = mocker.AsyncMock()
    proc.wait.return_value = 1 if failure == 'download' else 0
    mocker.patch('livecheck.special.crates.asyncio.create_subprocess_exec', return_value=proc)
    compress = mocker.patch('livecheck.special.crates.build_compress', return_value=False)
    with pytest.raises(RuntimeError) as exc_info:
        await update_crates_ebuild('example.ebuild', None, {'example.tar.gz': ()})
    if failure == 'source':
        assert 'git+https://example.com/repo' in str(exc_info.value)
    assert compress.await_count == (1 if failure == 'archive' else 0)


@pytest.mark.asyncio
async def test_update_crates_ebuild_skips_uploaded_archive(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.crates.dist_archive_already_uploaded', return_value=True)
    search = mocker.patch('livecheck.special.crates.search_ebuild')
    await update_crates_ebuild('example.ebuild', None, {'example.tar.gz': ()})
    search.assert_not_awaited()


@pytest.mark.parametrize('archive', [
    'https://example.com/${P}-crates.tar.xz',
    'https://example.com/dependencies.tar.xz -> ${P}-crates.tar.xz',
    'https://example.com/${P}-crates.tar.xz -> dependencies.tar.xz',
    '${DIST_SERVER}/${P}-crates.tar.xz',
    '${DIST_SERVER}/dependencies.tar.xz -> ${P}-crates.tar.xz',
])
def test_remove_native_crates_preserves_sources(archive: str) -> None:
    content = ('CRATES="old@1.0.0"\ninherit cargo\n'
               f'SRC_URI="https://example.com/${{P}}.tar.gz {archive} ${{CARGO_CRATE_URIS}}"\n')
    result = remove_native_crates(content)
    assert 'CRATES=""\ninherit cargo' in result
    assert 'https://example.com/${P}.tar.gz' in result
    assert 'crates.tar.xz' not in result
    assert 'CARGO_CRATE_URIS' not in result
    assert '->' not in result


def test_remove_native_crates_preserves_other_variables() -> None:
    metadata = ('# Fetch ${CARGO_CRATE_URIS} from https://example.com/pkg-crates.tar.xz.\n'
                'HOMEPAGE="https://example.com/site-crates.tar.xz"\n'
                'DESCRIPTION="Previously used ${CARGO_CRATE_URIS}"\n')
    content = metadata + 'SRC_URI="https://example.com/${P}-crates.tar.xz"\n'
    assert remove_native_crates(content) == metadata + 'SRC_URI=""\n'


@pytest.mark.parametrize('dependencies', [
    'test? ( https://example.com/pkg-crates.tar.xz )',
    'test? ( ${CARGO_CRATE_URIS} )',
    'test? ( !debug? ( ${CARGO_CRATE_URIS} ) )',
])
def test_remove_native_crates_removes_empty_use_groups(dependencies: str) -> None:
    source = 'https://example.com/source.tar.gz'
    result = remove_native_crates(f'SRC_URI="{dependencies} {source}"\n')
    assert import_module('portage.dep').use_reduce(
        result.removeprefix('SRC_URI="').removesuffix('"\n'), is_src_uri=True,
        matchall=True) == [source]


@pytest.mark.parametrize('expression', [
    '$(pypi_sdist_url "${PN}")',
    '$(pypi_sdist_url "$(get_name)")',
    '${SOURCE_URI:-"https://example.com/${P}.tar.gz"}',
])
def test_remove_native_crates_preserves_shell_expressions(expression: str) -> None:
    content = f'SRC_URI="{expression}\nhttps://example.com/${{P}}-crates.tar.xz"\n'
    assert remove_native_crates(content) == f'SRC_URI="{expression}\n"\n'


def test_remove_native_crates_rejects_unterminated_value() -> None:
    with pytest.raises(RuntimeError, match='Unterminated quoted SRC_URI'):
        remove_native_crates('SRC_URI="$(pypi_sdist_url "${PN}")\n')


@pytest.mark.asyncio
@pytest.mark.parametrize('content', [
    'EAPI=8\nCRATES="old@1.0.0"\ninherit cargo pypi\nSRC_URI+=" ${CARGO_CRATE_URIS}"\n',
    "EAPI=8\nCRATES='old@1.0.0'\ninherit cargo pypi\nSRC_URI+=\" ${CARGO_CRATE_URIS}\"\n",
    'EAPI=8\ninherit cargo pypi\n',
    ('EAPI=8\nCRATES="old@1.0.0"\nCRATES+=" old@2.0.0"\n'
     'CRATES="old@3.0.0"\ninherit cargo pypi\n'),
    'EAPI=8\n# SRC_URI previously used ${CARGO_CRATE_URIS}.\ninherit cargo pypi\n',
    ('EAPI=8\ninherit cargo\nSRC_URI="https://example.com/${P}.tar.gz\n'
     'https://example.com/${P}-crates.tar.xz"\n'),
    'EAPI=8\ninherit cargo\nSRC_URI="https://example.com/${P}.tar.gz"\nCRATES="old@1.0.0"\n',
    'EAPI=8\ninherit cargo pypi\nSRC_URI+=" ${DIST_SERVER}/${P}-crates.tar.xz"\n',
    'EAPI=8\ninherit cargo pypi\nSRC_URI+="https://x/${P}-crates.tar.xz -> deps.tar.xz"\n',
])
async def test_update_native_crates_from_lock(mocker: MockerFixture, tmp_path: Path,
                                              content: str) -> None:
    (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    lock = (REGISTRY_LOCK + '\n[[package]]\nname = "workspace-member"\nversion = "1.0.0"\n'
            '\n[[package]]\nname = "example"\nversion = "0.9.0+build.1"\n'
            'source = "registry+https://github.com/rust-lang/crates.io-index"\n')
    (tmp_path / 'Cargo.lock').write_text(lock, encoding='utf-8')
    search = mocker.patch('livecheck.special.crates.search_ebuild',
                          return_value=(str(tmp_path), str(tmp_path)))
    cargo = mocker.patch('livecheck.special.crates.asyncio.create_subprocess_exec')
    upload = mocker.patch('livecheck.special.crates.dist_archive_already_uploaded')
    result = await update_native_crates_ebuild('pkg.ebuild', 'rust/path', content)
    assert 'CRATES="\n\texample@0.9.0+build.1\n\texample@1.0.0\n"' in result
    assert result.index('CRATES=') < result.index('inherit')
    assert result.count('CRATES=') == 1
    assert 'CRATES+=' not in result
    assert result.count('SRC_URI+=" ${CARGO_CRATE_URIS}"') == 1
    assert result.rindex('${CARGO_CRATE_URIS}') > result.index('inherit')
    assert 'old@' not in result
    assert 'workspace-member' not in result
    assert '-crates.tar.xz' not in result
    assert '-> deps.tar.xz' not in result
    if 'https://example.com/${P}.tar.gz' in content:
        assert 'https://example.com/${P}.tar.gz' in result
    assert await update_native_crates_ebuild('pkg.ebuild', 'rust/path', result) == result
    search.assert_awaited_with('pkg.ebuild', 'Cargo.lock', 'rust/path')
    cargo.assert_not_called()
    upload.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('content', [
    'inherit cargo \\\n  pypi\n',
    'SRC_URI="https://example.com/${P}.tar.gz"\ninherit cargo \\\n  pypi\n',
    ('inherit cargo\nSRC_URI="${CARGO_CRATE_URIS}"\n'
     'SRC_URI="https://example.com/${P}.tar.gz"\n'),
    'SRC_URI="${CARGO_CRATE_URIS}"\ninherit cargo pypi\n',
    ('inherit cargo pypi\nSRC_URI="$(pypi_sdist_url "${PN}")\n'
     'https://example.com/${P}-crates.tar.xz"\n'),
])
async def test_update_native_crates_places_uris_after_inheritance(mocker: MockerFixture,
                                                                  tmp_path: Path,
                                                                  content: str) -> None:
    (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    (tmp_path / 'Cargo.lock').write_text(REGISTRY_LOCK, encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=(str(tmp_path), str(tmp_path)))
    result = await update_native_crates_ebuild('pkg.ebuild', None, content)
    assert result.endswith('\nSRC_URI+=" ${CARGO_CRATE_URIS}"\n')
    assert result.index('CRATES=') < result.index('inherit')
    if 'inherit cargo \\\n  pypi' in content:
        assert 'inherit cargo \\\n  pypi\n' in result
    if '$(pypi_sdist_url "${PN}")' in content:
        assert '$(pypi_sdist_url "${PN}")' in result
        assert '-crates.tar.xz' not in result
    assert await update_native_crates_ebuild('pkg.ebuild', None, result) == result


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['git+https://example.com/repo', 'registry+https://example.com'])
async def test_update_native_crates_rejects_sources(mocker: MockerFixture, tmp_path: Path,
                                                    source: str) -> None:
    (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    (tmp_path / 'Cargo.lock').write_text(REGISTRY_LOCK.replace(
        'registry+https://github.com/rust-lang/crates.io-index', source),
                                         encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=(str(tmp_path), str(tmp_path)))
    with pytest.raises(RuntimeError, match='Unsupported crate source'):
        await update_native_crates_ebuild('pkg.ebuild', None, 'inherit cargo\n')


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['unpack', 'lock', 'manifest', 'inherit', 'version'])
async def test_update_native_crates_reports_failures(mocker: MockerFixture, tmp_path: Path,
                                                     failure: str) -> None:
    if failure != 'manifest':
        (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    if failure != 'lock':
        (tmp_path / 'Cargo.lock').write_text(
            REGISTRY_LOCK.replace('1.0.0', '$UNSAFE') if failure == 'version' else REGISTRY_LOCK,
            encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=('' if failure == 'unpack' else str(tmp_path), str(tmp_path)))
    with pytest.raises(RuntimeError):
        await update_native_crates_ebuild('pkg.ebuild', None,
                                          'EAPI=8\n' if failure == 'inherit' else 'inherit cargo\n')
