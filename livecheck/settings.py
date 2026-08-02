"""Settings."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import json
import logging
import re

from . import utils
from .constants import PACKAGE_MANAGERS
from .settings_model import LivecheckSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

__all__ = ('TYPE_CHANGELOG', 'TYPE_CHECKSUM', 'TYPE_COMMIT', 'TYPE_DAVINCI', 'TYPE_DIRECTORY',
           'TYPE_IDA_FREE', 'TYPE_LOCATION_CHECKSUM', 'TYPE_METADATA', 'TYPE_NONE', 'TYPE_REGEX',
           'TYPE_REPOLOGY', 'LivecheckSettings', 'gather_settings')

log = logging.getLogger(__name__)
TYPE_CHANGELOG = 'changelog'
TYPE_CHECKSUM = 'checksum'
TYPE_COMMIT = 'commit'
TYPE_DAVINCI = 'davinci'
TYPE_DIRECTORY = 'directory'
TYPE_IDA_FREE = 'ida-free'
TYPE_METADATA = 'metadata'
TYPE_NONE = 'none'
TYPE_REGEX = 'regex'
TYPE_REPOLOGY = 'repology'
TYPE_LOCATION_CHECKSUM = 'location+hash-check'

SETTINGS_TYPES = {
    TYPE_CHANGELOG, TYPE_CHECKSUM, TYPE_COMMIT, TYPE_DAVINCI, TYPE_DIRECTORY, TYPE_IDA_FREE,
    TYPE_METADATA, TYPE_NONE, TYPE_REGEX, TYPE_REPOLOGY, TYPE_LOCATION_CHECKSUM
}


class UnknownTransformationFunction(NameError):
    def __init__(self, tfs: str) -> None:
        super().__init__(f'Unknown transformation function: {tfs}')


def _apply_type(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                path: Path) -> bool:
    if parsed.get('type') is None:
        return True
    type_ = parsed['type'].lower()
    if type_ == TYPE_REGEX:
        if parsed.get('url') is None:
            log.error('No "url" in %s.', path)
            return False
        if parsed.get('regex') is None:
            log.error('No "regex" in %s.', path)
            return False
        settings.custom_livechecks[catpkg] = (parsed['url'], parsed['regex'])
    if type_ == TYPE_REPOLOGY:
        if parsed.get('package') is None:
            log.error('No "package" in %s.', path)
            return False
        settings.custom_livechecks[catpkg] = (parsed['package'], '')
    if type_ == TYPE_DIRECTORY:
        if parsed.get('url') is None:
            log.error('No "url" in %s.', path)
            return False
        settings.custom_livechecks[catpkg] = (parsed['url'], '')
    if type_ == TYPE_CHANGELOG:
        if parsed.get('url') is None:
            log.error('No "url" in %s.', path)
            return False
        check_instance(parsed['url'], 'url', 'url', path)
        settings.custom_livechecks[catpkg] = (parsed['url'], '')
    if type_ == TYPE_CHECKSUM and parsed.get('url') is not None:
        settings.custom_livechecks[catpkg] = (parsed['url'], '')
    if type_ == TYPE_LOCATION_CHECKSUM:
        if parsed.get('url') is None:
            log.error('No "url" in %s.', path)
            return False
        settings.custom_livechecks[catpkg] = (parsed['url'], '')
    if type_ not in SETTINGS_TYPES:
        log.error('Unknown "type" in %s.', path)
    else:
        settings.type_packages[catpkg] = type_
    return True


def _apply_general(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                   path: Path) -> bool:
    # Prevent circular import.
    import livecheck.special.handlers as sc  # ruff:ignore[import-outside-top-level]

    if parsed.get('branch'):
        check_instance(parsed['branch'], 'branch', 'string', path)
        settings.branches[catpkg] = parsed['branch']
    if 'no_auto_update' in parsed:
        check_instance(parsed['no_auto_update'],
                       'no_auto_update',
                       'bool',
                       path,
                       specific_value=True)
        settings.no_auto_update.add(catpkg)
    if parsed.get('transformation_function'):
        tfs = parsed['transformation_function']
        check_instance(tfs, 'transformation_function', 'string', path)
        try:
            tf: Callable[[str], str] = getattr(sc, tfs)
        except AttributeError:
            try:
                tf = getattr(utils, tfs)
            except AttributeError as e:
                raise UnknownTransformationFunction(tfs) from e
        settings.transformations[catpkg] = tf
    if parsed.get('sha_source'):
        check_instance(parsed['sha_source'], 'sha_source', 'url', path)
        settings.sha_sources[catpkg] = parsed['sha_source']
    if parsed.get('dist_github_repository'):
        check_instance(parsed['dist_github_repository'], 'dist_github_repository', 'string', path)
        settings.dist_github_repositories[catpkg] = parsed['dist_github_repository']
    if parsed.get('dist_github_release'):
        check_instance(parsed['dist_github_release'], 'dist_github_release', 'string', path)
        settings.dist_github_releases[catpkg] = parsed['dist_github_release']
    if 'jetbrains' in parsed:
        check_instance(parsed['jetbrains'], 'jetbrains', 'bool', path)
        settings.jetbrains_packages[catpkg] = parsed['jetbrains']
    if 'keep_old' in parsed:
        check_instance(parsed['keep_old'], 'keep_old', 'bool', path)
        settings.keep_old[catpkg] = parsed['keep_old']
    if 'development' in parsed:
        check_instance(parsed['development'], 'development', 'bool', path)
        settings.development[catpkg] = parsed['development']
    return True


def _apply_vendor(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                  path: Path) -> bool:
    if parsed.get('yarn_base_package'):
        check_instance(parsed['yarn_base_package'], 'yarn_base_package', 'string', path)
        settings.yarn_base_packages[catpkg] = parsed['yarn_base_package']
        if parsed.get('yarn_packages'):
            check_instance(parsed['yarn_packages'], 'yarn_packages', 'list', path)
            settings.yarn_packages[catpkg] = set(parsed['yarn_packages'])
    if parsed.get('go_sum_uri'):
        check_instance(parsed['go_sum_uri'], 'go_sum_uri', 'url', path)
        settings.go_sum_uri[catpkg] = parsed['go_sum_uri']
    if parsed.get('dotnet_project'):
        check_instance(parsed['dotnet_project'], 'dotnet_project', 'string', path)
        settings.dotnet_projects[catpkg] = parsed['dotnet_project']
    if 'dotnet_packages' in parsed:
        check_instance(parsed['dotnet_packages'], 'dotnet_packages', 'bool', path)
        settings.dotnet_packages[catpkg] = parsed['dotnet_packages']
    if 'gomodule' in parsed:
        check_instance(parsed['gomodule'], 'gomodule', 'bool', path)
        settings.gomodule_packages[catpkg] = parsed['gomodule']
        settings.gomodule_path[catpkg] = ''
        if parsed.get('gomodule_path'):
            check_instance(parsed['gomodule_path'], 'gomodule_path', 'string', path)
            settings.gomodule_path[catpkg] = parsed['gomodule_path']
    if 'nodejs' in parsed:
        _apply_nodejs(settings, parsed, catpkg, path)
    if 'composer' in parsed:
        check_instance(parsed['composer'], 'composer', 'bool', path)
        settings.composer_packages[catpkg] = parsed['composer']
        settings.composer_path[catpkg] = ''
        if parsed.get('composer_path'):
            check_instance(parsed['composer_path'], 'composer_path', 'string', path)
            settings.composer_path[catpkg] = parsed['composer_path']
    if 'maven' in parsed:
        check_instance(parsed['maven'], 'maven', 'bool', path)
        settings.maven_packages[catpkg] = parsed['maven']
        settings.maven_path[catpkg] = ''
        if parsed.get('maven_path'):
            check_instance(parsed['maven_path'], 'maven_path', 'string', path)
            settings.maven_path[catpkg] = parsed['maven_path']
    return True


def _apply_nodejs(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                  path: Path) -> None:
    check_instance(parsed['nodejs'], 'nodejs', 'bool', path)
    settings.nodejs_packages[catpkg] = parsed['nodejs']
    settings.nodejs_path[catpkg] = ''
    if parsed.get('nodejs_path'):
        check_instance(parsed['nodejs_path'], 'nodejs_path', 'string', path)
        settings.nodejs_path[catpkg] = parsed['nodejs_path']
    if parsed.get('nodejs_package_manager'):
        check_instance(parsed['nodejs_package_manager'], 'nodejs_package_manager', 'string', path)
        manager = parsed['nodejs_package_manager'].lower()
        if manager not in PACKAGE_MANAGERS:
            log.error('Invalid "nodejs_package_manager" in %s.', path)
        else:
            settings.nodejs_package_managers[catpkg] = manager


def _apply_version(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                   path: Path) -> bool:
    if 'pattern_version' in parsed or 'replace_version' in parsed:
        if 'pattern_version' not in parsed:
            log.error('No "pattern_version" in %s.', path)
            return False
        if 'replace_version' not in parsed:
            log.error('No "replace_version" in %s.', path)
            return False
        check_instance(parsed['pattern_version'], 'pattern_version', 'regex', path)
        check_instance(parsed['replace_version'], 'replace_version', 'string', path)
        settings.regex_version[catpkg] = (parsed['pattern_version'], parsed['replace_version'])
    if 'restrict_version' in parsed:
        if parsed['restrict_version'].lower() not in {'full', 'major', 'minor'}:
            log.error('Invalid "restrict_version" in %s.', path)
            return False
        settings.restrict_version[catpkg] = parsed['restrict_version'].lower()
    if 'sync_version' in parsed:
        check_instance(parsed['sync_version'], 'sync_version', 'string', path)
        settings.sync_version[catpkg] = parsed['sync_version']
    if 'stable_version' in parsed:
        check_instance(parsed['stable_version'], 'stable_version', 'regex', path)
        settings.stable_version[catpkg] = parsed['stable_version']
    return True


def _apply_request(settings: LivecheckSettings, parsed: Mapping[str, Any], catpkg: str,
                   path: Path) -> bool:
    if 'headers' in parsed:
        check_instance(parsed['headers'], 'headers', 'dict', path)
        settings.request_headers[catpkg] = parsed['headers']
    if 'params' in parsed:
        check_instance(parsed['params'], 'params', 'dict', path)
        settings.request_params[catpkg] = parsed['params']
    if 'method' in parsed:
        check_instance(parsed['method'], 'method', 'string', path)
        method = parsed['method'].upper()
        if method not in {'DELETE', 'GET', 'HEAD', 'PATCH', 'POST', 'PUT'}:
            log.error('Invalid "method" in %s. Must be GET, POST, PUT, DELETE, PATCH, or HEAD.',
                      path)
        else:
            settings.request_method[catpkg] = method
    if 'data' in parsed:
        check_instance(parsed['data'], 'data', 'dict', path)
        settings.request_data[catpkg] = parsed['data']
    if 'multiline' in parsed:
        check_instance(parsed['multiline'], 'multiline', 'bool', path)
        settings.regex_multiline[catpkg] = parsed['multiline']
    return True


_APPLIERS = (_apply_type, _apply_general, _apply_vendor, _apply_version, _apply_request)


def gather_settings(search_dir: Path) -> LivecheckSettings:
    """
    Gather settings from ``livecheck.json`` files in the given directory.

    A configuration naming an unknown ``transformation_function`` propagates
    :py:class:`UnknownTransformationFunction`.

    Parameters
    ----------
    search_dir : Path
        Directory tree to scan for configuration files.

    Returns
    -------
    LivecheckSettings
        Merged settings loaded from discovered configuration.
    """
    settings = LivecheckSettings()
    for path in search_dir.glob('**/livecheck.json'):
        log.debug('Opening %s.', path)
        with path.open() as f:
            try:
                parsed = json.load(f)
            except json.JSONDecodeError:
                log.exception('Error parsing file %s.', path)
                continue
        catpkg = f'{path.parent.parent.name}/{path.parent.name}'
        for apply_settings in _APPLIERS:
            if not apply_settings(settings, parsed, catpkg, path):
                break
    return settings


def check_instance(value: object,
                   key: str,
                   dtype: str,
                   path: str | object,
                   *,
                   specific_value: object | None = None) -> None:
    is_type = False
    match dtype:
        case 'bool':
            is_type = isinstance(value, bool)
        case 'int':
            is_type = isinstance(value, int)
        case 'string':
            is_type = isinstance(value, str)
        case 'none':
            is_type = value is None
        case 'list':
            is_type = isinstance(value, list)
        case 'dict':
            is_type = isinstance(value, dict)
        case 'url' if isinstance(value, str):
            parsed_url = urlparse(value)
            is_type = all([parsed_url.scheme, parsed_url.netloc])
        case 'regex' if isinstance(value, str):
            try:
                re.compile(value)
                is_type = True
            except re.error:
                is_type = False

    if not is_type:
        log.error('value "%s" in key "%s" is not of type "%s" in file "%s.', value, key, dtype,
                  path)

    if specific_value is not None and value != specific_value:
        log.error('Value "%s" in key "%s" is not equal to "%s" in file "%s".', value, key,
                  specific_value, path)
