# ruff: noqa: FBT001
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.main import (
    do_main,
    execute_hooks,
    extract_restrict_version,
    get_egit_repo,
    get_old_sha,
    get_props,
    main,
    parse_metadata,
    parse_url,
    process_submodules,
    replace_date_in_ebuild,
    str_version,
)
import click
import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import Mock

    from click.testing import CliRunner
    from pytest_mock import MockerFixture

CP = 'sys-devel/gcc'


def test_replace_date_in_ebuild_full_date() -> None:
    ebuild = '20230101'
    new_date = '20240101'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '20240101'


def test_replace_date_in_ebuild_short_date() -> None:
    ebuild = '1.2.2_p230101-r1'
    new_date = '20240101'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '1.2.2_p240101'


def test_replace_date_in_ebuild_no_change() -> None:
    ebuild = '20230101-r1'
    new_date = '20230101'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '20230101-r1'


def test_replace_date_in_ebuild_invalid_date() -> None:
    ebuild = '2023'
    new_date = '20240101'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '2023'


def test_replace_date_in_ebuild_invalid_date2() -> None:
    ebuild = '12.0.1_p231124'
    new_date = '20240102'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '12.0.1_p240102'


def test_replace_date_in_ebuild_invalid_date3() -> None:
    ebuild = '231124'
    new_date = '20240102'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '240102'


def test_replace_date_in_ebuild_version_change() -> None:
    ebuild = '1.0.0_p20230101'
    new_date = '20240101'
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == '1.0.0_p20240101'


@pytest.fixture
def mock_settings(mocker: MockerFixture) -> Any:
    settings = mocker.Mock()
    settings.auto_update_flag = False
    settings.composer_packages = set()
    settings.custom_livechecks = {}
    settings.dotnet_projects = set()
    settings.git_flag = False
    settings.go_sum_uri = set()
    settings.gomodule_packages = set()
    settings.jetbrains_packages = set()
    settings.keep_old = {}
    settings.keep_old_flag = False
    settings.no_auto_update = set()
    settings.nodejs_packages = set()
    settings.progress_flag = False
    settings.sha_sources = {}
    settings.sync_version = {}
    settings.type_packages = {}
    settings.yarn_base_packages = set()
    return settings


def test_do_main_no_update(mocker: MockerFixture, tmp_path: Path, mock_settings: Mock) -> None:
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    last_version = '1.0.0'
    top_hash = ''
    hash_date = ''
    url = ''
    hook_dir = None
    search_dir = tmp_path
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('EAPI=8\n', encoding='utf-8')
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mock_compare = mocker.patch('livecheck.main.compare_versions', return_value=False)

    do_main(cat=cat,
            ebuild_version=ebuild_version,
            hash_date=hash_date,
            hook_dir=hook_dir,
            last_version=last_version,
            pkg=pkg,
            search_dir=search_dir,
            settings=mock_settings,
            top_hash=top_hash,
            url=url)
    mock_compare.assert_called_once_with(ebuild_version, last_version)


def test_do_main_update_with_sha(mocker: MockerFixture, tmp_path: Path,
                                 mock_settings: Mock) -> None:
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    last_version = '1.0.1'
    top_hash = 'abcdef1'
    hash_date = ''
    url = 'https://example.com'
    hook_dir = None
    search_dir = tmp_path
    cp = f'{cat}/{pkg}'
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('SHA="1234567"\n', encoding='utf-8')
    mock_settings.sha_sources = {}
    mock_settings.auto_update_flag = True
    mocker.patch('livecheck.main.get_old_sha', return_value='1234567')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.catpkg_catpkgsplit', return_value=(cp, cat, pkg, last_version))
    mocker.patch('livecheck.main.catpkgsplit2', return_value=(cat, pkg, last_version, 'r0'))
    mocker.patch('livecheck.main.str_version', side_effect=lambda v, _: v)
    mocker.patch('livecheck.main.digest_ebuild', return_value=True)
    mocker.patch('livecheck.main.P.getFetchMap', return_value={})
    mocker.patch('livecheck.main.is_sha', return_value=True)
    mocker.patch('livecheck.main.process_submodules', side_effect=lambda *a, **_: a[1])
    mocker.patch('livecheck.main.execute_hooks')
    mocker.patch('livecheck.main.Path.read_text', return_value='SHA="1234567"\n')
    mock_write = mocker.patch('livecheck.main.Path.write_text')
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))

    do_main(cat=cat,
            ebuild_version=ebuild_version,
            hash_date=hash_date,
            hook_dir=hook_dir,
            last_version=last_version,
            pkg=pkg,
            search_dir=search_dir,
            settings=mock_settings,
            top_hash=top_hash,
            url=url)
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_with_sha_source_and_no_top_hash(mocker: MockerFixture, tmp_path: Path,
                                                 mock_settings: Mock) -> None:
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    last_version = '1.0.1'
    top_hash = ''
    hash_date = ''
    url = 'https://example.com'
    hook_dir = None
    search_dir = tmp_path
    cp = f'{cat}/{pkg}'
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('SHA="1234567"\n', encoding='utf-8')

    mock_settings.sha_sources = {cp: 'https://sha.example.com'}
    mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='1234567')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.compare_versions', return_value=False)
    mock_write = mocker.patch('livecheck.main.Path.write_text')

    do_main(cat=cat,
            ebuild_version=ebuild_version,
            pkg=pkg,
            search_dir=search_dir,
            settings=mock_settings,
            last_version=last_version,
            top_hash=top_hash,
            hash_date=hash_date,
            url=url,
            hook_dir=hook_dir)

    mock_write.assert_not_called()


def test_process_submodules_no_submodules(mocker: MockerFixture) -> None:
    mock_submodules = mocker.patch('livecheck.main.SUBMODULES', autospec=True)
    mock_submodules.__contains__.return_value = False
    result = process_submodules('foo', 'ref', 'some content', 'https://github.com/org/repo')
    assert result == 'some content'


def test_process_submodules_github_repo(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.main.SUBMODULES', {'foo': [('subdir', 'SOME_SHA')]})
    mock_get_content = mocker.patch('livecheck.main.get_content')
    mock_get_content.return_value = mocker.Mock(json=lambda: {'sha': 'deadbeef'})
    contents = 'SOME_SHA="old_sha"\n'
    repo_uri = 'https://api.github.com/repos/org/repo'
    mocker.patch('livecheck.main.urlparse', return_value=mocker.Mock(path='/org/repo'))
    result = process_submodules('foo', 'main', contents, repo_uri)
    assert result == 'SOME_SHA="deadbeef"\n'


def test_process_submodules_non_github_repo(mocker: MockerFixture) -> None:
    mock_submodules = mocker.patch('livecheck.main.SUBMODULES', autospec=True)
    mock_get_content = mocker.patch('livecheck.main.get_content')
    mock_submodules.__contains__.return_value = True
    mock_submodules.__getitem__.return_value = ['submodule-dir']
    mock_get_content.return_value = mocker.Mock(json=lambda: {'sha': 'cafebabe'})
    contents = 'SUBMODULE_DIR_SHA="old_sha"\n'
    repo_uri = 'https://gitlab.com/org/repo'
    mocker.patch('livecheck.main.urlparse', return_value=mocker.Mock(path='/org/repo'))
    result = process_submodules('foo', 'main', contents, repo_uri)
    assert result == 'SUBMODULE_DIR_SHA="cafebabe"\n'


def test_process_submodules_multiple_items(mocker: MockerFixture) -> None:
    mock_submodules = mocker.patch('livecheck.main.SUBMODULES', autospec=True)
    mock_get_content = mocker.patch('livecheck.main.get_content')
    mock_submodules.__contains__.return_value = True
    mock_submodules.__getitem__.return_value = [('sub1', 'SHA1'), 'sub2']
    mock_get_content.side_effect = [
        mocker.Mock(json=lambda: {'sha': 'sha1'}),
        mocker.Mock(json=lambda: {'sha': 'sha2'})
    ]
    contents = 'SHA1="old_sha1"\nSUB2_SHA="old_sha2"\n'
    repo_uri = 'https://api.github.com/repos/org/repo'
    mocker.patch('livecheck.main.urlparse', return_value=mocker.Mock(path='/org/repo'))
    result = process_submodules('foo', 'main', contents, repo_uri)
    assert result == 'SHA1="sha1"\nSUB2_SHA="sha2"\n'


def test_process_submodules_get_content_not_ok_tuple_item(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.main.SUBMODULES', {'foo': [('subdir', 'SOME_SHA')]})
    mock_get_content = mocker.patch('livecheck.main.get_content')
    mock_response = mocker.Mock(ok=False)
    mock_get_content.return_value = mock_response
    contents = 'SOME_SHA="old_sha"\n'
    repo_uri = 'https://api.github.com/repos/org/repo'
    mocker.patch('livecheck.main.urlparse', return_value=mocker.Mock(path='/org/repo'))
    result = process_submodules('foo', 'main', contents, repo_uri)
    assert result == contents


@pytest.mark.parametrize(
    ('src_uri', 'is_gist_ret', 'is_github_ret', 'is_sourcehut_ret', 'is_pypi_ret',
     'is_jetbrains_ret', 'is_gitlab_ret', 'is_package_ret', 'is_pecl_ret', 'is_metacpan_ret',
     'is_rubygems_ret', 'is_sourceforge_ret', 'is_bitbucket_ret', 'expected'),
    [
        ('https://gist.github.com/foo/bar', True, False, False, False, False, False, False, False,
         False, False, False, False, ('', 'sha', 'date', 'https://gist.github.com/foo/bar')),
        ('https://github.com/foo/bar', False, True, False, False, False, False, False, False, False,
         False, False, False, ('ver', 'sha', 'date', 'https://github.com/foo/bar')),
        ('https://git.sr.ht/~foo/bar', False, False, True, False, False, False, False, False, False,
         False, False, False, ('ver', 'sha', 'date', 'https://git.sr.ht/~foo/bar')),
        ('https://pypi.org/project/foo', False, False, False, True, False, False, False, False,
         False, False, False, False, ('ver', '', '', 'url')),
        ('https://jetbrains.com/foo', False, False, False, False, True, False, False, False, False,
         False, False, False, ('ver', '', '', 'https://jetbrains.com/foo')),
        ('https://gitlab.com/foo/bar', False, False, False, False, False, True, False, False, False,
         False, False, False, ('ver', 'sha', 'date', 'https://gitlab.com/foo/bar')),
        ('https://example.com/package', False, False, False, False, False, False, True, False,
         False, False, False, False, ('ver', '', '', 'https://example.com/package')),
        ('https://pecl.php.net/package/foo', False, False, False, False, False, False, False, True,
         False, False, False, False, ('ver', '', '', 'https://pecl.php.net/package/foo')),
        ('https://metacpan.org/release/foo', False, False, False, False, False, False, False, False,
         True, False, False, False, ('ver', '', '', 'https://metacpan.org/release/foo')),
        ('https://rubygems.org/gems/foo', False, False, False, False, False, False, False, False,
         False, True, False, False, ('ver', '', '', 'https://rubygems.org/gems/foo')),
        ('https://sourceforge.net/projects/foo', False, False, False, False, False, False, False,
         False, False, False, True, False, ('ver', '', '', 'https://sourceforge.net/projects/foo')),
        ('https://bitbucket.org/foo/bar', False, False, False, False, False, False, False, False,
         False, False, False, True, ('ver', 'sha', 'date', 'https://bitbucket.org/foo/bar')),
        ('https://unknown.org/foo/bar', False, False, False, False, False, False, False, False,
         False, False, False, False, ('', '', '', 'https://unknown.org/foo/bar')),
        ('not_a_url', False, False, False, False, False, False, False, False, False, False, False,
         False, ('', '', '', 'not_a_url')),
    ])
def test_parse_url_variants(mocker: MockerFixture, src_uri: str, is_gist_ret: bool,
                            is_github_ret: bool, is_sourcehut_ret: bool, is_pypi_ret: bool,
                            is_jetbrains_ret: bool, is_gitlab_ret: bool, is_package_ret: bool,
                            is_pecl_ret: bool, is_metacpan_ret: bool, is_rubygems_ret: bool,
                            is_sourceforge_ret: bool, is_bitbucket_ret: bool,
                            expected: tuple[str, str, str, str]) -> None:
    mocker.patch('livecheck.main.is_pypi', return_value=is_pypi_ret)
    mocker.patch('livecheck.main.is_jetbrains', return_value=is_jetbrains_ret)
    mocker.patch('livecheck.main.is_package', return_value=is_package_ret)
    mocker.patch('livecheck.main.is_metacpan', return_value=is_metacpan_ret)
    mocker.patch('livecheck.main.is_sourceforge', return_value=is_sourceforge_ret)

    if src_uri == 'not_a_url':
        mocker.patch('livecheck.main.urlparse', return_value=mocker.Mock(hostname=None, path=''))
    else:
        mocker.patch('livecheck.main.urlparse',
                     return_value=mocker.Mock(hostname='host', path='/foo/bar'))

    mocker.patch('livecheck.main.get_latest_gist_package', return_value=('sha', 'date'))
    mocker.patch('livecheck.main.get_latest_github', return_value=('ver', 'sha', 'date'))
    mocker.patch('livecheck.main.get_latest_sourcehut', return_value=('ver', 'sha', 'date'))
    mocker.patch('livecheck.main.get_latest_pypi_package', return_value=('ver', 'url'))
    mocker.patch('livecheck.main.get_latest_jetbrains_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_gitlab', return_value=('ver', 'sha', 'date'))
    mocker.patch('livecheck.main.get_latest_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_pecl_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_metacpan_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_rubygems_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_sourceforge_package', return_value='ver')
    mocker.patch('livecheck.main.get_latest_bitbucket', return_value=('ver', 'sha', 'date'))
    mock_log_unhandled = mocker.patch('livecheck.main.log_unhandled_pkg')

    settings = mocker.Mock()
    ebuild = 'cat/pkg-1.0.0'
    force_sha = False

    result = parse_url(src_uri, ebuild, settings, force_sha=force_sha)
    assert result == expected

    if not any((is_gist_ret, is_github_ret, is_sourcehut_ret, is_pypi_ret, is_jetbrains_ret,
                is_gitlab_ret, is_package_ret, is_pecl_ret, is_metacpan_ret, is_rubygems_ret,
                is_sourceforge_ret, is_bitbucket_ret)) and src_uri != 'not_a_url':
        mock_log_unhandled.assert_called_once_with(ebuild, src_uri)
    else:
        mock_log_unhandled.assert_not_called()


def test_parse_metadata_no_metadata_file(tmp_path: Path, mocker: MockerFixture) -> None:
    repo_root = tmp_path
    ebuild = 'cat/pkg-1.0.0'
    settings = mocker.Mock()
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == ('', '', '', '')


def test_parse_metadata_with_multiple_upstreams(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch('livecheck.main.get_latest_github_metadata',
                 return_value=('latest_version', 'top_hash'))
    mock_get_latest_gitlab_meta = mocker.patch('livecheck.main.get_latest_gitlab_metadata')
    mock_et_parse = mocker.patch('livecheck.main.ET.parse')
    repo_root = tmp_path
    cat_dir = tmp_path / 'cat' / 'pkg'
    cat_dir.mkdir(parents=True)
    metadata_file = cat_dir / 'metadata.xml'
    metadata_file.write_text('<pkgmetadata></pkgmetadata>', encoding='utf-8')
    ebuild = 'cat/pkg-1.0.0'
    settings = mocker.Mock()
    remote_id_element1 = mocker.Mock()
    remote_id_element1.tag = 'remote-id'
    remote_id_element1.text = 'github:foo/bar'
    remote_id_element1.attrib = {'type': 'github'}
    remote_id_element2 = mocker.Mock()
    remote_id_element2.tag = 'remote-id'
    remote_id_element2.text = 'gitlab:foo/bar'
    remote_id_element2.attrib = {'type': 'gitlab'}
    upstream_element1 = [remote_id_element1]
    upstream_element2 = [remote_id_element2]
    mock_root = mocker.Mock()
    mock_root.findall.return_value = [upstream_element1, upstream_element2]
    mock_et_parse.return_value.getroot.return_value = mock_root
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == ('latest_version', 'top_hash', '', '')
    assert mock_get_latest_gitlab_meta.call_count == 0


@pytest.mark.parametrize(
    ('cp', 'expected'),
    [
        ('cat/pkg:slot:-1.2.3', ('cat/pkg-1.2.3', 'slot')),
        ('dev-libs/foo:main:-2.0.0', ('dev-libs/foo-2.0.0', 'main')),
        ('sys-apps/bar:0:-3.4.5', ('sys-apps/bar-3.4.5', '0')),
        ('cat/pkg-1.2.3', ('cat/pkg-1.2.3', '')),  # no match, returns as is
        ('cat/pkg:slot:1.2.3', ('cat/pkg:slot:1.2.3', '')),  # wrong format, returns as is
        ('cat/pkg:-1.2.3', ('cat/pkg:-1.2.3', '')),  # wrong format, returns as is
        ('cat/pkg:slot:-', ('cat/pkg-', 'slot')),  # version is empty
    ])
def test_extract_restrict_version(cp: str, expected: tuple[str, str]) -> None:
    assert extract_restrict_version(cp) == expected


@pytest.fixture
def mock_settings2(mocker: MockerFixture) -> Any:
    settings = mocker.Mock()
    settings.type_packages = {}
    settings.sync_version = {}
    settings.custom_livechecks = {}
    settings.branches = {}
    settings.restrict_version_process = None
    return settings


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / 'repo'
    ebuild_dir = repo_root / 'cat' / 'pkg'
    ebuild_dir.mkdir(parents=True)
    ebuild_file = ebuild_dir / 'pkg-1.0.0.ebuild'
    ebuild_file.write_text('EAPI=8\nSRC_URI="https://example.com/pkg-1.0.0.tar.gz"\n',
                           encoding='utf-8')
    return repo_root


def test_get_props_basic_yields(mocker: MockerFixture, fake_repo: Path,
                                mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.parse_url',
                 side_effect=[('', '', '', ''),
                              ('ver', 'sha', 'date', 'https://example.com/pkg-1.0.0.tar.gz')])
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'ver', 'sha', 'date',
                        'https://example.com/pkg-1.0.0.tar.gz')]


def test_get_props_exclude_package(mocker: MockerFixture, fake_repo: Path,
                                   mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.log')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=['cat/pkg']))
    assert results == []


def test_get_props_no_matches(mocker: MockerFixture, fake_repo: Path, mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=[])
    mocker.patch('livecheck.main.log')
    with pytest.raises(click.Abort):
        list(
            get_props(search_dir=fake_repo,
                      repo_root=fake_repo,
                      settings=mock_settings2,
                      names=['cat/pkg'],
                      exclude=[]))


def test_get_props_type_none_skips(mocker: MockerFixture, fake_repo: Path,
                                   mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': mocker.Mock()}
    mock_settings2.type_packages['cat/pkg'] = 'none'
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.log')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == []


def test_get_props_type_metadata_calls_parse_metadata(mocker: MockerFixture, fake_repo: Path,
                                                      mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'metadata'}
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.parse_metadata', return_value=('ver', 'sha', 'date', 'url'))
    mocker.patch('livecheck.main.log')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'ver', 'sha', 'date', 'url')]


@pytest.mark.parametrize(
    ('ebuild_content', 'url', 'expected'),
    [
        # SHA in ebuild, url unused
        ('SHA="abcdef1234567890abcdef1234567890abcdef12"\n', '',
         'abcdef1234567890abcdef1234567890abcdef12'),
        # COMMIT in ebuild, url unused
        ('COMMIT="1234567890abcdef1234567890abcdef12345678"\n', '',
         '1234567890abcdef1234567890abcdef12345678'),
        # EGIT_COMMIT in ebuild, url unused
        ('EGIT_COMMIT="fedcba9876543210fedcba9876543210fedcba98"\n', '',
         'fedcba9876543210fedcba9876543210fedcba98'),
        # No SHA/COMMIT in ebuild, url with sha at end
        ('EAPI=8\n', 'https://example.com/abcdef1', 'abcdef1'),
        # No SHA/COMMIT in ebuild, url with sha at end (slash)
        ('EAPI=8\n', 'https://example.com/abcdef1234567890abcdef1234567890abcdef12',
         'abcdef1234567890abcdef1234567890abcdef12'),
        # No SHA/COMMIT in ebuild, url with no slash
        ('EAPI=8\n', 'abcdef1', 'abcdef1'),
        # No SHA/COMMIT in ebuild, url empty
        ('EAPI=8\n', '', ''),
    ])
def test_get_old_sha(tmp_path: Path, ebuild_content: str, url: str, expected: str) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text(ebuild_content, encoding='utf-8')
    result = get_old_sha(ebuild_path, url)
    assert result == expected


def test_get_old_sha_multiple_lines(tmp_path: Path) -> None:
    content = ('EAPI=8\n'
               'SHA="1111111111111111111111111111111111111111"\n'
               'SHA="2222222222222222222222222222222222222222"\n')
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text(content, encoding='utf-8')
    result = get_old_sha(ebuild_path, '')
    assert result == '1111111111111111111111111111111111111111'


@pytest.mark.parametrize(
    ('ebuild_content', 'expected_egit', 'expected_branch'),
    [
        # Only EGIT_REPO_URI present, double quotes
        ('EGIT_REPO_URI="https://github.com/org/repo.git"\n', 'https://github.com/org/repo.git', ''
         ),
        # Only EGIT_REPO_URI present, single quotes
        ("EGIT_REPO_URI='https://gitlab.com/org/repo.git'\n", 'https://gitlab.com/org/repo.git', ''
         ),
        # Only EGIT_BRANCH present, double quotes
        ('EGIT_BRANCH="main"\n', '', 'main'),
        # Only EGIT_BRANCH present, single quotes
        ("EGIT_BRANCH='develop'\n", '', 'develop'),
        # Both present, EGIT_REPO_URI first
        ('EGIT_REPO_URI="https://github.com/org/repo.git"\nEGIT_BRANCH="main"\n',
         'https://github.com/org/repo.git', 'main'),
        # Both present, EGIT_BRANCH first
        ('EGIT_BRANCH="dev"\nEGIT_REPO_URI="https://github.com/org/repo.git"\n',
         'https://github.com/org/repo.git', 'dev'),
        # Both present, single quotes
        ("EGIT_BRANCH='dev'\nEGIT_REPO_URI='https://github.com/org/repo.git'\n",
         'https://github.com/org/repo.git', 'dev'),
        # Neither present
        ('EAPI=8\n', '', ''),
        # Both present, but with extra spaces
        ('   EGIT_REPO_URI="https://github.com/org/repo.git"   \n   EGIT_BRANCH="main"   \n', '', ''
         ),
    ])
def test_get_egit_repo(tmp_path: Path, ebuild_content: str, expected_egit: str,
                       expected_branch: str) -> None:
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text(ebuild_content, encoding='utf-8')
    egit, branch = get_egit_repo(ebuild_path)
    assert egit == expected_egit
    assert branch == expected_branch


def test_get_egit_repo_handles_empty_file(tmp_path: Path) -> None:
    ebuild_path = tmp_path / 'empty.ebuild'
    ebuild_path.write_text('', encoding='utf-8')
    egit, branch = get_egit_repo(ebuild_path)
    assert not egit
    assert not branch


def test_get_egit_repo_ignores_unrelated_lines(tmp_path: Path) -> None:
    content = ('EAPI=8\n'
               'DESCRIPTION="Test"\n'
               'HOMEPAGE="https://example.com"\n')
    ebuild_path = tmp_path / 'test.ebuild'
    ebuild_path.write_text(content, encoding='utf-8')
    egit, branch = get_egit_repo(ebuild_path)
    assert not egit
    assert not branch


@pytest.mark.parametrize(('version', 'sha', 'expected'), [
    ('1.2.3', '', '1.2.3'),
    ('1.2.3', None, '1.2.3'),
    ('1.2.3', 'abcdef1', '1.2.3 (abcdef1)'),
    ('20240101', 'deadbeef', '20240101 (deadbeef)'),
    ('', 'cafebabe', ' (cafebabe)'),
    ('', '', ''),
    ('v2.0.0', '1234567', 'v2.0.0 (1234567)'),
])
def test_str_version(version: str, sha: str, expected: str) -> None:
    assert str_version(version, sha) == expected


@pytest.fixture
def hook_dir(tmp_path: Path) -> Path:
    pre_dir = tmp_path / 'pre'
    post_dir = tmp_path / 'post'
    pre_dir.mkdir()
    post_dir.mkdir()
    pre_hook = pre_dir / 'hook1.sh'
    pre_hook.write_text('#!/bin/sh\necho pre', encoding='utf-8')
    pre_hook.chmod(0o755)
    post_hook = post_dir / 'hook2.sh'
    post_hook.write_text('#!/bin/sh\necho post', encoding='utf-8')
    post_hook.chmod(0o755)
    return tmp_path


def test_execute_hooks_runs_executable_files(mocker: MockerFixture, hook_dir: Path,
                                             tmp_path: Path) -> None:
    action = 'pre'
    cp = 'cat/pkg'
    search_dir = tmp_path
    str_old_version = '1.0.0'
    str_new_version = '1.0.1'
    old_sha = 'abc'
    new_sha = 'def'
    hash_date = '20240101'
    hook_path = hook_dir / action
    mocker.patch('os.access', return_value=True)
    mock_run = mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mocker.patch('livecheck.main.log.debug')
    execute_hooks(hook_dir, action, search_dir, cp, str_old_version, str_new_version, old_sha,
                  new_sha, hash_date)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert hook_path / 'hook1.sh' in args


def test_execute_hooks_skips_non_executable_files(mocker: MockerFixture, tmp_path: Path) -> None:
    action = 'pre'
    hook_path = tmp_path / action
    hook_path.mkdir()
    non_exec_file = hook_path / 'not_exec.sh'
    non_exec_file.write_text('#!/bin/sh\necho test', encoding='utf-8')
    non_exec_file.chmod(0o644)
    mocker.patch('os.access', return_value=False)
    mock_run = mocker.patch('livecheck.main.sp.run')
    mocker.patch('livecheck.main.log.debug')
    execute_hooks(tmp_path, action, tmp_path, 'cp', 'old', 'new', 'sha1', 'sha2', 'date')
    mock_run.assert_not_called()


def test_execute_hooks_handles_invalid_hook_dir_arg(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('os.access', return_value=True)
    mock_run = mocker.patch('livecheck.main.sp.run')
    execute_hooks(tmp_path, 'pre', tmp_path, 'cp', 'old', 'new', 'sha1', 'sha2', 'date')
    mock_run.assert_not_called()


def test_execute_hooks_handles_invalid_hook_dir_none(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_run = mocker.patch('livecheck.main.sp.run')
    execute_hooks(None, 'pre', tmp_path, 'cp', 'old', 'new', 'sha1', 'sha2', 'date')
    mock_run.assert_not_called()


def test_execute_hooks_handles_nonzero_returncode(mocker: MockerFixture, tmp_path: Path) -> None:
    action = 'pre'
    hook_path = tmp_path / action
    hook_path.mkdir()
    exec_file = hook_path / 'fail.sh'
    exec_file.write_text('#!/bin/sh\nexit 1', encoding='utf-8')
    exec_file.chmod(0o755)
    mocker.patch('os.access', return_value=True)
    mock_run = mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=1))
    mocker.patch('livecheck.main.log.debug')
    with pytest.raises(click.Abort):
        execute_hooks(tmp_path, action, tmp_path, 'cp', 'old', 'new', 'sha1', 'sha2', 'date')
    mock_run.assert_called_once()


@pytest.mark.parametrize(
    ('auto_update', 'debug', 'development', 'git', 'keep_old', 'progress', 'exclude',
     'package_names', 'working_dir', 'repo_root', 'repo_name', 'should_raise', 'expected_code'),
    [
        # Auto update, but not writable dir
        (True, False, False, False, False, False, (), (), None, '/repo', 'repo', True, None),
        # Not inside a repo
        (False, False, False, False, False, False, (), (), None, None, None, True, None),
        # Git enabled, but not auto_update
        (False, False, False, True, False, False, (), (), None, '/repo', 'repo', True, None),
        # Git enabled, auto_update, but .git missing
        (True, False, False, True, False, False, (), (), None, '/repo', 'repo', True, None),
    ])
def test_main_various_paths(mocker: MockerFixture, runner: CliRunner, auto_update: bool,
                            debug: bool, development: bool, git: bool, keep_old: bool,
                            progress: bool, exclude: tuple[str, ...],
                            package_names: tuple[str, ...], working_dir: Any, repo_root: str | None,
                            repo_name: str, should_raise: bool, expected_code: int | None) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings', return_value=mocker.Mock())
    mocker.patch('livecheck.main.get_props', return_value=[])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.P')
    mocker.patch('livecheck.main.digest_ebuild')
    mocker.patch('livecheck.main.execute_hooks')
    mocker.patch('livecheck.main.compare_versions', return_value=False)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.str_version', side_effect=lambda v, _: v)
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.process_submodules', side_effect=lambda *a, **_: a[1])
    mocker.patch('livecheck.main.is_sha', return_value=True)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.P.getFetchMap', return_value={})
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))

    def fake_os_access(path: Path | str, mode: int) -> bool:
        if auto_update and not git and not isinstance(path, str):
            return False
        if isinstance(path, str) and '.git' in path:
            return 'not-writable' not in path
        return True

    mocker.patch('os.access', side_effect=fake_os_access)
    mock_path = mocker.patch('pathlib.Path.is_dir')
    if git and auto_update:
        mock_path.side_effect = lambda self=None: '.git' in str(self)
    else:
        mock_path.return_value = True
    mock_get_repo = mocker.patch('livecheck.main.get_repository_root_if_inside')
    if repo_root is not None:
        mock_get_repo.return_value = (repo_root, repo_name)
    else:
        mock_get_repo.return_value = (None, None)

    def fake_check_program(prog: str, args: Any) -> bool:
        if prog == 'git':
            return 'git-not-installed' not in (repo_root or '')
        if prog == 'pkgdev':
            return 'pkg-dev-not-installed' not in (repo_root or '')
        return True

    mocker.patch('livecheck.main.check_program', side_effect=fake_check_program)
    if not should_raise:
        mocker.patch('livecheck.main.get_props',
                     return_value=[('cat', 'pkg', '1.0.0', '1.0.1', '', '', '')])
    args = []
    if auto_update:
        args.append('--auto-update')
    if debug:
        args.append('--debug')
    if development:
        args.append('--development')
    if git:
        args.append('--git')
    if keep_old:
        args.append('--keep-old')
    if progress:
        args.append('--progress')
    if working_dir:
        args.extend(['--working-dir', working_dir])
    for ex in exclude:
        args.extend(['--exclude', ex])
    if package_names:
        args.extend(package_names)

    if should_raise:
        result = runner.invoke(main, args)
        assert result.exit_code != 0
    else:
        result = runner.invoke(main, args)
        assert result.exit_code == expected_code


def test_main_calls_get_props_and_do_main(mocker: MockerFixture, runner: CliRunner,
                                          tmp_path: Path) -> None:
    mock_settings = mocker.Mock()
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings', return_value=mock_settings)
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('os.access', return_value=True)
    mocker.patch('pathlib.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', return_value=True)
    mock_do_main = mocker.patch('livecheck.main.do_main')
    mocker.patch('livecheck.main.get_props',
                 return_value=[
                     ('cat', 'pkg', '1.0.0', '1.0.1', 'sha', 'date', 'url'),
                     ('cat2', 'pkg2', '2.0.0', '2.0.1', 'sha2', 'date2', 'url2'),
                 ])
    result = runner.invoke(
        main, ['--auto-update', '--working-dir',
               str(tmp_path), 'cat/pkg', 'cat2/pkg2'])
    assert result.exit_code == 0
    assert mock_do_main.call_count == 2
    mock_do_main.assert_any_call(
        cat='cat',
        pkg='pkg',
        ebuild_version='1.0.0',
        last_version='1.0.1',
        top_hash='sha',
        hash_date='date',
        url='url',
        search_dir=tmp_path,
        settings=mock_settings,
        hook_dir=None,
    )
    mock_do_main.assert_any_call(
        cat='cat2',
        pkg='pkg2',
        ebuild_version='2.0.0',
        last_version='2.0.1',
        top_hash='sha2',
        hash_date='date2',
        url='url2',
        search_dir=tmp_path,
        settings=mock_settings,
        hook_dir=None,
    )


def test_main_handles_exception_in_get_props(mocker: MockerFixture, runner: CliRunner,
                                             tmp_path: Path) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('os.access', return_value=True)
    mocker.patch('pathlib.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', return_value=True)
    mocker.patch('livecheck.main.get_props', side_effect=Exception('fail'))
    result = runner.invoke(main, ['--working-dir', str(tmp_path)])
    assert result.exit_code != 0
