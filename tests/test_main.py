# ruff: noqa: FBT001
from __future__ import annotations

from typing import TYPE_CHECKING, Any
import logging
import subprocess as sp

from defusedxml import ElementTree as ET  # noqa: N817
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

    from _pytest.logging import LogCaptureFixture
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
    settings = mocker.MagicMock()
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
    settings.maven_packages = set()
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


def test_do_main_sha_sources_parse_url_fixes(mocker: MockerFixture, tmp_path: Path,
                                             mock_settings: Mock) -> None:
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    top_hash = ''
    hash_date = '20250101'
    url = 'https://example.com'
    hook_dir = None
    search_dir = tmp_path
    cp = f'{cat}/{pkg}'
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('SHA="1234567"\n', encoding='utf-8')
    # settings.sha_sources.get() returns a value
    mock_settings.sha_sources = {cp: 'https://sha.example.com'}
    mocker.patch('livecheck.main.parse_url', return_value=('', 'top_hash', '20250101', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='12345678')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mock_write = mocker.patch('livecheck.main.Path.write_text')
    do_main(cat=cat,
            ebuild_version=ebuild_version,
            pkg=pkg,
            search_dir=search_dir,
            settings=mock_settings,
            last_version='',
            top_hash=top_hash,
            hash_date=hash_date,
            url=url,
            hook_dir=hook_dir)
    mock_write.assert_not_called()


def test_do_main_logs_update_not_possible_when_requirements_fail(mocker: MockerFixture,
                                                                 tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.composer_packages = set()
    mock_settings.maven_packages = set()
    mock_settings.dotnet_projects = {cp}
    mock_settings.yarn_base_packages = set()
    mock_settings.nodejs_packages = set()
    mock_settings.gomodule_packages = set()
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
    mocker.patch('livecheck.main.Path.write_text')
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mocker.patch('livecheck.main.check_dotnet_requirements', return_value=False)
    mocker.patch('livecheck.main.check_composer_requirements', return_value=True)
    mocker.patch('livecheck.main.check_yarn_requirements', return_value=True)
    mocker.patch('livecheck.main.check_nodejs_requirements', return_value=True)
    mocker.patch('livecheck.main.check_gomodule_requirements', return_value=True)
    mock_log = mocker.patch('livecheck.main.log')
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
    mock_log.warning.assert_any_call('Update is not possible.')


def test_do_main_keep_old_true_git_flag_true(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.keep_old = {cp: True}
    mock_settings.git_flag = True
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


def test_do_main_keep_old_true_git_flag_true_rename_failure(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.keep_old = {cp: True}
    mock_settings.git_flag = True
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
    mock_log = mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run',
                 side_effect=sp.CalledProcessError(1, 'git', 'Git command failed'))
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
    mock_log.exception.assert_called_once_with('Error moving `%s` to `%s`.', mocker.ANY, mocker.ANY)


def test_do_main_keep_old_true_git_flag_true_write_text_failure(mocker: MockerFixture,
                                                                tmp_path: Path,
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
    mock_settings.keep_old = {cp: True}
    mock_settings.git_flag = True
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
    mock_log = mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.Path.write_text', side_effect=OSError)
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
    mock_log.exception.assert_called_once_with('Error writing `%s`.', mocker.ANY)


def test_do_main_pkgdev_commit_raises_called_process_error(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.git_flag = True
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
    mocker.patch('livecheck.main.Path.write_text')
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])

    def fake_sp_run(args: Any, **kwargs: Any) -> Any:
        if args[0] == 'pkgdev' and args[1] == 'commit':
            raise sp.CalledProcessError(1, args, 'pkgdev commit failed')
        return mocker.Mock(returncode=0)

    mocker.patch('livecheck.main.sp.run', side_effect=fake_sp_run)
    mock_log = mocker.patch('livecheck.main.log')
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
    mock_log.exception.assert_any_call('Error committing %s.', mocker.ANY)


def test_do_main_digest_ebuild_returns_false(mocker: MockerFixture, tmp_path: Path,
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
    # digest_ebuild returns False
    mock_digest = mocker.patch('livecheck.main.digest_ebuild', return_value=False)
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
    mock_digest.assert_called()
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_gomodule_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.gomodule_packages = {cp}
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
    mock_update_gomodule_ebuild = mocker.patch('livecheck.main.update_gomodule_ebuild')
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
    mock_update_gomodule_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', mocker.ANY, {})
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_nodejs_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.nodejs_packages = {cp}
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
    mock_update_nodejs_ebuild = mocker.patch('livecheck.main.update_nodejs_ebuild')
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
    mock_update_nodejs_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', mocker.ANY, {})
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_composer_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.composer_packages = {cp}
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
    mock_update_composer_ebuild = mocker.patch('livecheck.main.update_composer_ebuild')
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
    mock_update_composer_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', mocker.ANY, {})
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_maven_packages(mocker: MockerFixture, tmp_path: Path, mock_settings: Mock) -> None:
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
    mock_settings.auto_update_flag = True
    mock_settings.maven_packages = {cp}
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
    mocker.patch('livecheck.main.check_maven_requirements', return_value=True)
    mock_update_maven_ebuild = mocker.patch('livecheck.main.update_maven_ebuild')
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
    mock_update_maven_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', mocker.ANY, {})
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_yarn_base_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.yarn_base_packages = {cp: ''}
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
    mock_update_yarn_ebuild = mocker.patch('livecheck.main.update_yarn_ebuild')
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
    mock_update_yarn_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', '', 'pkg', mocker.ANY)
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_go_sum_uri(mocker: MockerFixture, tmp_path: Path, mock_settings: Mock) -> None:
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
    mock_settings.auto_update_flag = True
    mock_settings.go_sum_uri = {cp: ''}
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
    mock_update_go_ebuild = mocker.patch('livecheck.main.update_go_ebuild')
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
    mock_update_go_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', 'abcdef1', '')
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_dotnet_projects(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.dotnet_projects = {cp: ''}
    mocker.patch('livecheck.main.check_dotnet_requirements', return_value=True)
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
    mock_update_dotnet_ebuild = mocker.patch('livecheck.main.update_dotnet_ebuild')
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
    mock_update_dotnet_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild', '')
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_jetbrains_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.jetbrains_packages = {cp}
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
    mock_update_jetbrains_ebuild = mocker.patch('livecheck.main.update_jetbrains_ebuild')
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
    mock_update_jetbrains_ebuild.assert_called_once_with(
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild')
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_type_checksum_updates_checksum_metadata(mocker: MockerFixture, tmp_path: Path,
                                                         mock_settings: Mock) -> None:
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    last_version = '1.0.1'
    top_hash = 'abcdef1'
    hash_date = '20240101'
    url = 'https://example.com'
    hook_dir = None
    search_dir = tmp_path
    cp = f'{cat}/{pkg}'
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('SHA="1234567"\n', encoding='utf-8')
    mock_settings.auto_update_flag = True
    mock_settings.type_packages = {cp: 'checksum'}
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
    mocker.patch('livecheck.main.remove_gomodule_url', return_value='Not the same content')
    mock_write = mocker.patch('livecheck.main.Path.write_text')
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mock_update_checksum_metadata = mocker.patch('livecheck.main.update_checksum_metadata')
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
    mock_update_checksum_metadata.assert_called_once_with(f'{cp}-{last_version}', url,
                                                          str(search_dir))
    mock_write.assert_called_once_with('abcdef1', encoding='utf-8')


def test_do_main_old_content_differs_with_gomodule_packages(mocker: MockerFixture, tmp_path: Path,
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
    mock_settings.auto_update_flag = True
    mock_settings.sha_sources = {}
    mock_settings.keep_old = {}
    mock_settings.git_flag = False
    mock_settings.gomodule_packages = {cp}
    mocker.patch('livecheck.main.remove_gomodule_url', return_value='Not the same content')
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
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mocker.patch('livecheck.main.execute_hooks')
    mocker.patch('livecheck.main.Path.read_text',
                 side_effect=['SHA="1234567"\n', 'SHA="abcdef1"\n'])
    write_text_mock = mocker.patch('livecheck.main.Path.write_text')
    process_submodules_mock = mocker.patch('livecheck.main.process_submodules',
                                           side_effect=lambda *_, **__: 'SHA="abcdef1"\n')
    mock_update_gomodule_ebuild = mocker.patch('livecheck.main.update_gomodule_ebuild')
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
    assert mock_update_gomodule_ebuild.called
    assert write_text_mock.call_count >= 2
    assert process_submodules_mock.called


def test_do_main_old_content_differs_with_gomodule_packages_digest_false(
        mocker: MockerFixture, tmp_path: Path, mock_settings: Mock) -> None:
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
    mock_settings.auto_update_flag = True
    mock_settings.sha_sources = {}
    mock_settings.keep_old = {}
    mock_settings.git_flag = False
    mock_settings.keep_old_flag = True
    mock_settings.gomodule_packages = {cp}
    mocker.patch('livecheck.main.remove_gomodule_url', return_value='Not the same content')
    mocker.patch('livecheck.main.get_old_sha', return_value='1234567')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.catpkg_catpkgsplit', return_value=(cp, cat, pkg, last_version))
    mocker.patch('livecheck.main.catpkgsplit2', return_value=(cat, pkg, last_version, 'r0'))
    mocker.patch('livecheck.main.str_version', side_effect=lambda v, _: v)
    # digest_ebuild returns True for first call, False for second call
    mock_digest = mocker.patch('livecheck.main.digest_ebuild', side_effect=[True, True, False])
    mocker.patch('livecheck.main.P.getFetchMap', return_value={})
    mocker.patch('livecheck.main.is_sha', return_value=True)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mocker.patch('livecheck.main.execute_hooks')
    # Simulate old_content != content
    mocker.patch('livecheck.main.Path.read_text',
                 side_effect=['SHA="1234567"\n', 'SHA="abcdef1"\n'])
    write_text_mock = mocker.patch('livecheck.main.Path.write_text')
    process_submodules_mock = mocker.patch('livecheck.main.process_submodules',
                                           side_effect=lambda *_, **__: 'SHA="abcdef1"\n')
    mocker.patch('livecheck.main.update_gomodule_ebuild')
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
    assert write_text_mock.call_count >= 2
    assert process_submodules_mock.called
    assert mock_digest.call_count == 3
    assert mock_digest.call_args_list[-1][0][0] == (
        f'{search_dir}/{cat}/{pkg}/{pkg}-{last_version}.ebuild')


def test_do_main_not_is_sha_and_cp_in_tag_name_functions(mocker: MockerFixture, tmp_path: Path,
                                                         mock_settings: Mock) -> None:
    # Setup
    cat = 'cat'
    pkg = 'pkg'
    ebuild_version = '1.0.0'
    last_version = '1.0.1'
    top_hash = 'not-a-sha'
    hash_date = ''
    url = 'https://example.com'
    hook_dir = None
    search_dir = tmp_path
    cp = f'{cat}/{pkg}'
    ebuild_path = tmp_path / f'{cat}/{pkg}/{pkg}-1.0.0.ebuild'
    ebuild_path.parent.mkdir(parents=True)
    ebuild_path.write_text('SHA="1234567"\n', encoding='utf-8')
    mock_settings.auto_update_flag = True
    mock_settings.sha_sources = {}
    mock_settings.no_auto_update = set()
    mock_settings.keep_old = {}
    mock_settings.git_flag = False
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.replace_date_in_ebuild', side_effect=lambda v, _, __: v)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.catpkg_catpkgsplit', return_value=(cp, cat, pkg, last_version))
    mocker.patch('livecheck.main.catpkgsplit2', return_value=(cat, pkg, last_version, 'r0'))
    mocker.patch('livecheck.main.str_version', side_effect=lambda v, _: v)
    mocker.patch('livecheck.main.digest_ebuild', return_value=True)
    mocker.patch('livecheck.main.P.getFetchMap', return_value={})
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.process_submodules', side_effect=lambda *a, **_: a[1])
    mocker.patch('livecheck.main.execute_hooks')
    mocker.patch('livecheck.main.Path.read_text', return_value='SHA="1234567"\n')
    mock_write = mocker.patch('livecheck.main.Path.write_text')
    mocker.patch('livecheck.main.sp.run', return_value=mocker.Mock(returncode=0))
    mock_is_sha = mocker.patch('livecheck.main.is_sha', return_value=False)
    mocker.patch('livecheck.main.TAG_NAME_FUNCTIONS', {cp: lambda *_: 'tagged-sha'})
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
    mock_is_sha.assert_called_with(top_hash)
    mock_write.assert_called_once_with('tagged-sha', encoding='utf-8')


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


@pytest.mark.parametrize((
    'attrib_type',
    'get_latest_meta_func',
    'get_latest_meta_return',
    'expected',
), [
    (
        'github',
        'get_latest_github_metadata',
        ('latest_version', 'top_hash'),
        ('latest_version', 'top_hash', '', ''),
    ),
    (
        'sourcehut',
        'get_latest_sourcehut_metadata',
        'latest_version',
        ('latest_version', '', '', ''),
    ),
    (
        'bitbucket',
        'get_latest_bitbucket_metadata',
        ('latest_version', 'top_hash'),
        ('latest_version', 'top_hash', '', ''),
    ),
    (
        'gitlab',
        'get_latest_gitlab_metadata',
        ('latest_version', 'top_hash'),
        ('latest_version', 'top_hash', '', ''),
    ),
    (
        'metacpan',
        'get_latest_metacpan_metadata',
        'latest_version',
        ('latest_version', '', '', ''),
    ),
    (
        'pecl',
        'get_latest_pecl_metadata',
        'latest_version',
        ('latest_version', '', '', ''),
    ),
    (
        'rubygems',
        'get_latest_rubygems_metadata',
        'latest_version',
        ('latest_version', '', '', ''),
    ),
    (
        'sourceforge',
        'get_latest_sourceforge_metadata',
        'latest_version',
        ('latest_version', '', '', ''),
    ),
    (
        'pypi',
        'get_latest_pypi_metadata',
        ('latest_version', 'url'),
        ('latest_version', '', '', 'url'),
    ),
    (
        'pypi',
        'get_latest_pypi_metadata',
        ('', 'url'),
        ('', '', '', ''),
    ),
])
def test_parse_metadata_cases(attrib_type: str, get_latest_meta_func: str,
                              get_latest_meta_return: str, expected: tuple[str, ...],
                              tmp_path: Path, mocker: MockerFixture) -> None:
    mock_get_latest_meta = mocker.patch(f'livecheck.main.{get_latest_meta_func}',
                                        return_value=get_latest_meta_return)
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
    remote_id_element1.text = attrib_type
    remote_id_element1.attrib = {'type': attrib_type}
    upstream_element1 = [remote_id_element1]
    mock_root = mocker.Mock()
    mock_root.findall.return_value = [upstream_element1]
    mock_et_parse.return_value.getroot.return_value = mock_root
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == expected
    if attrib_type == 'gitlab':
        mock_get_latest_meta.assert_called_once_with(attrib_type, attrib_type, ebuild, settings)
    else:
        mock_get_latest_meta.assert_called_once_with(attrib_type, ebuild, settings)


def test_parse_metadata_parse_error(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_et_parse = mocker.patch('livecheck.main.ET.parse')
    mock_et_parse.side_effect = ET.ParseError('Parse error')
    repo_root = tmp_path
    cat_dir = tmp_path / 'cat' / 'pkg'
    cat_dir.mkdir(parents=True)
    metadata_file = cat_dir / 'metadata.xml'
    metadata_file.write_text('<pkgmetadata></pkgmetadata>', encoding='utf-8')
    ebuild = 'cat/pkg-1.0.0'
    settings = mocker.Mock()
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == ('', '', '', '')


def test_parse_metadata_no_remote_id(mocker: MockerFixture, tmp_path: Path) -> None:
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
    remote_id_element1.text = ''
    remote_id_element1.attrib = {}
    upstream_element1 = [remote_id_element1]
    mock_root = mocker.Mock()
    mock_root.findall.return_value = [upstream_element1]
    mock_et_parse.return_value.getroot.return_value = mock_root
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == ('', '', '', '')


def test_parse_metadata_no_remote_id2(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_et_parse = mocker.patch('livecheck.main.ET.parse')
    repo_root = tmp_path
    cat_dir = tmp_path / 'cat' / 'pkg'
    cat_dir.mkdir(parents=True)
    metadata_file = cat_dir / 'metadata.xml'
    metadata_file.write_text('<pkgmetadata></pkgmetadata>', encoding='utf-8')
    ebuild = 'cat/pkg-1.0.0'
    settings = mocker.Mock()
    remote_id_element1 = mocker.Mock()
    remote_id_element1.tag = 'remote-id2'
    remote_id_element1.text = ''
    remote_id_element1.attrib = {}
    upstream_element1 = [remote_id_element1]
    mock_root = mocker.Mock()
    mock_root.findall.return_value = [upstream_element1]
    mock_et_parse.return_value.getroot.return_value = mock_root
    result = parse_metadata(str(repo_root), ebuild, settings)
    assert result == ('', '', '', '')


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


def test_get_props_no_names_argument_yields(mocker: MockerFixture, fake_repo: Path,
                                            mock_settings2: Mock) -> None:
    # Setup: create two ebuild files in the repo
    ebuild1 = fake_repo / 'cat1' / 'pkg1' / 'pkg1-1.0.0.ebuild'
    ebuild2 = fake_repo / 'cat2' / 'pkg2' / 'pkg2-2.0.0.ebuild'
    ebuild1.parent.mkdir(parents=True, exist_ok=True)
    ebuild2.parent.mkdir(parents=True, exist_ok=True)
    ebuild1.write_text('EAPI=8\n', encoding='utf-8')
    ebuild2.write_text('EAPI=8\n', encoding='utf-8')
    mocker.patch('livecheck.main.get_highest_matches',
                 return_value=['cat1/pkg1-1.0.0', 'cat2/pkg2-2.0.0'])

    def fake_catpkg_catpkgsplit(arg: str) -> tuple[str, str, str, str]:
        if arg == 'cat1/pkg1-1.0.0':
            return ('cat1/pkg1', 'cat1', 'pkg1', '1.0.0')
        if arg == 'cat2/pkg2-2.0.0':
            return ('cat2/pkg2', 'cat2', 'pkg2', '2.0.0')
        return ('cat/pkg', 'cat', 'pkg', '1.0.0')

    mocker.patch('livecheck.main.catpkg_catpkgsplit', side_effect=fake_catpkg_catpkgsplit)
    mocker.patch('livecheck.main.get_first_src_uri', return_value='https://example.com/pkg.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.parse_url',
                 side_effect=[
                     ('ver1', 'sha1', 'date1', 'url1'),
                     ('ver2', 'sha2', 'date2', 'url2'),
                 ])
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=None,
                  exclude=[]))
    assert results == [
        ('cat1', 'pkg1', '1.0.0', 'ver1', 'sha1', 'date1', 'url1'),
        ('cat2', 'pkg2', '2.0.0', 'ver2', 'sha2', 'date2', 'url2'),
    ]


def test_get_props_no_names_argument_exclude_all(mocker: MockerFixture, fake_repo: Path,
                                                 mock_settings2: Mock) -> None:
    ebuild1 = fake_repo / 'cat1' / 'pkg1' / 'pkg1-1.0.0.ebuild'
    ebuild1.parent.mkdir(parents=True, exist_ok=True)
    ebuild1.write_text('EAPI=8\n', encoding='utf-8')
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat1/pkg1-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat1/pkg1', 'cat1', 'pkg1', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri', return_value='https://example.com/pkg.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.log')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=None,
                  exclude=['cat1/pkg1']))
    assert results == []


def test_get_props_no_names_argument_no_matches(mocker: MockerFixture, fake_repo: Path,
                                                mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=[])
    mocker.patch('livecheck.main.log')
    with pytest.raises(click.Abort):
        list(
            get_props(search_dir=fake_repo,
                      repo_root=fake_repo,
                      settings=mock_settings2,
                      names=None,
                      exclude=[]))


def test_get_props_type_davinci_calls_get_latest_davinci_package(mocker: MockerFixture,
                                                                 fake_repo: Path,
                                                                 mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'davinci'}
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
    mock_get_latest_davinci_package = mocker.patch('livecheck.main.get_latest_davinci_package',
                                                   return_value='davinci_ver')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'davinci_ver', '', '', '')]
    mock_get_latest_davinci_package.assert_called_once_with('pkg')


def test_get_props_type_directory_calls_get_latest_directory_package(mocker: MockerFixture,
                                                                     fake_repo: Path,
                                                                     mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'directory'}
    mock_settings2.custom_livechecks = {'cat/pkg': ('https://dir.example.com', None)}
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
    mock_get_latest_directory_package = mocker.patch('livecheck.main.get_latest_directory_package',
                                                     return_value=('dir_ver', 'dir_url'))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'dir_ver', '', '', 'dir_url')]
    mock_get_latest_directory_package.assert_called_once_with('https://dir.example.com',
                                                              'cat/pkg-1.0.0', mock_settings2)


def test_get_props_type_repology_calls_get_latest_repology(mocker: MockerFixture, fake_repo: Path,
                                                           mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'repology'}
    mock_settings2.custom_livechecks = {'cat/pkg': ('repology_pkg', None)}
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
    mock_get_latest_repology = mocker.patch('livecheck.main.get_latest_repology',
                                            return_value='repo_ver')
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'repo_ver', '', '', '')]
    mock_get_latest_repology.assert_called_once_with('cat/pkg-1.0.0', mock_settings2,
                                                     'repology_pkg')


def test_get_props_type_regex_calls_get_latest_regex_package(mocker: MockerFixture, fake_repo: Path,
                                                             mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'regex'}
    mock_settings2.custom_livechecks = {'cat/pkg': ('https://regex.example.com', 'v([0-9.]+)')}
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
    mock_get_latest_regex_package = mocker.patch(
        'livecheck.main.get_latest_regex_package',
        return_value=('regex_ver', 'regex_date', 'regex_url'))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'regex_ver', '', 'regex_date', 'regex_url')]
    mock_get_latest_regex_package.assert_called_once_with(
        'cat/pkg-1.0.0', 'https://regex.example.com', 'v([0-9.]+)', mock_settings2)


def test_get_props_type_checksum_calls_get_latest_checksum_package(mocker: MockerFixture,
                                                                   fake_repo: Path,
                                                                   mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'checksum'}
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
    mock_get_latest_checksum_package = mocker.patch('livecheck.main.get_latest_checksum_package',
                                                    return_value=('cs_ver', 'cs_date', 'cs_url'))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'cs_ver', '', 'cs_date', 'cs_url')]
    mock_get_latest_checksum_package.assert_called_once_with('https://example.com/pkg-1.0.0.tar.gz',
                                                             'cat/pkg-1.0.0', str(fake_repo))


def test_get_props_type_commit_calls_parse_url(mocker: MockerFixture, fake_repo: Path,
                                               mock_settings2: Mock) -> None:
    mock_settings2.type_packages = {'cat/pkg': 'commit'}
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('egit_url', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.log')
    mock_parse_url = mocker.patch(
        'livecheck.main.parse_url',
        return_value=('commit_ver', 'commit_sha', 'commit_date', 'commit_url'))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'commit_ver', 'commit_sha', 'commit_date',
                        'commit_url')]
    mock_parse_url.assert_called_once_with('egit_url/commit/',
                                           'cat/pkg-1.0.0',
                                           mock_settings2,
                                           force_sha=True)


def test_get_props_with_egit_repo_and_branch(mocker: MockerFixture, fake_repo: Path,
                                             mock_settings2: Mock) -> None:
    # Setup mocks for get_highest_matches and catpkg_catpkgsplit
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    # get_egit_repo returns egit url and branch
    egit_url = 'https://github.com/org/repo.git'
    branch_name = 'main'
    mock_get_egit_repo = mocker.patch('livecheck.main.get_egit_repo',
                                      return_value=(egit_url, branch_name))
    mocker.patch('livecheck.main.get_old_sha', return_value='abcdef1')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mock_log = mocker.patch('livecheck.main.log')
    # parse_url returns a version, sha, date, url
    mock_parse_url = mocker.patch(
        'livecheck.main.parse_url',
        return_value=('ver', 'sha', 'date', 'https://github.com/org/repo.git/commit/abcdef1'))
    # settings.type_packages is empty so default path is taken
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'ver', 'sha', 'date',
                        'https://github.com/org/repo.git/commit/abcdef1')]
    # Ensure get_egit_repo was called and branch was set in settings
    mock_get_egit_repo.assert_called_once()
    assert mock_settings2.branches['cat/pkg'] == branch_name
    mock_parse_url.assert_called_once_with(egit_url + '/commit/' + 'abcdef1',
                                           'cat/pkg-1.0.0',
                                           mock_settings2,
                                           force_sha=True)
    mock_log.info.assert_any_call('Processing: %s | Version: %s', 'cat/pkg', '1.0.0')


def test_get_props_sync_version_yields(mocker: MockerFixture, fake_repo: Path,
                                       mock_settings2: Mock) -> None:
    # Setup: catpkg is in settings.sync_version
    mock_settings2.sync_version = {'cat/pkg': 'cat/pkg-2.0.0'}
    mocker.patch(
        'livecheck.main.get_highest_matches',
        side_effect=[
            ['cat/pkg-1.0.0'],  # for main get_highest_matches
            ['cat/pkg-2.0.0'],  # for sync_version get_highest_matches
        ])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 side_effect=[('cat/pkg', 'cat', 'pkg', '1.0.0'),
                              ('cat/pkg', 'cat', 'pkg', '2.0.0')])
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=['https://homepage'])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    # Should yield with last_version from sync_version (with -r* removed)
    assert results == [('cat', 'pkg', '1.0.0', '2.0.0', '', '', '')]


def test_get_props_sync_version_no_matches(mocker: MockerFixture, fake_repo: Path,
                                           mock_settings2: Mock) -> None:
    mock_settings2.sync_version = {'cat/pkg': 'cat/pkg-2.0.0'}
    mocker.patch(
        'livecheck.main.get_highest_matches',
        side_effect=[
            ['cat/pkg-1.0.0'],  # for main get_highest_matches
            [],  # for sync_version get_highest_matches
        ])
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
    mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == []


def test_get_props_no_last_version_no_top_hash_uses_homepage(mocker: MockerFixture, fake_repo: Path,
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
    mocker.patch('livecheck.main.P.aux_get',
                 return_value=['https://homepage1', 'https://homepage2'])
    mocker.patch('livecheck.main.log')
    parse_url_mock = mocker.patch(
        'livecheck.main.parse_url',
        side_effect=[
            ('', '', '', ''),  # for src_uri
            ('ver', 'sha', 'date', 'url'),  # for homepage1
        ])
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'ver', 'sha', 'date', 'url')]
    assert parse_url_mock.call_count == 2
    parse_url_mock.assert_any_call('https://example.com/pkg-1.0.0.tar.gz',
                                   'cat/pkg-1.0.0',
                                   mock_settings2,
                                   force_sha=False)
    parse_url_mock.assert_any_call('https://homepage1',
                                   'cat/pkg-1.0.0',
                                   mock_settings2,
                                   force_sha=False)


def test_get_props_no_last_version_no_top_hash_no_homepage(mocker: MockerFixture, fake_repo: Path,
                                                           mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_latest_repology', return_value='')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=[])
    mocker.patch('livecheck.main.log')
    mock_get_content = mocker.patch('livecheck.special.directory.get_content')
    mock_get_content.return_value = mocker.MagicMock(text='')
    parse_url_mock = mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == []
    parse_url_mock.assert_called_once_with('https://example.com/pkg-1.0.0.tar.gz',
                                           'cat/pkg-1.0.0',
                                           mock_settings2,
                                           force_sha=False)


def test_get_props_no_last_version_no_top_hash_uses_directory(mocker: MockerFixture,
                                                              fake_repo: Path,
                                                              mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.get_latest_repology', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get', return_value=[])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    get_latest_directory_package_mock = mocker.patch('livecheck.main.get_latest_directory_package',
                                                     return_value=('dir_ver', 'dir_url'))
    mock_settings2.custom_livechecks = {'cat/pkg': ('https://dir.example.com', None)}
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'dir_ver', '', '', 'dir_url')]
    get_latest_directory_package_mock.assert_called_once_with(
        'https://example.com/pkg-1.0.0.tar.gz', 'cat/pkg-1.0.0', mock_settings2)


def test_get_props_no_last_version_no_top_hash_uses_directory_loop_homes(
        mocker: MockerFixture, fake_repo: Path, mock_settings2: Mock) -> None:
    mocker.patch('livecheck.main.get_highest_matches', return_value=['cat/pkg-1.0.0'])
    mocker.patch('livecheck.main.catpkg_catpkgsplit',
                 return_value=('cat/pkg', 'cat', 'pkg', '1.0.0'))
    mocker.patch('livecheck.main.get_latest_repology', return_value='')
    mocker.patch('livecheck.main.get_first_src_uri',
                 return_value='https://example.com/pkg-1.0.0.tar.gz')
    mocker.patch('livecheck.main.get_egit_repo', return_value=('', ''))
    mocker.patch('livecheck.main.get_old_sha', return_value='')
    mocker.patch('livecheck.main.catpkgsplit2', return_value=('cat', 'pkg', '1.0.0', 'r0'))
    mocker.patch('livecheck.main.compare_versions', return_value=True)
    mocker.patch('livecheck.main.remove_leading_zeros', side_effect=lambda v: v)
    mocker.patch('livecheck.main.P.aux_get',
                 return_value=['https://homepage1', 'https://homepage2'])
    mocker.patch('livecheck.main.log')
    mocker.patch('livecheck.main.parse_url', return_value=('', '', '', ''))
    get_latest_directory_package_mock = mocker.patch('livecheck.main.get_latest_directory_package',
                                                     side_effect=[('', ''), ('', ''),
                                                                  ('dir_ver', 'dir_url')])
    mock_settings2.custom_livechecks = {'cat/pkg': ('https://dir.example.com', None)}
    results = list(
        get_props(search_dir=fake_repo,
                  repo_root=fake_repo,
                  settings=mock_settings2,
                  names=['cat/pkg'],
                  exclude=[]))
    assert results == [('cat', 'pkg', '1.0.0', 'dir_ver', '', '', 'dir_url')]
    get_latest_directory_package_mock.assert_any_call('https://homepage1', 'cat/pkg-1.0.0',
                                                      mock_settings2)


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


def test_main_exclude_logs_message(mocker: MockerFixture, runner: CliRunner, tmp_path: Path,
                                   caplog: LogCaptureFixture) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_props')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('livecheck.main.os.access', return_value=True)
    mocker.patch('livecheck.main.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', return_value=True)
    with caplog.at_level(logging.DEBUG):
        result = runner.invoke(main, ['--exclude', 'cat/pkg', '--exclude', 'cat2/pkg2'])
    assert result.exit_code == 0
    assert 'Excluding cat/pkg, cat2/pkg2.' in caplog.messages


def test_main_git_check_program_git(mocker: MockerFixture, runner: CliRunner, tmp_path: Path,
                                    caplog: LogCaptureFixture) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_props')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('livecheck.main.os.access', return_value=True)
    mocker.patch('livecheck.main.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', return_value=False)
    result = runner.invoke(main, ['--git', '--auto-update', '--working-dir', str(tmp_path)])
    assert result.exit_code != 0
    assert 'Git is not installed.' in caplog.messages


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


def test_main_auto_update_git_happy_path(mocker: MockerFixture, runner: CliRunner,
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
                 ])
    args = ['--auto-update', '--git', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code == 0
    mock_do_main.assert_called_once_with(
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


def test_main_auto_update_git_missing_git_dir(mocker: MockerFixture, runner: CliRunner,
                                              tmp_path: Path) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('os.access', return_value=True)
    mocker.patch('pathlib.Path.is_dir', side_effect=lambda _=None: False)
    mocker.patch('livecheck.main.check_program', return_value=True)
    args = ['--auto-update', '--git', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code != 0


def test_main_auto_update_git_git_not_installed(mocker: MockerFixture, runner: CliRunner,
                                                tmp_path: Path) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('os.access', return_value=True)
    mocker.patch('pathlib.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', side_effect=lambda prog, _: prog != 'git')
    args = ['--auto-update', '--git', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code != 0


def test_main_auto_update_git_git_dir_not_writable(mocker: MockerFixture, runner: CliRunner,
                                                   tmp_path: Path) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))

    def fake_os_access(path: Path, mode: int) -> bool:
        return '.git' not in str(path)

    mocker.patch('os.access', side_effect=fake_os_access)
    mocker.patch('pathlib.Path.is_dir', return_value=True)
    mocker.patch('livecheck.main.check_program', return_value=True)
    args = ['--auto-update', '--git', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code != 0


def test_main_auto_update_git_pkgdev_not_installed(mocker: MockerFixture, runner: CliRunner,
                                                   tmp_path: Path) -> None:
    mocker.patch('livecheck.main.chdir')
    mocker.patch('livecheck.main.setup_logging')
    mocker.patch('livecheck.main.gather_settings')
    mocker.patch('livecheck.main.get_repository_root_if_inside',
                 return_value=(str(tmp_path), 'repo'))
    mocker.patch('os.access', return_value=True)
    mocker.patch('pathlib.Path.is_dir', return_value=True)

    def fake_check_program(prog: str, args: Any) -> bool:
        if prog == 'git':
            return True
        return prog != 'pkgdev'

    mocker.patch('livecheck.main.check_program', side_effect=fake_check_program)
    args = ['--auto-update', '--git', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code != 0


def test_main_handles_exception_in_do_main(mocker: MockerFixture, runner: CliRunner,
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
    mocker.patch('livecheck.main.get_props',
                 return_value=[
                     ('cat', 'pkg', '1.0.0', '1.0.1', 'sha', 'date', 'url'),
                 ])
    mock_do_main = mocker.patch('livecheck.main.do_main', side_effect=Exception('fail in do_main'))
    args = ['--auto-update', '--working-dir', str(tmp_path), 'cat/pkg']
    result = runner.invoke(main, args)
    assert result.exit_code != 0
    assert mock_do_main.called
