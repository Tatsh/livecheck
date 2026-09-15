from __future__ import annotations

from typing import TYPE_CHECKING
import os
import tarfile

import pytest

from livecheck.special.crates import remove_crates_url, update_crates_ebuild

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_remove_crates_url_preserves_source() -> None:
    content = 'SRC_URI="https://example.com/${P}.tar.gz\nhttps://example.com/${P}-crates.tar.xz"\n'
    assert remove_crates_url(content) == 'SRC_URI="https://example.com/${P}.tar.gz\n"\n'


@pytest.mark.asyncio
async def test_update_crates_ebuild_creates_gentoo_archive(mocker: MockerFixture,
                                                           tmp_path: Path) -> None:
    mocker.patch.dict(os.environ, {
        'CARGO_HOME': '/caller/cargo',
        'HTTPS_PROXY': 'http://proxy:8080'
    })
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    (source / 'Cargo.lock').write_text('version = 3\n', encoding='utf-8')
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
    assert run.call_args.args == ('/usr/bin/cargo', 'vendor', '--locked', '--versioned-dirs',
                                  str(tmp_path / 'cargo_home' / 'gentoo'))
    assert run.call_args.kwargs['cwd'] == str(source)
    assert run.call_args.kwargs['env']['CARGO_HOME'] == str(tmp_path / 'cargo_home')
    assert run.call_args.kwargs['env']['HTTPS_PROXY'] == 'http://proxy:8080'
    assert os.environ['CARGO_HOME'] == '/caller/cargo'
    with tarfile.open(tmp_path / 'example-1.0-crates.tar.xz') as archive:
        assert 'cargo_home/gentoo/example-1.0.0/.cargo-checksum.json' in archive.getnames()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['lock', 'source', 'cargo', 'download', 'archive'])
async def test_update_crates_ebuild_reports_failures(mocker: MockerFixture, tmp_path: Path,
                                                     failure: str) -> None:
    (tmp_path / 'Cargo.toml').write_text('[workspace]\n', encoding='utf-8')
    if failure != 'lock':
        lock = ('[[package]]\nsource = "git+https://example.com/repo"\n'
                if failure == 'source' else 'version = 3\n')
        (tmp_path / 'Cargo.lock').write_text(lock, encoding='utf-8')
    mocker.patch('livecheck.special.crates.search_ebuild',
                 return_value=(str(tmp_path), str(tmp_path)))
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
