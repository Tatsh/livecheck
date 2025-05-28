from __future__ import annotations

from typing import TYPE_CHECKING, Any

from livecheck.main import do_main, replace_date_in_ebuild
import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import Mock

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
