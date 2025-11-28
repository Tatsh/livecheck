from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.checksum import (
    get_latest_checksum_package,
    get_latest_location_checksum_package,
    update_checksum_metadata,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_checksum_package_match_and_checksum_mismatch(mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    manifest_content = ('DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n'
                        'DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('beefdead', 'beefcafe', 1234))
    mocker.patch('livecheck.special.checksum.get_last_modified',
                 return_value='2024-06-01T12:00:00Z')
    version, last_modified, returned_url = get_latest_checksum_package(url, ebuild, repo_root)
    assert version == '1.0'
    assert last_modified == '2024-06-01T12:00:00Z'
    assert returned_url == url


def test_get_latest_checksum_package_match_and_checksum_match(mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    manifest_content = ('DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n')

    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('deadbeef', 'cafebabe', 1234))
    result = get_latest_checksum_package(url, ebuild, repo_root)
    assert result == ('', '', '')


def test_get_latest_checksum_package_single_dist_line_matching_hash(mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    # Only one DIST line, but with different filename - should still check it
    manifest_content = ('DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    # Hash matches - no update needed
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('123456', '789abc', 5678))
    result = get_latest_checksum_package(url, ebuild, repo_root)
    assert result == ('', '', '')


def test_get_latest_checksum_package_single_dist_line_different_hash(mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    # Only one DIST line, but with different filename - should still check it
    manifest_content = ('DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    # Hash differs - update needed
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('different', 'hashes', 1234))
    mocker.patch('livecheck.special.checksum.get_last_modified', return_value='20240601')
    result = get_latest_checksum_package(url, ebuild, repo_root)
    assert result == ('1.0', '20240601', url)


def test_get_latest_checksum_package_multiple_dist_lines_no_match(mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    # Multiple DIST lines, none matching the filename
    manifest_content = ('DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n'
                        'DIST baz-3.0.tar.gz 9012 BLAKE2B abcdef SHA512 987654\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    result = get_latest_checksum_package(url, ebuild, repo_root)
    assert result == ('', '', '')


def test_get_latest_checksum_package_multiple_dist_lines_matching_hash(
        mocker: MockerFixture) -> None:
    url = 'https://example.com/foo-1.0.tar.gz'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    # Multiple DIST lines, one matching filename and hash matches
    manifest_content = ('DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n'
                        'DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mock_open = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', mock_open)
    # Hash matches - no update needed
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('deadbeef', 'cafebabe', 1234))
    result = get_latest_checksum_package(url, ebuild, repo_root)
    assert result == ('', '', '')


def test_update_checksum_metadata_updates_matching_line(mocker: MockerFixture) -> None:
    ebuild = 'cat/foo/foo-1.0.ebuild'
    url = 'https://example.com/foo-1.0.tar.gz'
    repo_root = '/repo'
    manifest_content = ('DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n'
                        'DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    expected_content = ('DIST foo-1.0.tar.gz 4321 BLAKE2B newbeef SHA512 newcafe\n'
                        'DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('newbeef', 'newcafe', 4321))
    temp_file_mock = mocker.MagicMock()
    tf_mock = mocker.mock_open()
    temp_file_mock.open = tf_mock
    mocker.patch('livecheck.special.checksum.EbuildTempFile', return_value=temp_file_mock)
    temp_file_mock.__enter__.return_value = temp_file_mock
    temp_file_mock.__exit__.return_value = None
    manifest_open_mock = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', manifest_open_mock)
    update_checksum_metadata(ebuild, url, repo_root)
    handle = tf_mock()
    written_lines = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert written_lines == expected_content


def test_update_checksum_metadata_no_matching_line(mocker: MockerFixture) -> None:
    ebuild = 'cat/foo/foo-1.0.ebuild'
    url = 'https://example.com/foo-1.0.tar.gz'
    repo_root = '/repo'
    manifest_content = ('DIST bar-2.0.tar.gz 5678 BLAKE2B 123456 SHA512 789abc\n')
    expected_content = manifest_content
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('newbeef', 'newcafe', 4321))
    temp_file_mock = mocker.MagicMock()
    tf_mock = mocker.mock_open()
    temp_file_mock.open = tf_mock
    mocker.patch('livecheck.special.checksum.EbuildTempFile', return_value=temp_file_mock)
    temp_file_mock.__enter__.return_value = temp_file_mock
    temp_file_mock.__exit__.return_value = None
    manifest_open_mock = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', manifest_open_mock)
    update_checksum_metadata(ebuild, url, repo_root)
    handle = tf_mock()
    written_lines = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert written_lines == expected_content


def test_update_checksum_metadata_multiple_matching_lines(mocker: MockerFixture) -> None:
    ebuild = 'cat/foo/foo-1.0.ebuild'
    url = 'https://example.com/foo-1.0.tar.gz'
    repo_root = '/repo'
    manifest_content = ('DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n'
                        'DIST foo-1.0.tar.gz 1234 BLAKE2B deadbeef SHA512 cafebabe\n')
    expected_content = ('DIST foo-1.0.tar.gz 4321 BLAKE2B newbeef SHA512 newcafe\n'
                        'DIST foo-1.0.tar.gz 4321 BLAKE2B newbeef SHA512 newcafe\n')
    mocker.patch('livecheck.special.checksum.catpkg_catpkgsplit',
                 return_value=('cat/foo', 'foo', 'r0', '1.0'))
    mocker.patch('livecheck.special.checksum.hash_url', return_value=('newbeef', 'newcafe', 4321))
    temp_file_mock = mocker.MagicMock()
    tf_mock = mocker.mock_open()
    temp_file_mock.open = tf_mock
    mocker.patch('livecheck.special.checksum.EbuildTempFile', return_value=temp_file_mock)
    temp_file_mock.__enter__.return_value = temp_file_mock
    temp_file_mock.__exit__.return_value = None
    manifest_open_mock = mocker.mock_open(read_data=manifest_content)
    mocker.patch('pathlib.Path.open', manifest_open_mock)
    update_checksum_metadata(ebuild, url, repo_root)
    handle = tf_mock()
    written_lines = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert written_lines == expected_content


def test_get_latest_location_checksum_package_with_location_header(mocker: MockerFixture) -> None:
    url = 'https://example.com/redirect'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    redirect_url = 'https://cdn.example.com/foo-1.0.tar.gz'
    mock_response = mocker.Mock()
    mock_response.headers = {'Location': redirect_url}
    mocker.patch('livecheck.special.checksum.get_content', return_value=mock_response)
    mocker.patch(
        'livecheck.special.checksum.get_latest_checksum_package',
        return_value=('1.0', '20240601', redirect_url),
    )
    version, last_modified, returned_url = get_latest_location_checksum_package(
        url, ebuild, repo_root)
    assert version == '1.0'
    assert last_modified == '20240601'
    assert returned_url == redirect_url


def test_get_latest_location_checksum_package_no_location_header(mocker: MockerFixture) -> None:
    url = 'https://example.com/redirect'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    mock_response = mocker.Mock()
    mock_response.headers = {}
    mocker.patch('livecheck.special.checksum.get_content', return_value=mock_response)
    version, last_modified, returned_url = get_latest_location_checksum_package(
        url, ebuild, repo_root)
    assert not version
    assert not last_modified
    assert not returned_url


def test_get_latest_location_checksum_package_with_headers_and_params(
        mocker: MockerFixture) -> None:
    url = 'https://example.com/redirect'
    ebuild = 'cat/foo/foo-1.0.ebuild'
    repo_root = '/repo'
    headers = {'Referer': 'https://example.com'}
    params = {'agree': 'Yes'}
    redirect_url = 'https://cdn.example.com/foo-1.0.tar.gz'
    mock_response = mocker.Mock()
    mock_response.headers = {'Location': redirect_url}
    mock_get_content = mocker.patch('livecheck.special.checksum.get_content',
                                    return_value=mock_response)
    mocker.patch(
        'livecheck.special.checksum.get_latest_checksum_package',
        return_value=('1.0', '20240601', redirect_url),
    )
    version, last_modified, returned_url = get_latest_location_checksum_package(url,
                                                                                ebuild,
                                                                                repo_root,
                                                                                headers=headers,
                                                                                params=params)
    assert version == '1.0'
    assert last_modified == '20240601'
    assert returned_url == redirect_url
    mock_get_content.assert_called_once_with(url,
                                             allow_redirects=False,
                                             headers=headers,
                                             params=params)
