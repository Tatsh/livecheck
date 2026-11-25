# ruff:file-ignore[boolean-type-hint-positional-argument, hardcoded-temp-file]
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock
import tarfile

from anyio import Path as AnyioPath
import pytest

from livecheck.dist_github import DistGitHubSettings
from livecheck.special.utils import (
    EbuildTempFile,
    build_compress,
    build_digest_archive,
    compute_vendor_archive_name,
    dist_archive_already_uploaded,
    ensure_digest_archive,
    get_archive_digest,
    get_archive_extension,
    get_project_path,
    log_unhandled_commit,
    remove_url_ebuild,
    replace_archive_digest,
    search_ebuild,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(('filename', 'expected'), [('archive', ''), ('archive.7z', '.7z'),
                                                    ('archive.TAR.BZ2', '.tar.bz2'),
                                                    ('archive.TAR.GZ', '.tar.gz'),
                                                    ('archive.bz2', '.bz2'),
                                                    ('archive.gh.tar.gz', '.gh.tar.gz'),
                                                    ('archive.gz', '.gz'), ('archive.rar', '.rar'),
                                                    ('archive.tar', '.tar'),
                                                    ('archive.tar.Gz', '.tar.gz'),
                                                    ('archive.tar.bz2', '.tar.bz2'),
                                                    ('archive.tar.gz', '.tar.gz'),
                                                    ('archive.tar.gz.backup', ''),
                                                    ('archive.tar.lz', '.tar.lz'),
                                                    ('archive.tar.xz', '.tar.xz'),
                                                    ('archive.tar.xz2', ''),
                                                    ('archive.tar.z', '.tar.z'),
                                                    ('archive.tar.zst', '.tar.zst'),
                                                    ('archive.tbz', '.tbz'),
                                                    ('archive.tbz2', '.tbz2'),
                                                    ('archive.tc.gz', '.tc.gz'),
                                                    ('archive.tgz', '.tgz'), ('archive.txt', ''),
                                                    ('archive.txz', '.txz'), ('archive.xz', '.xz'),
                                                    ('archive.zip', '.zip')])
def test_get_archive_extension(filename: str, expected: str, mocker: MockerFixture) -> None:
    # No need to mock anything for this pure function, but mocker is available
    assert get_archive_extension(filename) == expected


@pytest.mark.parametrize(
    ('ebuild', 'remove', 'expected'),
    [
        # Remove a URL line ending with the remove string
        ('SRC_URI="https://example.com/foo.tar.gz"\n', '.tar.gz', ''),
        # Do not remove if not ending with remove string
        ('SRC_URI="https://example.com/foo.zip"\n', '.tar.gz',
         'SRC_URI="https://example.com/foo.zip"\n'),
        # Remove only the matching line, keep others
        ('# comment\nSRC_URI="https://example.com/foo.tar.gz"\nSRC_URI="https://example.com/bar.zip"\n',
         '.tar.gz', '# comment\nSRC_URI="https://example.com/bar.zip"\n'),
        # Keep comments and blank lines
        ('\n# comment\nSRC_URI="https://example.com/foo.tar.gz"\n\n', '.tar.gz', '\n# comment\n\n'),
        # Remove line with single quotes
        ("SRC_URI='https://example.com/foo.tar.gz'\n", '.tar.gz', ''),
        # Remove line with no quotes
        ('SRC_URI=https://example.com/foo.tar.gz\n', '.tar.gz', ''),
        # Remove only if remove string is at the end
        ('SRC_URI="https://example.com/foo.tar.gz.backup"\n', '.tar.gz',
         'SRC_URI="https://example.com/foo.tar.gz.backup"\n'),
        # Remove line with extra whitespace
        ('   SRC_URI="https://example.com/foo.tar.gz"   \n', '.tar.gz', ''),
        # Remove line with only the remove string
        ('.tar.gz\n', '.tar.gz', ''),
        # Remove line with remove string and trailing quote
        ('"https://example.com/foo.tar.gz"\n', '.tar.gz', ''),
        # Remove line with remove string and trailing single quote
        ("'https://example.com/foo.tar.gz'\n", '.tar.gz', ''),
        # Remove line with remove string and no quotes
        ('https://example.com/foo.tar.gz\n', '.tar.gz', ''),
        # Keep line if remove string is in the middle
        ('SRC_URI="https://example.com/foo.tar.gz.zip"\n', '.tar.gz',
         'SRC_URI="https://example.com/foo.tar.gz.zip"\n')
    ])
def test_remove_url_ebuild(ebuild: str, remove: str, expected: str) -> None:
    result = remove_url_ebuild(ebuild, remove)
    assert result == expected


@pytest.mark.parametrize(
    ('ebuild', 'archive', 'path', 'found', 'expected_root'),
    [
        # Test when archive is found in files
        ('foo.ebuild', 'archive.tar.gz', None, True, '/tmp/unpacked_dir'),
        # Test when archive is not found
        ('foo.ebuild', 'missing.tar.gz', None, False, ''),
        # Test when path is provided and found in root
        ('foo.ebuild', 'archive.tar.gz', 'some/path', True, '/tmp/unpacked_dir/some/path'),
        # Test when path is provided and not found
        ('foo.ebuild', 'archive.tar.gz', 'notfound/path', False, '')
    ])
@pytest.mark.asyncio
async def test_search_ebuild(mocker: MockerFixture, ebuild: str, archive: str, path: str | None,
                             found: bool, expected_root: str) -> None:
    temp_dir = '/tmp/unpacked_dir'
    mocker.patch('livecheck.special.utils.unpack_ebuild', return_value=temp_dir)
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    if path is None:
        if found:
            walk_result: list[tuple[Any, ...]] = [(temp_dir, [], [archive]),
                                                  (temp_dir + '/subdir', [], [])]
        else:
            walk_result = [(temp_dir, [], ['other-file.txt']), (temp_dir + '/subdir', [], [])]
    elif found:
        walk_result = [(temp_dir, [], []), (temp_dir + '/' + path, [], [archive])]
    else:
        walk_result = [(temp_dir, [], []), (temp_dir + '/another-path', [], [])]
    mocker.patch('os.walk', return_value=walk_result)
    mocker.patch('livecheck.special.utils.to_thread.run_sync', side_effect=lambda fn, **_: fn())
    root, returned_temp_dir = await search_ebuild(ebuild, archive, path)
    if expected_root:
        assert root == expected_root
        assert returned_temp_dir == temp_dir
    else:
        assert not root
        assert not returned_temp_dir
        if path is None:
            mock_logger.error.assert_called_once_with('Error searching the `%s` inside package.',
                                                      archive)


@pytest.mark.asyncio
async def test_search_ebuild_path_skips_directory_without_archive(mocker: MockerFixture) -> None:
    temp_dir = '/tmp/unpacked_dir'
    mocker.patch('livecheck.special.utils.unpack_ebuild', return_value=temp_dir)
    mocker.patch('os.walk',
                 return_value=[(f'{temp_dir}/foo-1/internal/mysql/collector', [], ['query.go']),
                               (f'{temp_dir}/foo-1/collector', [], ['go.mod'])])
    mocker.patch('livecheck.special.utils.to_thread.run_sync', side_effect=lambda fn, **_: fn())
    root, returned_temp_dir = await search_ebuild('foo.ebuild', 'go.mod', '/collector')
    assert root == f'{temp_dir}/foo-1/collector'
    assert returned_temp_dir == temp_dir


@pytest.mark.asyncio
async def test_search_ebuild_unpack_error(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.utils.unpack_ebuild', return_value=None)
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    mocker.patch('livecheck.special.utils.to_thread.run_sync', side_effect=lambda fn, **_: fn())
    root, temp_dir = await search_ebuild('foo.ebuild', 'archive.tar.gz')
    assert not root
    assert not temp_dir
    mock_logger.warning.assert_called_once_with('Error unpacking the ebuild.')


@pytest.mark.parametrize(
    ('temp_dir', 'base_dir', 'directory', 'extension', 'fetchlist', 'exists', 'filename',
     'archive_ext', 'expected_result', 'expected_warning'),
    [
        # Directory does not exist
        ('/tmp/temp', '/tmp/base', 'vendor', '.tar.gz', {
            'foo.tar.gz': ('url',)
        }, False, 'foo.tar.gz', '.tar.gz', False, 'The directory vendor was not created.'),
        # fetchlist is empty
        ('/tmp/temp', '/tmp/base', 'vendor', '.tar.gz', {}, True, None, None, False, None),
        # Invalid extension
        ('/tmp/temp', '/tmp/base', 'vendor', '.tar.gz', {
            'foo.invalid': ('url',)
        }, True, 'foo.invalid', '', False, 'Invalid extension.'),
        # Extension already in filename
        ('/tmp/temp', '/tmp/base', 'vendor', '.tar.gz', {
            'foo.tar.gz': ('url',)
        }, True, 'foo.tar.gz', '.tar.gz', True, None),
        # Extension not in filename
        ('/tmp/temp', '/tmp/base', 'vendor', '.tar.xz', {
            'foo.tar.gz': ('url',)
        }, True, 'foo.tar.gz', '.tar.gz', True, None)
    ])
@pytest.mark.asyncio
async def test_build_compress(mocker: MockerFixture, temp_dir: str, base_dir: str, directory: str,
                              extension: str, fetchlist: Mapping[str, Collection[str]],
                              exists: bool, filename: str, archive_ext: str, expected_result: bool,
                              expected_warning: str | None) -> None:
    mocker.patch('pathlib.Path.exists', return_value=exists)
    mocker.patch('livecheck.special.utils.get_distdir', return_value=Path('/tmp/distdir'))
    mocker.patch('livecheck.special.utils.get_archive_extension',
                 return_value=archive_ext if archive_ext is not None else '')
    mock_tarfile_open = mocker.patch('tarfile.open')
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    mocker.patch('pathlib.Path.resolve', side_effect=lambda **_: Path(base_dir))
    mocker.patch('livecheck.special.utils.to_thread.run_sync', side_effect=lambda fn, **_: fn())
    result = await build_compress(temp_dir, base_dir, directory, extension, fetchlist)
    assert result == expected_result
    if not exists:
        mock_logger.warning.assert_called_once_with('The directory vendor was not created.')
    elif not fetchlist:
        assert not mock_logger.warning.called
    elif not archive_ext:
        mock_logger.warning.assert_called_once_with('Invalid extension.')
    elif expected_result:
        mock_tarfile_open.assert_called_once()
    else:
        assert not mock_tarfile_open.called
    mock_logger.reset_mock()
    mock_tarfile_open.reset_mock()


@pytest.mark.asyncio
async def test_ebuild_tempfile_context_manager_success(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    temp_file_path = '/tmp/test-abcdef.ebuild'
    mocker.patch('tempfile.mkstemp', return_value=(0, temp_file_path))
    mocker.patch('os.close')
    mock_ebuild = AsyncMock()
    mock_ebuild.unlink = AsyncMock()
    mock_temp = AsyncMock()
    mock_temp.exists = AsyncMock(return_value=True)
    mock_stat = AsyncMock()
    mock_stat.return_value.st_size = 1
    mock_temp.stat = mock_stat
    mock_temp.rename = AsyncMock()
    # After rename, temp file no longer exists.
    mock_temp.exists = AsyncMock(side_effect=[True, False])
    mocker.patch('livecheck.special.utils.AnyioPath',
                 side_effect=lambda p: mock_ebuild if p == ebuild_path else mock_temp)
    mocker.patch('pathlib.Path.chmod')
    async with EbuildTempFile(ebuild_path) as temp_file:
        assert temp_file == Path(temp_file_path)
    mock_ebuild.unlink.assert_called_once_with(missing_ok=True)


@pytest.mark.asyncio
async def test_ebuild_tempfile_tempfile_empty(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    temp_file_path = '/tmp/test-abcdef.ebuild'
    mocker.patch('tempfile.mkstemp', return_value=(0, temp_file_path))
    mocker.patch('os.close')
    mock_ebuild = AsyncMock()
    mock_ebuild.unlink = AsyncMock()
    mock_temp = AsyncMock()
    mock_temp.exists = AsyncMock(return_value=True)
    mock_stat = AsyncMock()
    mock_stat.return_value.st_size = 0
    mock_temp.stat = mock_stat
    mock_temp.rename = AsyncMock()
    mock_temp.unlink = AsyncMock()
    mocker.patch('livecheck.special.utils.AnyioPath',
                 side_effect=lambda p: mock_ebuild if p == ebuild_path else mock_temp)
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    async with EbuildTempFile(ebuild_path):
        pass
    mock_logger.error.assert_called_once_with('The temporary file is empty or missing.')


@pytest.mark.asyncio
async def test_ebuild_tempfile_exception_cleanup(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    mock_temp = AsyncMock()
    mock_temp.exists = AsyncMock(return_value=True)
    mock_temp.unlink = AsyncMock()
    mock_ebuild = AsyncMock()
    mocker.patch('livecheck.special.utils.AnyioPath',
                 side_effect=lambda p: mock_ebuild if p == ebuild_path else mock_temp)
    etf = EbuildTempFile(ebuild_path)
    etf.temp_file = mock_temp
    await etf.__aexit__(Exception, Exception('fail'), None)
    mock_temp.unlink.assert_called_once_with(missing_ok=True)


def test_get_project_path_returns_cache_path(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.utils.user_cache_dir',
                 return_value='/home/user/.cache/livecheck')
    result = get_project_path('some-package')
    assert result == Path('/home/user/.cache/livecheck/some-package')


def test_log_unhandled_commit_logs_warning(mocker: MockerFixture) -> None:
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    catpkg = 'category/package'
    src_uri = 'https://example.com/foo.tar.gz'
    log_unhandled_commit(catpkg, src_uri)
    mock_logger.warning.assert_called_once_with('Unhandled commit: %s SRC_URI: %s', catpkg, src_uri)


def test_compute_vendor_archive_name_empty_fetchlist() -> None:
    assert not compute_vendor_archive_name('-vendor.tar.xz', {})


def test_compute_vendor_archive_name_no_extension() -> None:
    assert not compute_vendor_archive_name('-vendor.tar.xz', {'plain-1.0': ()})


def test_compute_vendor_archive_name_renames() -> None:
    name = compute_vendor_archive_name('-vendor.tar.xz', {'foo-1.0.tar.gz': ()})
    assert name == 'foo-1.0-vendor.tar.xz'


def test_compute_vendor_archive_name_passes_through_when_suffix_present() -> None:
    assert compute_vendor_archive_name('-vendor.tar.xz',
                                       {'foo-1.0-vendor.tar.xz': ()}) == 'foo-1.0-vendor.tar.xz'


@pytest.mark.asyncio
async def test_dist_archive_already_uploaded_returns_false_without_settings() -> None:
    assert await dist_archive_already_uploaded('-vendor.tar.xz', {'foo-1.0.tar.gz': ()},
                                               None) is False


@pytest.mark.asyncio
async def test_dist_archive_already_uploaded_returns_false_when_forced() -> None:
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist', force=True)
    assert await dist_archive_already_uploaded('-vendor.tar.xz', {'foo-1.0.tar.gz': ()},
                                               settings) is False


@pytest.mark.asyncio
async def test_dist_archive_already_uploaded_returns_false_when_name_blank() -> None:
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await dist_archive_already_uploaded('-vendor.tar.xz', {}, settings) is False


@pytest.mark.asyncio
async def test_dist_archive_already_uploaded_consults_asset_exists(mocker: MockerFixture) -> None:
    asset_exists = mocker.patch('livecheck.special.utils.asset_exists',
                                new_callable=AsyncMock,
                                return_value=True)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')
    assert await dist_archive_already_uploaded('-vendor.tar.xz', {'foo-1.0.tar.gz': ()},
                                               settings) is True
    asset_exists.assert_awaited_once_with(settings, 'foo-1.0-vendor.tar.xz')


def _tree(root: Path, files: Mapping[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding='utf-8')
    return root


def _members(archive: Path) -> list[str]:
    with tarfile.open(archive) as tar:
        return tar.getnames()


@pytest.mark.parametrize(('content', 'extension', 'expected'), [
    ('SRC_URI="https://example.com/${PN}-0123456789abcdef-node_modules.tar.xz"',
     '-node_modules.tar.xz', '0123456789abcdef'),
    ('SRC_URI="https://example.com/${P}-node_modules.tar.xz"', '-node_modules.tar.xz', None),
    ('SRC_URI="https://example.com/${PN}-0123456789abcdef-mvn.tar.xz"', '-vendor.tar.xz', None),
    (('SRC_URI="https://example.com/${PN}-0123456789abcdef-mvn.tar.xz\n'
      '\thttps://example.com/${PN}-fedcba9876543210-vendor.tar.xz"'), '-vendor.tar.xz',
     'fedcba9876543210'),
])
def test_get_archive_digest(content: str, extension: str, expected: str | None) -> None:
    assert get_archive_digest(content, extension) == expected


@pytest.mark.parametrize('name', ['${P}', '${PN}-0123456789abcdef', 'foo-1.0'])
def test_replace_archive_digest(name: str) -> None:
    content = ('SRC_URI="https://example.com/foo-src.tar.xz\n'
               f'\thttps://example.com/dist/{name}-vendor.tar.xz\n'
               '\thttps://example.com/dist/${P}-mvn.tar.xz"\n')
    assert replace_archive_digest(
        content, '-vendor.tar.xz',
        'fedcba9876543210') == ('SRC_URI="https://example.com/foo-src.tar.xz\n'
                                '\thttps://example.com/dist/${PN}-fedcba9876543210-vendor.tar.xz\n'
                                '\thttps://example.com/dist/${P}-mvn.tar.xz"\n')


@pytest.mark.asyncio
async def test_ensure_digest_archive_builds_missing_archive(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)

    def _build(path: Path) -> bool:
        path.write_bytes(b'archive')
        return True

    build = AsyncMock(side_effect=_build)

    assert await ensure_digest_archive('foo', '0123456789abcdef', '-vendor.tar.xz',
                                       build) == '0123456789abcdef'
    build.assert_awaited_once_with(tmp_path / 'foo-0123456789abcdef-vendor.tar.xz.partial')
    assert [path.name async for path in AnyioPath(tmp_path).iterdir()] == [
        'foo-0123456789abcdef-vendor.tar.xz'
    ]


@pytest.mark.asyncio
async def test_ensure_digest_archive_reuses_previous_digest(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    upload = mocker.patch('livecheck.special.utils.upload_dist_archive', new_callable=AsyncMock)
    build = AsyncMock(return_value=True)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')

    assert await ensure_digest_archive('foo',
                                       '0123456789abcdef',
                                       '-vendor.tar.xz',
                                       build,
                                       dist_settings=settings,
                                       previous_digest='0123456789abcdef') == '0123456789abcdef'
    build.assert_not_awaited()
    upload.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('uploaded', [True, False])
async def test_ensure_digest_archive_uploads_archive_in_distdir(mocker: MockerFixture,
                                                                tmp_path: Path,
                                                                uploaded: bool) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    mocker.patch('livecheck.special.utils.asset_exists', new_callable=AsyncMock, return_value=False)
    upload = mocker.patch('livecheck.special.utils.upload_dist_archive',
                          new_callable=AsyncMock,
                          return_value=uploaded)
    (archive := tmp_path / 'foo-0123456789abcdef-vendor.tar.xz').write_bytes(b'')
    build = AsyncMock(return_value=True)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')

    result = await ensure_digest_archive('foo',
                                         '0123456789abcdef',
                                         '-vendor.tar.xz',
                                         build,
                                         dist_settings=settings)

    assert result == ('0123456789abcdef' if uploaded else None)
    build.assert_not_awaited()
    upload.assert_awaited_once_with(settings, archive)


@pytest.mark.asyncio
async def test_ensure_digest_archive_reuses_published_archive(mocker: MockerFixture,
                                                              tmp_path: Path) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    asset_exists = mocker.patch('livecheck.special.utils.asset_exists',
                                new_callable=AsyncMock,
                                return_value=True)
    upload = mocker.patch('livecheck.special.utils.upload_dist_archive', new_callable=AsyncMock)
    build = AsyncMock(return_value=True)
    settings = DistGitHubSettings(force=True, repository='Tatsh/livecheck', release='dist')

    assert await ensure_digest_archive('foo',
                                       '0123456789abcdef',
                                       '-vendor.tar.xz',
                                       build,
                                       dist_settings=settings) == '0123456789abcdef'
    asset_exists.assert_awaited_once_with(settings, 'foo-0123456789abcdef-vendor.tar.xz')
    build.assert_not_awaited()
    upload.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('interrupted', [False, True])
async def test_ensure_digest_archive_build_fails(mocker: MockerFixture, tmp_path: Path,
                                                 interrupted: bool) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    upload = mocker.patch('livecheck.special.utils.upload_dist_archive', new_callable=AsyncMock)
    mocker.patch('livecheck.special.utils.asset_exists', new_callable=AsyncMock, return_value=False)
    settings = DistGitHubSettings(repository='Tatsh/livecheck', release='dist')

    def _build(path: Path) -> bool:
        path.write_bytes(b'trunc')
        if interrupted:
            msg = 'No space left on device'
            raise OSError(msg)
        return False

    build = AsyncMock(side_effect=_build)

    if interrupted:
        with pytest.raises(OSError, match='No space left on device'):
            await ensure_digest_archive('foo',
                                        '0123456789abcdef',
                                        '-vendor.tar.xz',
                                        build,
                                        dist_settings=settings)
    else:
        assert await ensure_digest_archive('foo',
                                           '0123456789abcdef',
                                           '-vendor.tar.xz',
                                           build,
                                           dist_settings=settings) is None
    assert not [path async for path in AnyioPath(tmp_path).iterdir()]
    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_digest_archive_shares_archive_between_versions(mocker: MockerFixture,
                                                                    tmp_path: Path) -> None:
    distdir = tmp_path / 'distfiles'
    distdir.mkdir()
    mocker.patch('livecheck.special.utils.get_distdir', return_value=distdir)
    files = {'vendor/modules.txt': '# example.com/mod v1.0.0\n', 'vendor/example.com/mod/a.go': ''}
    first = await build_digest_archive(str(_tree(tmp_path / 'foo-1.0', files)), 'vendor',
                                       '-vendor.tar.xz', 'foo')
    second = await build_digest_archive(str(_tree(tmp_path / 'foo-1.1', files)), 'vendor',
                                        '-vendor.tar.xz', 'foo')
    third = await build_digest_archive(
        str(_tree(tmp_path / 'foo-1.2', {
            **files, 'vendor/example.com/mod/b.go': ''
        })), 'vendor', '-vendor.tar.xz', 'foo')

    assert first is not None
    assert len(first) == 16
    assert second == first
    assert third not in {None, first}
    assert sorted(path.name for path in distdir.iterdir()) == sorted(
        (f'foo-{first}-vendor.tar.xz', f'foo-{third}-vendor.tar.xz'))
    assert _members(distdir / f'foo-{first}-vendor.tar.xz') == [
        'vendor', 'vendor/example.com', 'vendor/example.com/mod', 'vendor/example.com/mod/a.go',
        'vendor/modules.txt'
    ]


@pytest.mark.asyncio
async def test_build_digest_archive_omits_excluded_files_from_digest(mocker: MockerFixture,
                                                                     tmp_path: Path) -> None:
    distdir = tmp_path / 'distfiles'
    distdir.mkdir()
    mocker.patch('livecheck.special.utils.get_distdir', return_value=distdir)
    digests = []
    for version, record in (('1.0', '#Mon Nov 23 2026\n'), ('1.1', '#Tue Nov 24 2026\n')):
        base_dir = _tree(tmp_path / f'foo-{version}', {
            '.m2/org/x/1.0/x-1.0.jar': 'jar',
            '.m2/org/x/1.0/_remote.repositories': record
        })
        digests.append(await
                       build_digest_archive(str(base_dir),
                                            '.m2',
                                            '-mvn.tar.xz',
                                            'foo',
                                            excluded=lambda name: name == '_remote.repositories'))

    assert digests[0] is not None
    assert digests[1] == digests[0]
    assert '.m2/org/x/1.0/_remote.repositories' in _members(
        distdir / f'foo-{digests[0]}-mvn.tar.xz')


@pytest.mark.asyncio
async def test_build_digest_archive_digest_covers_modes_and_links(mocker: MockerFixture,
                                                                  tmp_path: Path) -> None:
    mocker.patch('livecheck.special.utils.get_distdir', return_value=tmp_path)
    plain = _tree(tmp_path / 'plain', {'vendor/tool': '', 'vendor/data': ''})
    executable = _tree(tmp_path / 'executable', {'vendor/tool': '', 'vendor/data': ''})
    (executable / 'vendor' / 'tool').chmod(0o755)
    linked = _tree(tmp_path / 'linked', {'vendor/tool': '', 'vendor/data': ''})
    (linked / 'vendor' / 'link').symlink_to('tool')
    relinked = _tree(tmp_path / 'relinked', {'vendor/tool': '', 'vendor/data': ''})
    (relinked / 'vendor' / 'link').symlink_to('data')

    digests = {
        await build_digest_archive(str(base_dir), 'vendor', '-vendor.tar.xz', 'foo')
        for base_dir in (plain, executable, linked, relinked)
    }

    assert None not in digests
    assert len(digests) == 4


@pytest.mark.asyncio
async def test_build_digest_archive_without_directory(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    logger = mocker.patch('livecheck.special.utils.logger')
    assert await build_digest_archive(str(tmp_path), 'vendor', '-vendor.tar.xz', 'foo') is None
    logger.warning.assert_called_once_with('The directory vendor was not created.')
