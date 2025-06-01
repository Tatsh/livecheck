# ruff: noqa: FBT001, S108
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from livecheck.special.utils import (
    EbuildTempFile,
    build_compress,
    get_archive_extension,
    log_unhandled_commit,
    remove_url_ebuild,
    search_ebuild,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(('filename', 'expected'), [
    ('archive.tar.gz', '.tar.gz'),
    ('archive.tar.xz', '.tar.xz'),
    ('archive.tar.bz2', '.tar.bz2'),
    ('archive.tar.lz', '.tar.lz'),
    ('archive.tar.zst', '.tar.zst'),
    ('archive.tc.gz', '.tc.gz'),
    ('archive.tar.z', '.tar.z'),
    ('archive.gz', '.gz'),
    ('archive.xz', '.xz'),
    ('archive.zip', '.zip'),
    ('archive.tbz2', '.tbz2'),
    ('archive.bz2', '.bz2'),
    ('archive.tbz', '.tbz'),
    ('archive.txz', '.txz'),
    ('archive.tar', '.tar'),
    ('archive.tgz', '.tgz'),
    ('archive.rar', '.rar'),
    ('archive.7z', '.7z'),
    ('archive', ''),
    ('archive.txt', ''),
    ('archive.TAR.GZ', '.tar.gz'),
    ('archive.TAR.BZ2', '.tar.bz2'),
    ('archive.tar.Gz', '.tar.gz'),
    ('archive.tar.xz2', ''),
    ('archive.tar.gz.backup', ''),
])
def test_get_archive_extension(filename: str, expected: str, mocker: MockerFixture) -> None:
    # No need to mock anything for this pure function, but mocker is available
    assert get_archive_extension(filename) == expected


@pytest.mark.parametrize(
    ('ebuild', 'remove', 'expected'),
    [
        # Remove a URL line ending with the remove string
        (
            'SRC_URI="https://example.com/foo.tar.gz"\n',
            '.tar.gz',
            '',
        ),
        # Do not remove if not ending with remove string
        (
            'SRC_URI="https://example.com/foo.zip"\n',
            '.tar.gz',
            'SRC_URI="https://example.com/foo.zip"\n',
        ),
        # Remove only the matching line, keep others
        (
            '# comment\nSRC_URI="https://example.com/foo.tar.gz"\nSRC_URI="https://example.com/bar.zip"\n',
            '.tar.gz',
            '# comment\nSRC_URI="https://example.com/bar.zip"\n',
        ),
        # Keep comments and blank lines
        (
            '\n# comment\nSRC_URI="https://example.com/foo.tar.gz"\n\n',
            '.tar.gz',
            '\n# comment\n\n',
        ),
        # Remove line with single quotes
        (
            "SRC_URI='https://example.com/foo.tar.gz'\n",
            '.tar.gz',
            '',
        ),
        # Remove line with no quotes
        (
            'SRC_URI=https://example.com/foo.tar.gz\n',
            '.tar.gz',
            '',
        ),
        # Remove only if remove string is at the end
        (
            'SRC_URI="https://example.com/foo.tar.gz.backup"\n',
            '.tar.gz',
            'SRC_URI="https://example.com/foo.tar.gz.backup"\n',
        ),
        # Remove line with extra whitespace
        (
            '   SRC_URI="https://example.com/foo.tar.gz"   \n',
            '.tar.gz',
            '',
        ),
        # Remove line with only the remove string
        (
            '.tar.gz\n',
            '.tar.gz',
            '',
        ),
        # Remove line with remove string and trailing quote
        (
            '"https://example.com/foo.tar.gz"\n',
            '.tar.gz',
            '',
        ),
        # Remove line with remove string and trailing single quote
        (
            "'https://example.com/foo.tar.gz'\n",
            '.tar.gz',
            '',
        ),
        # Remove line with remove string and no quotes
        (
            'https://example.com/foo.tar.gz\n',
            '.tar.gz',
            '',
        ),
        # Keep line if remove string is in the middle
        (
            'SRC_URI="https://example.com/foo.tar.gz.zip"\n',
            '.tar.gz',
            'SRC_URI="https://example.com/foo.tar.gz.zip"\n',
        ),
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
def test_search_ebuild(mocker: MockerFixture, ebuild: str, archive: str, path: str | None,
                       found: bool, expected_root: str) -> None:
    temp_dir = '/tmp/unpacked_dir'
    mocker.patch('livecheck.special.utils.unpack_ebuild', return_value=temp_dir)
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    if path is None:
        if found:
            walk_result: list[tuple[Any, ...]] = [
                (temp_dir, [], [archive]),
                (temp_dir + '/subdir', [], []),
            ]
        else:
            walk_result = [
                (temp_dir, [], ['other-file.txt']),
                (temp_dir + '/subdir', [], []),
            ]
    elif found:
        walk_result = [
            (temp_dir, [], []),
            (temp_dir + '/' + path, [], []),
        ]
    else:
        walk_result = [
            (temp_dir, [], []),
            (temp_dir + '/another-path', [], []),
        ]
    mocker.patch('os.walk', return_value=walk_result)
    root, returned_temp_dir = search_ebuild(ebuild, archive, path)
    if expected_root:
        assert root == expected_root
        assert returned_temp_dir == temp_dir
    else:
        assert not root
        assert not returned_temp_dir
        if path is None:
            mock_logger.error.assert_called_once_with('Error searching the `%s` inside package.',
                                                      archive)


def test_search_ebuild_unpack_error(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.special.utils.unpack_ebuild', return_value=None)
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    root, temp_dir = search_ebuild('foo.ebuild', 'archive.tar.gz')
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
def test_build_compress(mocker: MockerFixture, temp_dir: str, base_dir: str, directory: str,
                        extension: str, fetchlist: Mapping[str, Collection[str]], exists: bool,
                        filename: str, archive_ext: str, expected_result: bool,
                        expected_warning: str | None) -> None:
    mocker.patch('pathlib.Path.exists', return_value=exists)
    mocker.patch('livecheck.special.utils.get_distdir', return_value=Path('/tmp/distdir'))
    mocker.patch('livecheck.special.utils.get_archive_extension',
                 return_value=archive_ext if archive_ext is not None else '')
    mock_tarfile_open = mocker.patch('tarfile.open')
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    mocker.patch('pathlib.Path.resolve', side_effect=lambda: Path(base_dir))
    result = build_compress(temp_dir, base_dir, directory, extension, fetchlist)
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


def test_ebuild_tempfile_context_manager_success(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    temp_file_path = '/tmp/test-abcdef.ebuild'
    mock_tempfile = mocker.patch('tempfile.NamedTemporaryFile')
    mock_tempfile.return_value.name = temp_file_path
    mock_path = mocker.patch('livecheck.special.utils.Path')
    mock_ebuild = mock_path.return_value
    mock_temp = mock_path.return_value
    mock_ebuild.stem = 'test'
    mock_ebuild.suffix = '.ebuild'
    mock_ebuild.parent = '/tmp'
    mock_temp.exists.return_value = True
    mock_temp.stat.return_value.st_size = 1
    mock_ebuild.exists.return_value = False
    with EbuildTempFile(ebuild_path) as temp_file:
        assert temp_file == mock_temp
    mock_ebuild.unlink.assert_not_called()


def test_ebuild_tempfile_tempfile_empty(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    temp_file_path = '/tmp/test-abcdef.ebuild'
    mock_tempfile = mocker.patch('tempfile.NamedTemporaryFile')
    mock_tempfile.return_value.name = temp_file_path
    mock_path = mocker.patch('livecheck.special.utils.Path')
    mock_ebuild = mock_path.return_value
    mock_temp = mock_path.return_value
    mock_ebuild.stem = 'test'
    mock_ebuild.suffix = '.ebuild'
    mock_ebuild.parent = '/tmp'
    mock_temp.exists.return_value = True
    mock_temp.stat.return_value.st_size = 0
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    with EbuildTempFile(ebuild_path):
        pass
    mock_logger.error.assert_called_once_with('The temporary file is empty or missing.')


def test_ebuild_tempfile_exception_cleanup(mocker: MockerFixture) -> None:
    ebuild_path = '/tmp/test.ebuild'
    temp_file_path = '/tmp/test-abcdef.ebuild'
    mock_tempfile = mocker.patch('tempfile.NamedTemporaryFile')
    mock_tempfile.return_value.name = temp_file_path
    mock_path = mocker.patch('livecheck.special.utils.Path')
    mock_ebuild = mock_path.return_value
    mock_temp = mock_path.return_value
    mock_ebuild.stem = 'test'
    mock_ebuild.suffix = '.ebuild'
    mock_ebuild.parent = '/tmp'
    mock_temp.exists.return_value = True
    etf = EbuildTempFile(ebuild_path)
    etf.temp_file = mock_temp
    etf.__exit__(Exception, Exception('fail'), None)
    mock_temp.unlink.assert_called_once_with(missing_ok=True)


def test_log_unhandled_commit_logs_warning(mocker: MockerFixture) -> None:
    mock_logger = mocker.patch('livecheck.special.utils.logger')
    catpkg = 'category/package'
    src_uri = 'https://example.com/foo.tar.gz'
    log_unhandled_commit(catpkg, src_uri)
    mock_logger.warning.assert_called_once_with('Unhandled commit: %s SRC_URI: %s', catpkg, src_uri)
