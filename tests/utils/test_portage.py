from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
import operator
import re as real_re

from livecheck.utils.portage import (
    accept_version,
    catpkg_catpkgsplit,
    catpkgsplit2,
    compare_versions,
    digest_ebuild,
    fetch_ebuild,
    get_distdir,
    get_first_src_uri,
    get_highest_matches,
    get_last_version,
    get_repository_root_if_inside,
    is_version_development,
    mask_version,
    remove_initial_match,
    remove_leading_zeros,
    sanitize_version,
    unpack_ebuild,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(('version', 'expected'), [
    (0, '0'),
    ('', ''),
    ('v1.2.3', '1.2.3'),
    ('s1.2.3', '1.2.3'),
    ('1.2.3', '1.2.3'),
    ('1.2.3a', '1.2.3a'),
    ('1.2.3-alpha', '1.2.3_alpha'),
    ('1.2.3-alpha0', '1.2.3_alpha'),
    ('1.2.3-beta1', '1.2.3_beta1'),
    ('1.2.3-beta.1', '1.2.3_beta1'),
    ('1.2.3-rc2', '1.2.3_rc2'),
    ('1.2.3_rc2', '1.2.3_rc2'),
    ('1.2.3 RC 2', '1.2.3_rc2'),
    ('1.2.3-pre', '1.2.3_pre'),
    ('1.2.3-dev', '1.2.3_beta'),
    ('1.2.3-test', '1.2.3_beta'),
    ('1.2.3_test', '1.2.3_beta'),
    ('1.2.3_test 1', '1.2.3_beta1'),
    ('1.2.3p', '1.2.3_p'),
    ('1.2.3-unknown', '1.2.3'),
    ('1.2.3-unknown1', '1.2.31'),
    ('1.2.3-1', '1.2.3.1'),
    ('1.2.3_1', '1.2.3.1'),
    ('1.2.3 1', '1.2.3.1'),
    ('1.2.3-rc', '1.2.3_rc'),
    ('1.2.3-rc-1', '1.2.3_rc1'),
    ('2022.12.26 2022-12-26 19:55', '2022.12.26'),
    ('2022_12_26 2022-12-26 19:55', '2022.12.26'),
    ('2022-12-26 2022-12-26 19:55', '2022.12.26'),
    ('dosbox 2022-12-26 2022-12-26 19:55', '2022.12.26'),
    ('samba-4.19.7', '4.19.7'),
    ('test-190', '190'),
    ('test 190', '190'),
    ('318.1', '318.1'),
    ('1.2.0.4068', '1.2.0.4068'),
    ('v2015-09-29-license-adobe', '2015.9.29'),
    ('dosbox-x-v2025.01.01', '2025.1.1'),
    ('v0.8.9p10', '0.8.9_p10'),
    ('build_420', '420'),
    ('glabels', ''),
    ('NewBuild25rc1', '25_rc1'),
    ('v1.12.post318', '1.12_p318'),
    ('1.002', '1.002'),
    ('1.3.0-build.4', '1.3.0'),
    ('0.2.tar.gz', '0.2'),
    ('0.8.1-pl5', '0.8.1_p5'),
    ('0.8 patchlevel   6', '0.8_p6'),
    ('0.0.8b2', '0.0.8_beta2'),
    ('0.0.8a5', '0.0.8_alpha5'),
    ('0.1.8b0', '0.1.8_beta'),
    ('1.4.1-build.2', '1.4.1'),
])
def test_sanitize_version(version: str, expected: str) -> None:
    assert sanitize_version(version) == expected


@pytest.mark.parametrize(('version', 'expected'), [
    ('2022.01.06', '2022.1.6'),
    ('24.01.12', '24.1.12'),
    ('0.0.3', '0.0.3'),
    ('1.0.3-r1', '1.0.3-r1'),
    ('2022-12-26', '2022-12-26'),
    ('1.0.3', '1.0.3'),
    ('1.2', '1.2'),
    ('1.222222222', '1.222222222'),
    ('1', '1'),
    ('0.1.2', '0.1.2'),
    ('24.01.02', '24.1.2'),
])
def test_remove_leading_zeros(version: str, expected: str) -> None:
    assert remove_leading_zeros(version) == expected


@pytest.mark.parametrize(('cp', 'version', 'restrict_version', 'expected'), [
    ('dev-util/foo', '1.2.3', 'major', 'dev-util/foo:1:'),
    ('dev-util/foo', '1.2.3', 'minor', 'dev-util/foo:1.2:'),
    ('dev-util/foo', '1.2.3', 'full', 'dev-util/foo'),
    ('dev-util/foo', '1.2.3', None, 'dev-util/foo'),
    ('dev-util/foo', '2.0', 'major', 'dev-util/foo:2:'),
    ('dev-util/foo', '2.0', 'minor', 'dev-util/foo:2.0:'),
    ('dev-util/foo', '2.0', 'full', 'dev-util/foo'),
    ('dev-util/foo', '2.0', '', 'dev-util/foo'),
])
def test_mask_version(cp: str, version: str, restrict_version: str | None, expected: str) -> None:
    assert mask_version(cp, version, restrict_version) == expected


def test_get_highest_matches_basic(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit',
                 side_effect=lambda _: ('cat/pkg', 'cat', 'pkg', '1.2.3'))
    mock_p.xmatch.return_value = ['cat/pkg-1.2.3', 'cat/pkg-1.2.2']
    mock_p.findname2.return_value = ('cat/pkg-1.2.3', '/repo/root')

    names = ['cat/pkg']
    repo_root = Path('/repo/root')
    dummy_settings = mocker.Mock()
    dummy_settings.restrict_version = {}
    result = get_highest_matches(names, repo_root, dummy_settings)
    assert result == ['cat/pkg-1.2.3']


def test_get_highest_matches_no_matches(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.xmatch.return_value = []
    names = ['cat/pkg']
    repo_root = Path('/repo/root')
    dummy_settings = mocker.Mock()
    result = get_highest_matches(names, repo_root, dummy_settings)
    assert result == []


def test_get_highest_matches_invalid_package_structure(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.xmatch.return_value = ['invalid']

    def raise_value_error(x: Any) -> NoReturn:
        msg = 'bad structure'
        raise ValueError(msg)

    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit', side_effect=raise_value_error)
    names = ['cat/pkg']
    repo_root = Path('/repo/root')
    dummy_settings = mocker.Mock()
    result = get_highest_matches(names, repo_root, dummy_settings)
    assert result == []


def test_get_highest_matches_wrong_repo_root(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.xmatch.return_value = ['cat/pkg-1.2.3']
    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.2.3'))
    mock_p.findname2.return_value = ('cat/pkg-1.2.3', '/other/root')
    names = ['cat/pkg']
    repo_root = Path('/repo/root')
    dummy_settings = mocker.Mock()
    result = get_highest_matches(names, repo_root, dummy_settings)
    assert result == []


def test_get_highest_matches_ignores_9999(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.xmatch.return_value = ['cat/pkg-9999']
    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '9999'))
    mock_p.findname2.return_value = ('cat/pkg-9999', '/repo/root')
    names = ['cat/pkg']
    repo_root = Path('/repo/root')
    dummy_settings = mocker.Mock()
    result = get_highest_matches(names, repo_root, dummy_settings)
    assert result == []


def test_catpkgsplit2_valid_atom(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.utils.portage.catpkgsplit')
    mock_catpkgsplit.return_value = ('cat', 'pkg', '1.2.3', 'r0')
    catpkgsplit2.cache_clear()
    result = catpkgsplit2('cat/pkg-1.2.3')
    assert result == ('cat', 'pkg', '1.2.3', 'r0')


def test_catpkgsplit2_valid_atom_with_revision(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.utils.portage.catpkgsplit')
    mock_catpkgsplit.return_value = ('cat', 'pkg', '1.2.3', 'r1')
    catpkgsplit2.cache_clear()
    result = catpkgsplit2('cat/pkg-1.2.3-r1')
    assert result == ('cat', 'pkg', '1.2.3', 'r1')


def test_catpkgsplit2_none_returned(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.utils.portage.catpkgsplit')
    mock_catpkgsplit.return_value = None
    catpkgsplit2.cache_clear()
    with pytest.raises(ValueError, match='Invalid atom:'):
        catpkgsplit2('invalid-atom')


def test_catpkgsplit2_wrong_tuple_size(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.utils.portage.catpkgsplit')
    mock_catpkgsplit.return_value = ('cat', 'pkg', '1.2.3')  # Only 3 elements
    catpkgsplit2.cache_clear()
    with pytest.raises(ValueError, match='Invalid atom:'):
        catpkgsplit2('cat/pkg-1.2.3')


def test_catpkgsplit2_category_none(mocker: MockerFixture) -> None:
    mock_catpkgsplit = mocker.patch('livecheck.utils.portage.catpkgsplit')
    mock_catpkgsplit.return_value = (None, 'pkg', '1.2.3', 'r0')
    catpkgsplit2.cache_clear()
    result = catpkgsplit2('pkg-1.2.3')
    assert result == (None, 'pkg', '1.2.3', 'r0')


@pytest.mark.parametrize(
    ('atom', 'cat', 'pkg', 'ebuild_version', 'revision', 'expected'),
    [
        # No revision or r0
        ('cat/pkg-1.2.3', 'cat', 'pkg', '1.2.3', 'r0', ('cat/pkg', 'cat', 'pkg', '1.2.3')),
        # With revision r1
        ('cat/pkg-1.2.3-r1', 'cat', 'pkg', '1.2.3', 'r1', ('cat/pkg', 'cat', 'pkg', '1.2.3-r1')),
        # With revision r2
        ('cat/pkg-2.0.0-r2', 'cat', 'pkg', '2.0.0', 'r2', ('cat/pkg', 'cat', 'pkg', '2.0.0-r2')),
        # No revision, just version
        ('cat/pkg-0.1', 'cat', 'pkg', '0.1', '', ('cat/pkg', 'cat', 'pkg', '0.1')),
    ])
def test_catpkg_catpkgsplit_variants(mocker: MockerFixture, atom: str, cat: str, pkg: str,
                                     ebuild_version: str, revision: str,
                                     expected: tuple[str, str, str, str]) -> None:
    mock_catpkgsplit2 = mocker.patch('livecheck.utils.portage.catpkgsplit2')
    mock_catpkgsplit2.return_value = (cat, pkg, ebuild_version, revision)
    catpkg_catpkgsplit.cache_clear()
    result = catpkg_catpkgsplit(atom)
    assert result == expected


def test_catpkg_catpkgsplit_category_none(mocker: MockerFixture) -> None:
    mock_catpkgsplit2 = mocker.patch('livecheck.utils.portage.catpkgsplit2')
    mock_catpkgsplit2.return_value = (None, 'pkg', '1.2.3', 'r0')
    catpkg_catpkgsplit.cache_clear()
    with pytest.raises(AssertionError):
        catpkg_catpkgsplit('pkg-1.2.3')


def test_catpkg_catpkgsplit_revision_r0(mocker: MockerFixture) -> None:
    mock_catpkgsplit2 = mocker.patch('livecheck.utils.portage.catpkgsplit2')
    mock_catpkgsplit2.return_value = ('cat', 'pkg', '1.2.3', 'r0')
    catpkg_catpkgsplit.cache_clear()
    result = catpkg_catpkgsplit('cat/pkg-1.2.3')
    assert result == ('cat/pkg', 'cat', 'pkg', '1.2.3')


def test_catpkg_catpkgsplit_revision_non_r0(mocker: MockerFixture) -> None:
    mock_catpkgsplit2 = mocker.patch('livecheck.utils.portage.catpkgsplit2')
    mock_catpkgsplit2.return_value = ('cat', 'pkg', '1.2.3', 'r5')
    catpkg_catpkgsplit.cache_clear()
    result = catpkg_catpkgsplit('cat/pkg-1.2.3-r5')
    assert result == ('cat/pkg', 'cat', 'pkg', '1.2.3-r5')


@pytest.mark.parametrize(
    ('match', 'aux_get_return', 'expected'),
    [
        (
            'cat/pkg-1.2.3',
            ['http://example.com/src.tar.gz mirror://gentoo/src.tar.gz'],
            'http://example.com/src.tar.gz',
        ),
        (
            'cat/pkg-1.2.3',
            ['mirror://gentoo/src.tar.gz ftp://example.com/src.tar.gz'],
            'mirror://gentoo/src.tar.gz',
        ),
        (
            'cat/pkg-1.2.3',
            ['ftp://example.com/src.tar.gz'],
            'ftp://example.com/src.tar.gz',
        ),
        (
            'cat/pkg-1.2.3',
            ['not_a_uri something_else'],
            '',
        ),
        (
            'cat/pkg-1.2.3',
            [''],
            '',
        ),
    ],
)
def test_get_first_src_uri_basic(mocker: MockerFixture, match: str, aux_get_return: str,
                                 expected: str) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.aux_get.return_value = aux_get_return
    result = get_first_src_uri(match)
    assert result == expected


def test_get_first_src_uri_with_search_dir(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.aux_get.return_value = ['https://example.com/foo.tar.gz']
    search_dir = Path('/some/dir')
    result = get_first_src_uri('cat/pkg-1.2.3', search_dir)
    mock_p.aux_get.assert_called_with('cat/pkg-1.2.3', ['SRC_URI'], mytree=str(search_dir))
    assert result == 'https://example.com/foo.tar.gz'


def test_get_first_src_uri_keyerror(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    mock_p.aux_get.side_effect = KeyError('not found')
    result = get_first_src_uri('cat/pkg-1.2.3')
    assert not result


def test_get_first_src_uri_multiple_lines(mocker: MockerFixture) -> None:
    mock_p = mocker.patch('livecheck.utils.portage.P')
    # Simulate multiple lines, each line is split
    mock_p.aux_get.return_value = [
        'not_a_uri',
        'https://foo.com/bar.tar.gz',
        'mirror://gentoo/baz.tar.gz',
    ]
    result = get_first_src_uri('cat/pkg-1.2.3')
    assert result == 'https://foo.com/bar.tar.gz'


def test_get_repository_root_if_inside_inside_overlay(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    # Setup fake repo structure
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    subdir = repo_root / 'cat' / 'pkg'
    subdir.mkdir(parents=True)
    # Patch portage.config and settings
    mock_settings = {
        'PORTDIR_OVERLAY': str(repo_root),
        'PORTDIR': str(tmp_path / 'main-repo'),
    }
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.side_effect = mock_settings.__getitem__
    mock_config.get.side_effect = mock_settings.get
    mocker.patch('livecheck.utils.portage.portage.config', return_value=mock_config)
    # Directory inside overlay
    result = get_repository_root_if_inside(subdir)
    assert result == (str(repo_root.resolve()), repo_root.name)


def test_get_repository_root_if_inside_inside_portdir(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    portdir = tmp_path / 'main-repo'
    portdir.mkdir()
    subdir = portdir / 'foo'
    subdir.mkdir()
    mock_settings = {
        'PORTDIR_OVERLAY': str(tmp_path / 'overlay'),
        'PORTDIR': str(portdir),
    }
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.side_effect = mock_settings.__getitem__
    mock_config.get.side_effect = mock_settings.get
    mocker.patch('livecheck.utils.portage.portage.config', return_value=mock_config)
    result = get_repository_root_if_inside(subdir)
    assert result == (str(portdir.resolve()), portdir.name)


def test_get_repository_root_if_inside_not_in_any_repo(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    overlay = tmp_path / 'overlay'
    overlay.mkdir()
    portdir = tmp_path / 'main-repo'
    portdir.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    mock_settings = {
        'PORTDIR_OVERLAY': str(overlay),
        'PORTDIR': str(portdir),
    }
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.side_effect = mock_settings.__getitem__
    mock_config.get.side_effect = mock_settings.get
    mocker.patch('livecheck.utils.portage.portage.config', return_value=mock_config)
    result = get_repository_root_if_inside(outside)
    assert result == ('', '')


def test_get_repository_root_if_inside_local_path_exclusion(mocker: MockerFixture,
                                                            tmp_path: Path) -> None:
    overlay = tmp_path / 'overlay'
    overlay.mkdir()
    portdir = tmp_path / 'main-repo'
    portdir.mkdir()
    # Simulate a /local/ path
    local_dir = tmp_path / 'local' / 'repo'
    local_dir.mkdir(parents=True)
    mock_settings = {
        'PORTDIR_OVERLAY': str(overlay),
        'PORTDIR': str(portdir),
    }
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.side_effect = mock_settings.__getitem__
    mock_config.get.side_effect = mock_settings.get
    mocker.patch('livecheck.utils.portage.portage.config', return_value=mock_config)
    result = get_repository_root_if_inside(local_dir)
    assert result == ('', '')


@pytest.mark.parametrize(('version', 'expected'), [
    ('1.2.3', False),
    ('1.2.3-alpha', True),
    ('1.2.3-beta', True),
    ('1.2.3-pre', True),
    ('1.2.3-dev', True),
    ('1.2.3-rc', True),
    ('1.2.3-ALPHA', True),
    ('1.2.3-BETA', True),
    ('1.2.3-PRE', True),
    ('1.2.3-DEV', True),
    ('1.2.3-RC', True),
    ('1.2.3-final', False),
    ('1.2.3-release', False),
    ('alpha', True),
    ('beta', True),
    ('pre', True),
    ('dev', True),
    ('rc', True),
    ('', False),
    ('1.2.3a', False),
    ('1.2.3b', False),
    ('1.2.3rc1', True),
    ('1.2.3dev1', True),
    ('1.2.3-pre1', True),
    ('1.2.3alpha', True),
    ('1.2.3beta', True),
    ('1.2.3rc', True),
    ('1.2.3dev', True),
    ('1.2.3-rc2', True),
    ('1.2.3-dev2', True),
    ('1.2.3-pre2', True),
])
def test_is_version_development(version: str, expected: bool) -> None:  # noqa: FBT001
    assert is_version_development(version) == expected


@pytest.mark.parametrize(('a', 'b', 'expected'), [
    ('foobar', 'foo', 'bar'),
    ('foo', 'foobar', ''),
    ('foobar', 'foobar', ''),
    ('foobar', '', 'foobar'),
    ('', 'foobar', ''),
    ('abcde', 'abc', 'de'),
    ('abc', 'abcde', ''),
    ('abc', 'abc', ''),
    ('abc', 'def', 'abc'),
    ('prefix_rest', 'prefix_', 'rest'),
    ('prefix_rest', 'prefix', '_rest'),
    ('prefix', 'prefix', ''),
    ('prefix', 'pre', 'fix'),
    ('', '', ''),
])
def test_remove_initial_match_various_cases(a: str, b: str, expected: str) -> None:
    assert remove_initial_match(a, b) == expected


@pytest.mark.parametrize(('old', 'new', 'vercmp_result', 'expected'), [
    ('1.2.3', '1.2.4', -1, True),
    ('1.2.3', '1.2.3', 0, False),
    ('1.2.4', '1.2.3', 1, False),
    ('2.0', '2.1', -1, True),
    ('2.1', '2.0', 1, False),
    ('1.0', '1.0.0', -1, True),
    ('1.0.0', '1.0', 1, False),
])
def test_compare_versions(mocker: MockerFixture, old: str, new: str, vercmp_result: int,
                          expected: bool) -> None:  # noqa: FBT001
    mock_vercmp = mocker.patch('livecheck.utils.portage.vercmp', return_value=vercmp_result)
    result = compare_versions(old, new)
    mock_vercmp.assert_called_once_with(old, new)
    assert result is expected


@pytest.mark.parametrize(
    ('distdir_value', 'expected'),
    [
        ('/custom/distdir', Path('/custom/distdir')),
        ('', Path('/var/cache/distfiles')),
        (None, Path('/var/cache/distfiles')),
    ],
)
def test_get_distdir(mocker: MockerFixture, distdir_value: str | None, expected: Path) -> None:
    mock_settings = {'DISTDIR': distdir_value} if distdir_value is not None else {}
    mock_config = mocker.MagicMock()
    mock_config.get.side_effect = mock_settings.get
    mocker.patch('livecheck.utils.portage.portage.config', return_value=mock_config)
    result = get_distdir()
    assert result == expected


@pytest.mark.parametrize(
    ('ebuild_path', 'doebuild_return', 'expected'),
    [
        ('/path/to/foo.ebuild', 0, True),
        ('/path/to/bar.ebuild', 1, False),
        ('/path/to/baz.ebuild', -1, False),
    ],
)
def test_fetch_ebuild_basic(mocker: MockerFixture, ebuild_path: str, doebuild_return: int,
                            expected: bool) -> None:  # noqa: FBT001
    mock_config = mocker.MagicMock()
    mock_portage = mocker.patch('livecheck.utils.portage.portage')
    mock_portage.config.return_value = mock_config
    mock_portage.doebuild.return_value = doebuild_return

    result = fetch_ebuild(ebuild_path)
    mock_portage.config.assert_called_once_with(clone=mock_portage.settings)
    mock_portage.doebuild.assert_called_once_with(ebuild_path,
                                                  'fetch',
                                                  settings=mock_config,
                                                  tree='porttree')
    assert result is expected


@pytest.mark.parametrize(
    ('ebuild_path', 'doebuild_return', 'expected'),
    [
        ('/path/to/foo.ebuild', 0, True),
        ('/path/to/bar.ebuild', 1, False),
        ('/path/to/baz.ebuild', -1, False),
    ],
)
def test_digest_ebuild_basic(mocker: MockerFixture, ebuild_path: str, doebuild_return: int,
                             expected: bool) -> None:  # noqa: FBT001
    mock_config = mocker.MagicMock()
    mock_portage = mocker.patch('livecheck.utils.portage.portage')
    mock_portage.config.return_value = mock_config
    mock_portage.doebuild.return_value = doebuild_return

    result = digest_ebuild(ebuild_path)
    mock_portage.config.assert_called_once_with(clone=mock_portage.settings)
    mock_portage.doebuild.assert_called_once_with(ebuild_path,
                                                  'digest',
                                                  settings=mock_config,
                                                  tree='porttree')
    assert result is expected


@pytest.mark.parametrize(
    ('clean_return', 'unpack_return', 'workdir_exists', 'workdir_is_dir', 'expected'),
    [
        # clean fails
        (1, 0, True, True, ''),
        # unpack fails
        (0, 1, True, True, ''),
        # workdir does not exist
        (0, 0, False, True, ''),
        # workdir exists but is not a dir
        (0, 0, True, False, ''),
        # workdir exists and is a dir
        (0, 0, True, True, '/some/workdir'),
    ],
)
def test_unpack_ebuild(
        mocker: MockerFixture,
        clean_return: int,
        unpack_return: int,
        workdir_exists: bool,  # noqa: FBT001
        workdir_is_dir: bool,  # noqa: FBT001
        expected: str) -> None:
    mock_config = mocker.MagicMock()
    mock_portage = mocker.patch('livecheck.utils.portage.portage')
    mock_portage.config.return_value = mock_config
    mock_portage.doebuild.side_effect = [clean_return, unpack_return]
    mock_config.__getitem__.return_value = '/some/workdir'

    mock_path = mocker.patch('livecheck.utils.portage.Path')
    mock_workdir = mock_path.return_value
    mock_workdir.exists.return_value = workdir_exists
    mock_workdir.is_dir.return_value = workdir_is_dir
    mock_workdir.__str__.return_value = '/some/workdir'

    result = unpack_ebuild('/path/to/foo.ebuild')

    assert result == expected
    mock_portage.config.assert_called_once_with(clone=mock_portage.settings)
    # Only call doebuild for clean and unpack if clean succeeds
    if clean_return != 0:
        assert mock_portage.doebuild.call_count == 1
        mock_portage.doebuild.assert_any_call('/path/to/foo.ebuild',
                                              'clean',
                                              settings=mock_config,
                                              tree='porttree')
    else:
        assert mock_portage.doebuild.call_count == 2
        mock_portage.doebuild.assert_any_call('/path/to/foo.ebuild',
                                              'clean',
                                              settings=mock_config,
                                              tree='porttree')
        mock_portage.doebuild.assert_any_call('/path/to/foo.ebuild',
                                              'unpack',
                                              settings=mock_config,
                                              tree='porttree')
    if clean_return == 0 and unpack_return == 0:
        mock_path.assert_called_with('/some/workdir')
        mock_workdir.exists.assert_called_once()
    else:
        mock_path.assert_not_called()


@pytest.mark.parametrize(
    ('results', 'repo', 'ebuild', 'settings_attrs', 'expected_version'),
    [
        # Basic: transformation and regex not set, sanitize_version used, valid version
        (
            [{
                'tag': '1.2.4'
            }, {
                'tag': '1.2.3'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {},
                'regex_version': {},
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            '1.2.4',
        ),
        # Transformation function present
        (
            [{
                'tag': 'v1.2.5'
            }, {
                'tag': 'v1.2.4'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {
                    'cat/pkg': lambda tag: tag.lstrip('v')
                },
                'regex_version': {},
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            '1.2.5',
        ),
        # Regex version present
        (
            [{
                'tag': 'foo-1.2.6'
            }, {
                'tag': 'foo-1.2.5'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {},
                'regex_version': {
                    'cat/pkg': (r'foo-', '')
                },
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            '1.2.6',
        ),
        # Version filtered out by restrict_version_process
        (
            [{
                'tag': '1.2.7'
            }, {
                'tag': '1.2.8'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {},
                'regex_version': {},
                'restrict_version_process': '2.8',  # No version startswith 2.8
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            None,
        ),
        # Version filtered out by catpkg_catpkgsplit ValueError
        (
            [{
                'tag': 'bad_ver'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {},
                'regex_version': {},
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            None,
        ),
        # Accept version returns False
        (
            [{
                'tag': '1.2.9'
            }],
            'repo',
            'cat/pkg-1.2.3',
            {
                'transformations': {},
                'regex_version': {},
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
                'accept_version': False,
            },
            None,
        ),
        # Ebuild version has more than one dot, but tag version has none (should skip)
        (
            [{
                'tag': 'foo'
            }],
            'repo',
            'cat/pkg-1.2.3.4',
            {
                'transformations': {},
                'regex_version': {},
                'restrict_version_process': '',
                'restrict_version': {},
                'stable_version': {},
                'is_devel': lambda _: False,
            },
            None,
        ),
    ])
def test_get_last_version_cases(mocker: MockerFixture, results: Collection[Mapping[str, str]],
                                repo: str, ebuild: str, settings_attrs: Mapping[str, Any],
                                expected_version: str | None) -> None:
    # Patch catpkg_catpkgsplit to handle ebuild and tag versions
    def fake_catpkg_catpkgsplit(atom: str) -> tuple[str, str, str, str]:
        if atom == ebuild:
            return ('cat/pkg', 'cat', 'pkg', '1.2.3')
        if atom.startswith('cat/pkg-'):
            version = atom.split('-', 1)[1]
            if version == 'bad_ver':
                msg = 'bad version'
                raise ValueError(msg)
            return ('cat/pkg', 'cat', 'pkg', version)
        msg = 'bad atom'
        raise ValueError(msg)

    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit', side_effect=fake_catpkg_catpkgsplit)
    mocker.patch('livecheck.utils.portage.sanitize_version', side_effect=lambda v, _: v)
    mocker.patch('livecheck.utils.portage.compare_versions', side_effect=operator.lt)

    # Patch accept_version if requested
    if settings_attrs.get('accept_version', True) is False:
        mocker.patch('livecheck.utils.portage.accept_version', return_value=False)
    else:
        mocker.patch('livecheck.utils.portage.accept_version', return_value=True)

    # Build dummy settings
    dummy_settings = mocker.Mock()
    for k, v in settings_attrs.items():
        setattr(dummy_settings, k, v)

    result = get_last_version(results, repo, ebuild, dummy_settings)
    if expected_version is None:
        assert result == {}
    else:
        assert result['version'] == expected_version


def test_get_last_version_sanitize_version_returns_empty(mocker: MockerFixture) -> None:
    # Patch catpkg_catpkgsplit to handle ebuild and tag versions
    def fake_catpkg_catpkgsplit(atom: str) -> tuple[str, str, str, str]:
        if atom == 'cat/pkg-1.2.3':
            return ('cat/pkg', 'cat', 'pkg', '1.2.3')
        msg = 'bad atom'
        raise ValueError(msg)

    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit', side_effect=fake_catpkg_catpkgsplit)
    mocker.patch('livecheck.utils.portage.sanitize_version', return_value='')

    results = [{'tag': '1.2.3'}]
    repo = 'repo'
    ebuild = 'cat/pkg-1.2.3'
    dummy_settings = mocker.Mock()
    dummy_settings.transformations = {}
    dummy_settings.regex_version = {}
    dummy_settings.restrict_version_process = ''
    dummy_settings.restrict_version = {}
    dummy_settings.stable_version = {}
    dummy_settings.is_devel = lambda _: False

    result = get_last_version(results, repo, ebuild, dummy_settings)
    assert result == {}


def test_get_last_version_catpkg_catpkgsplit_raises_value_error(mocker: MockerFixture) -> None:
    # Patch catpkg_catpkgsplit to raise ValueError
    mocker.patch('livecheck.utils.portage.catpkg_catpkgsplit',
                 side_effect=[('cat/pkg', 'cat', 'pkg', '1.2.3'),
                              ValueError('bad atom')])

    results = [{'tag': '1.2.3'}]
    repo = 'repo'
    ebuild = 'cat/pkg-1.2.3'
    dummy_settings = mocker.Mock()
    dummy_settings.transformations = {}
    dummy_settings.regex_version = {}
    dummy_settings.restrict_version_process = ''
    dummy_settings.restrict_version = {}
    dummy_settings.stable_version = {}
    dummy_settings.is_devel = lambda _: False

    result = get_last_version(results, repo, ebuild, dummy_settings)
    assert result == {}


@pytest.mark.parametrize(
    ('ebuild_version', 'version', 'catpkg', 'settings_attrs', 'expected'),
    [
        # ebuild_version is development, should return True
        ('1.2.3-alpha', '1.2.4', 'cat/pkg', {
            'stable_version': {},
            'is_devel': lambda _: False,
        }, True),
        # settings.is_devel returns True, should return True
        ('1.2.3', '1.2.4', 'cat/pkg', {
            'stable_version': {},
            'is_devel': lambda _: True,
        }, True),
        # stable_version regex matches version, should return True
        ('1.2.3', '2.0.0', 'cat/pkg', {
            'stable_version': {
                'cat/pkg': r'^2\..*'
            },
            'is_devel': lambda _: False,
        }, True),
        # version is development, should return False
        ('1.2.3', '1.2.4-beta', 'cat/pkg', {
            'stable_version': {},
            'is_devel': lambda _: False,
        }, False),
        # stable_version regex does not match version, should return False
        ('1.2.3', '3.0.0', 'cat/pkg', {
            'stable_version': {
                'cat/pkg': r'^2\..*'
            },
            'is_devel': lambda _: False,
        }, False),
        # Neither development nor stable, should return True
        ('1.2.3', '1.2.4', 'cat/pkg', {
            'stable_version': {},
            'is_devel': lambda _: False,
        }, True),
        # Both ebuild_version and version are not development, but stable_version is set and matches
        ('1.2.3', '2.1.0', 'cat/pkg', {
            'stable_version': {
                'cat/pkg': r'^2\..*'
            },
            'is_devel': lambda _: False,
        }, True),
        # Both ebuild_version and version are not development, but stable_version is set and does
        # not match.
        ('1.2.3', '3.1.0', 'cat/pkg', {
            'stable_version': {
                'cat/pkg': r'^2\..*'
            },
            'is_devel': lambda _: False,
        }, False),
    ])
def test_accept_version_cases(mocker: MockerFixture, ebuild_version: str, version: str, catpkg: str,
                              settings_attrs: Mapping[str,
                                                      Any], expected: bool) -> None:  # noqa: FBT001
    # Patch is_version_development to match the real implementation
    mocker.patch(
        'livecheck.utils.portage.is_version_development',
        side_effect=lambda v: 'alpha' in v or 'beta' in v or 'dev' in v or 'rc' in v or 'pre' in v)
    # Patch re.match to use the real re.match
    mocker.patch('livecheck.utils.portage.re', real_re)
    # Build dummy settings
    dummy_settings = mocker.Mock()
    for k, v in settings_attrs.items():
        setattr(dummy_settings, k, v)
    result = accept_version(ebuild_version, version, catpkg, dummy_settings)
    assert result is expected
