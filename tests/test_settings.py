from __future__ import annotations

from typing import TYPE_CHECKING, Any
import json
import operator

from livecheck import settings
import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import Mock

    from pytest_mock import MockerFixture


def test_livecheck_settings_defaults() -> None:
    s = settings.LivecheckSettings()
    assert isinstance(s.branches, dict)
    assert isinstance(s.custom_livechecks, dict)
    assert isinstance(s.dotnet_projects, dict)
    assert isinstance(s.go_sum_uri, dict)
    assert isinstance(s.type_packages, dict)
    assert isinstance(s.no_auto_update, set)
    assert isinstance(s.sha_sources, dict)
    assert isinstance(s.transformations, dict)
    assert isinstance(s.yarn_base_packages, dict)
    assert isinstance(s.yarn_packages, dict)
    assert isinstance(s.jetbrains_packages, dict)
    assert isinstance(s.keep_old, dict)
    assert isinstance(s.gomodule_packages, dict)
    assert isinstance(s.gomodule_path, dict)
    assert isinstance(s.nodejs_packages, dict)
    assert isinstance(s.nodejs_path, dict)
    assert isinstance(s.development, dict)
    assert isinstance(s.composer_packages, dict)
    assert isinstance(s.composer_path, dict)
    assert isinstance(s.regex_version, dict)
    assert isinstance(s.restrict_version, dict)
    assert isinstance(s.sync_version, dict)
    assert isinstance(s.stable_version, dict)
    assert s.auto_update_flag is False
    assert s.debug_flag is False
    assert s.development_flag is False
    assert s.git_flag is False
    assert s.keep_old_flag is False
    assert s.progress_flag is False
    assert not s.restrict_version_process


def test_is_devel_returns_flag_when_not_in_development() -> None:
    s = settings.LivecheckSettings(development_flag=True)
    assert s.is_devel('cat/pkg') is True


def test_is_devel_returns_value_from_development_dict() -> None:
    s = settings.LivecheckSettings(development={'cat/pkg': False}, development_flag=True)
    assert s.is_devel('cat/pkg') is False


def test_is_devel_returns_default_when_not_set() -> None:
    s = settings.LivecheckSettings()
    assert s.is_devel('cat/pkg') is False


def test_livecheck_settings_mutable_fields_are_independent() -> None:
    s1 = settings.LivecheckSettings()
    s2 = settings.LivecheckSettings()
    s1.branches['foo'] = 'bar'
    assert 'foo' not in s2.branches


def test_livecheck_settings_repr_and_eq() -> None:
    s1 = settings.LivecheckSettings(branches={'a': 'b'})
    s2 = settings.LivecheckSettings(branches={'a': 'b'})
    assert repr(s1).startswith('LivecheckSettings(')
    assert s1 == s2


def test_livecheck_settings_custom_livechecks_and_types() -> None:
    s = settings.LivecheckSettings(custom_livechecks={'cat/pkg': ('url', 'regex')},
                                   type_packages={'cat/pkg': settings.TYPE_REGEX})
    assert s.custom_livechecks['cat/pkg'] == ('url', 'regex')
    assert s.type_packages['cat/pkg'] == settings.TYPE_REGEX


@pytest.fixture
def mock_utils(mocker: MockerFixture) -> Any:
    # Patch livecheck.utils with a dummy transformation function
    module = mocker.patch('livecheck.utils')
    module.utils_tf = operator.itemgetter(slice(None, None, -1))
    return module


def make_json_file(tmp_path: Path, rel_path: Path | str, data: Any) -> Path:
    file_path = tmp_path / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data))
    return file_path


def test_gather_settings_basic(tmp_path: Path) -> None:
    data = {'type': settings.TYPE_REGEX, 'url': 'https://example.com', 'regex': 'v([0-9.]+)'}
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    result = settings.gather_settings(tmp_path)
    assert 'cat/pkg' in result.custom_livechecks
    assert result.custom_livechecks['cat/pkg'] == ('https://example.com', 'v([0-9.]+)')
    assert result.type_packages['cat/pkg'] == settings.TYPE_REGEX


def test_gather_settings_with_transformation_function(tmp_path: Path) -> None:
    data = {
        'type': settings.TYPE_REGEX,
        'url': 'https://example.com',
        'regex': 're3_v([0-9.]+)',
        'transformation_function': 'handle_re'
    }
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    result = settings.gather_settings(tmp_path)
    assert 'cat/pkg' in result.transformations
    assert callable(result.transformations['cat/pkg'])
    assert result.transformations['cat/pkg']('re3_v1') == '1'


def test_gather_settings_with_utils_transformation(tmp_path: Path, mocker: MockerFixture,
                                                   mock_utils: Mock) -> None:
    # Patch special.handlers to not have the function, so it falls back to utils
    data = {
        'type': settings.TYPE_REGEX,
        'url': 'https://example.com',
        'regex': 'v([0-9.]+)',
        'transformation_function': 'dash_to_underscore'
    }
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    result = settings.gather_settings(tmp_path)
    assert 'cat/pkg' in result.transformations
    assert result.transformations['cat/pkg']('a-b-c') == 'a_b_c'


def test_gather_settings_unknown_transformation(tmp_path: Path, mocker: MockerFixture) -> None:
    data = {
        'type': settings.TYPE_REGEX,
        'url': 'https://example.com',
        'regex': 'v([0-9.]+)',
        'transformation_function': 'not_found'
    }
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    with pytest.raises(settings.UnknownTransformationFunction):
        settings.gather_settings(tmp_path)


def test_gather_settings_handles_various_fields(tmp_path: Path) -> None:
    data = {
        'type': settings.TYPE_DIRECTORY,
        'url': 'https://example.com/dir',
        'branch': 'main',
        'no_auto_update': True,
        'sha_source': 'https://example.com/sha',
        'yarn_base_package': 'foo',
        'yarn_packages': ['bar', 'baz'],
        'go_sum_uri': 'https://example.com/go.sum',
        'dotnet_project': 'proj.csproj',
        'jetbrains': True,
        'keep_old': True,
        'gomodule': True,
        'gomodule_path': 'mod/path',
        'nodejs': True,
        'nodejs_path': 'node/path',
        'development': True,
        'composer': True,
        'composer_path': 'composer/path',
        'pattern_version': r'v(\d+)',
        'replace_version': r'\1',
        'restrict_version': 'major',
        'sync_version': 'sync',
        'stable_version': r'stable'
    }
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    result = settings.gather_settings(tmp_path)
    assert result.branches['cat/pkg'] == 'main'
    assert 'cat/pkg' in result.no_auto_update
    assert result.sha_sources['cat/pkg'] == 'https://example.com/sha'
    assert result.yarn_base_packages['cat/pkg'] == 'foo'
    assert result.yarn_packages['cat/pkg'] == {'bar', 'baz'}
    assert result.go_sum_uri['cat/pkg'] == 'https://example.com/go.sum'
    assert result.dotnet_projects['cat/pkg'] == 'proj.csproj'
    assert result.jetbrains_packages['cat/pkg'] is True
    assert result.keep_old['cat/pkg'] is True
    assert result.gomodule_packages['cat/pkg'] is True
    assert result.gomodule_path['cat/pkg'] == 'mod/path'
    assert result.nodejs_packages['cat/pkg'] is True
    assert result.nodejs_path['cat/pkg'] == 'node/path'
    assert result.development['cat/pkg'] is True
    assert result.composer_packages['cat/pkg'] is True
    assert result.composer_path['cat/pkg'] == 'composer/path'
    assert result.regex_version['cat/pkg'] == (r'v(\d+)', r'\1')
    assert result.restrict_version['cat/pkg'] == 'major'
    assert result.sync_version['cat/pkg'] == 'sync'
    assert result.stable_version['cat/pkg'] == r'stable'


def test_gather_settings_invalid_json_logs_and_skips(tmp_path: Path, mocker: MockerFixture) -> None:
    # Patch logger to check for error
    logger = mocker.patch('livecheck.settings.log')
    file_path = tmp_path / 'cat/pkg/livecheck.json'
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('{invalid json')
    result = settings.gather_settings(tmp_path)
    logger.exception.assert_called()
    # Should not raise, and settings should be empty
    assert not result.custom_livechecks


def test_gather_settings_invalid_type_logs_error(tmp_path: Path, mocker: MockerFixture) -> None:
    logger = mocker.patch('livecheck.settings.log')
    data = {'type': 'unknown_type'}
    make_json_file(tmp_path, 'cat/pkg/livecheck.json', data)
    settings.gather_settings(tmp_path)
    logger.error.assert_any_call('Unknown "type" in %s.', mocker.ANY)
