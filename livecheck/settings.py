"""Settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import json
import logging
import re

from . import utils

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

__all__ = ('TYPE_CHECKSUM', 'TYPE_COMMIT', 'TYPE_DAVINCI', 'TYPE_DIRECTORY', 'TYPE_METADATA',
           'TYPE_NONE', 'TYPE_REGEX', 'TYPE_REPOLOGY', 'LivecheckSettings', 'gather_settings')

log = logging.getLogger(__name__)
TYPE_CHECKSUM = 'checksum'
TYPE_COMMIT = 'commit'
TYPE_DAVINCI = 'davinci'
TYPE_DIRECTORY = 'directory'
TYPE_METADATA = 'metadata'
TYPE_NONE = 'none'
TYPE_REGEX = 'regex'
TYPE_REPOLOGY = 'repology'

SETTINGS_TYPES = {
    TYPE_CHECKSUM, TYPE_COMMIT, TYPE_DAVINCI, TYPE_DIRECTORY, TYPE_METADATA, TYPE_NONE, TYPE_REGEX,
    TYPE_REPOLOGY
}


@dataclass
class LivecheckSettings:
    """All settings."""
    branches: dict[str, str] = field(default_factory=dict)
    custom_livechecks: dict[str, tuple[str, str]] = field(default_factory=dict)
    dotnet_projects: dict[str, str] = field(default_factory=dict)
    """Dictionary of catpkg to project or solution file (base name only)."""
    go_sum_uri: dict[str, str] = field(default_factory=dict)
    """
    Dictionary of catpkg to full URI to ``go.sum`` with ``@PV@`` used for
    where version gets placed.
    """
    type_packages: dict[str, str] = field(default_factory=dict)
    no_auto_update: set[str] = field(default_factory=set)
    """Disable auto-detection of semantic versioning."""
    sha_sources: dict[str, str] = field(default_factory=dict)
    transformations: Mapping[str, Callable[[str], str]] = field(default_factory=dict)
    yarn_base_packages: dict[str, str] = field(default_factory=dict)
    yarn_packages: dict[str, set[str]] = field(default_factory=dict)
    jetbrains_packages: dict[str, bool] = field(default_factory=dict)
    keep_old: dict[str, bool] = field(default_factory=dict)
    gomodule_packages: dict[str, bool] = field(default_factory=dict)
    gomodule_path: dict[str, str] = field(default_factory=dict)
    nodejs_packages: dict[str, bool] = field(default_factory=dict)
    nodejs_path: dict[str, str] = field(default_factory=dict)
    development: dict[str, bool] = field(default_factory=dict)
    composer_packages: dict[str, bool] = field(default_factory=dict)
    composer_path: dict[str, str] = field(default_factory=dict)
    maven_packages: dict[str, bool] = field(default_factory=dict)
    maven_path: dict[str, str] = field(default_factory=dict)
    regex_version: dict[str, tuple[str, str]] = field(default_factory=dict)
    restrict_version: dict[str, str] = field(default_factory=dict)
    sync_version: dict[str, str] = field(default_factory=dict)
    stable_version: dict[str, str] = field(default_factory=dict)
    # Settings from command line flag.
    auto_update_flag: bool = False
    debug_flag: bool = False
    development_flag: bool = False
    git_flag: bool = False
    keep_old_flag: bool = False
    progress_flag: bool = False
    # Internal settings.
    restrict_version_process: str = ''

    def is_devel(self, catpkg: str) -> bool:
        """Check if the package is a development version."""
        return self.development.get(catpkg, self.development_flag)


class UnknownTransformationFunction(NameError):
    def __init__(self, tfs: str) -> None:
        super().__init__(f'Unknown transformation function: {tfs}')


def gather_settings(search_dir: Path) -> LivecheckSettings:  # noqa: C901, PLR0912, PLR0914, PLR0915
    """
    Gather settings from ``livecheck.json`` files in the given directory.

    Raises
    ------
    UnknownTransformationFunction
        If a transformation function is invalid.
    """
    # Prevent circular import.
    import livecheck.special.handlers as sc  # noqa: PLC0415

    branches: dict[str, str] = {}
    custom_livechecks: dict[str, tuple[str, str]] = {}
    dotnet_projects: dict[str, str] = {}
    golang_packages: dict[str, str] = {}
    type_packages: dict[str, str] = {}
    no_auto_update: set[str] = set()
    sha_sources: dict[str, str] = {}
    transformations: dict[str, Callable[[str], str]] = {}
    yarn_base_packages: dict[str, str] = {}
    yarn_packages: dict[str, set[str]] = {}
    jetbrains_packages: dict[str, bool] = {}
    keep_old: dict[str, bool] = {}
    gomodule_packages: dict[str, bool] = {}
    gomodule_path: dict[str, str] = {}
    nodejs_packages: dict[str, bool] = {}
    nodejs_path: dict[str, str] = {}
    development: dict[str, bool] = {}
    composer_packages: dict[str, bool] = {}
    composer_path: dict[str, str] = {}
    maven_packages: dict[str, bool] = {}
    maven_path: dict[str, str] = {}
    regex_version: dict[str, tuple[str, str]] = {}
    restrict_version: dict[str, str] = {}
    sync_version: dict[str, str] = {}
    stable_version: dict[str, str] = {}

    for path in search_dir.glob('**/livecheck.json'):
        log.debug('Opening %s.', path)
        with path.open() as f:
            dn = path.parent
            catpkg = f'{dn.parent.name}/{dn.name}'
            try:
                settings_parsed = json.load(f)
            except json.JSONDecodeError:
                log.exception('Error parsing file %s.', path)
                continue
            if settings_parsed.get('type') is not None:
                type_ = settings_parsed.get('type').lower()
                if type_ == TYPE_REGEX:
                    if settings_parsed.get('url') is None:
                        log.error('No "url" in %s.', path)
                        continue
                    if settings_parsed.get('regex') is None:
                        log.error('No "regex" in %s.', path)
                        continue
                    custom_livechecks[catpkg] = (settings_parsed['url'], settings_parsed['regex'])
                if type_ == TYPE_REPOLOGY:
                    if settings_parsed.get('package') is None:
                        log.error('No "package" in %s.', path)
                        continue
                    custom_livechecks[catpkg] = (settings_parsed.get('package'), '')
                if type_ == TYPE_DIRECTORY:
                    if settings_parsed.get('url') is None:
                        log.error('No "url" in %s.', path)
                        continue
                    custom_livechecks[catpkg] = (settings_parsed.get('url'), '')
                if type_ not in SETTINGS_TYPES:
                    log.error('Unknown "type" in %s.', path)
                else:
                    type_packages[catpkg] = type_

            if settings_parsed.get('branch'):
                check_instance(settings_parsed['branch'], 'branch', 'string', path)
                branches[catpkg] = settings_parsed['branch']
            if 'no_auto_update' in settings_parsed:
                check_instance(settings_parsed['no_auto_update'], 'no_auto_update', 'bool', path,
                               True)  # noqa: FBT003
                no_auto_update.add(catpkg)
            if settings_parsed.get('transformation_function', None):
                tfs = settings_parsed['transformation_function']
                check_instance(settings_parsed['transformation_function'],
                               'transformation_function', 'string', path)
                try:
                    tf: Callable[[str], str] = getattr(sc, tfs)
                except AttributeError:
                    try:
                        tf = getattr(utils, tfs)
                    except AttributeError as e:
                        raise UnknownTransformationFunction(tfs) from e
                transformations[catpkg] = tf
            if settings_parsed.get('sha_source'):
                check_instance(settings_parsed['sha_source'], 'sha_source', 'url', path)
                sha_sources[catpkg] = settings_parsed['sha_source']
            if settings_parsed.get('yarn_base_package'):
                check_instance(settings_parsed['yarn_base_package'], 'yarn_base_package', 'string',
                               path)
                yarn_base_packages[catpkg] = settings_parsed['yarn_base_package']
                if settings_parsed.get('yarn_packages'):
                    check_instance(settings_parsed['yarn_packages'], 'yarn_packages', 'list', path)
                    yarn_packages[catpkg] = set(settings_parsed['yarn_packages'])
            if settings_parsed.get('go_sum_uri'):
                check_instance(settings_parsed['go_sum_uri'], 'go_sum_uri', 'url', path)
                golang_packages[catpkg] = settings_parsed['go_sum_uri']
            if settings_parsed.get('dotnet_project'):
                check_instance(settings_parsed['dotnet_project'], 'dotnet_project', 'string', path)
                dotnet_projects[catpkg] = settings_parsed['dotnet_project']
            if 'jetbrains' in settings_parsed:
                check_instance(settings_parsed['jetbrains'], 'jetbrains', 'bool', path)
                jetbrains_packages[catpkg] = settings_parsed['jetbrains']
            if 'keep_old' in settings_parsed:
                check_instance(settings_parsed['keep_old'], 'keep_old', 'bool', path)
                keep_old[catpkg] = settings_parsed['keep_old']
            if 'gomodule' in settings_parsed:
                check_instance(settings_parsed['gomodule'], 'gomodule', 'bool', path)
                gomodule_packages[catpkg] = settings_parsed['gomodule']
                gomodule_path[catpkg] = ''
                if settings_parsed.get('gomodule_path'):
                    check_instance(settings_parsed['gomodule_path'], 'gomodule_path', 'string',
                                   path)
                    gomodule_path[catpkg] = settings_parsed['gomodule_path']
            if 'nodejs' in settings_parsed:
                check_instance(settings_parsed['nodejs'], 'nodejs', 'bool', path)
                nodejs_packages[catpkg] = settings_parsed['nodejs']
                nodejs_path[catpkg] = ''
                if settings_parsed.get('nodejs_path'):
                    check_instance(settings_parsed['nodejs_path'], 'nodejs_path', 'string', path)
                    nodejs_path[catpkg] = settings_parsed['nodejs_path']
            if 'development' in settings_parsed:
                check_instance(settings_parsed['development'], 'development', 'bool', path)
                development[catpkg] = settings_parsed['development']
            if 'composer' in settings_parsed:
                check_instance(settings_parsed['composer'], 'composer', 'bool', path)
                composer_packages[catpkg] = settings_parsed['composer']
                composer_path[catpkg] = ''
                if settings_parsed.get('composer_path'):
                    check_instance(settings_parsed['composer_path'], 'composer_path', 'string',
                                   path)
                    composer_path[catpkg] = settings_parsed['composer_path']
            if 'maven' in settings_parsed:
                check_instance(settings_parsed['maven'], 'maven', 'bool', path)
                maven_packages[catpkg] = settings_parsed['maven']
                maven_path[catpkg] = ''
                if settings_parsed.get('maven_path'):
                    check_instance(settings_parsed['maven_path'], 'maven_path', 'string', path)
                    maven_path[catpkg] = settings_parsed['maven_path']
            if 'pattern_version' in settings_parsed or 'replace_version' in settings_parsed:
                if 'pattern_version' not in settings_parsed:
                    log.error('No "pattern_version" in %s.', path)
                    continue
                if 'replace_version' not in settings_parsed:
                    log.error('No "replace_version" in %s.', path)
                    continue
                check_instance(settings_parsed['pattern_version'], 'pattern_version', 'regex', path)
                check_instance(settings_parsed['replace_version'], 'replace_version', 'string',
                               path)
                regex_version[catpkg] = (settings_parsed['pattern_version'],
                                         settings_parsed['replace_version'])
            if 'restrict_version' in settings_parsed:
                if settings_parsed.get('restrict_version').lower(
                ) != 'full' and settings_parsed.get('restrict_version').lower(
                ) != 'major' and settings_parsed.get('restrict_version').lower() != 'minor':
                    log.error('Invalid "restrict_version" in %s.', path)
                    continue
                restrict_version[catpkg] = settings_parsed['restrict_version'].lower()
            if 'sync_version' in settings_parsed:
                check_instance(settings_parsed['sync_version'], 'sync_version', 'string', path)
                sync_version[catpkg] = settings_parsed['sync_version']
            if 'stable_version' in settings_parsed:
                check_instance(settings_parsed['stable_version'], 'stable_version', 'regex', path)
                stable_version[catpkg] = settings_parsed['stable_version']

    return LivecheckSettings(
        branches, custom_livechecks, dotnet_projects, golang_packages, type_packages,
        no_auto_update, sha_sources, transformations, yarn_base_packages, yarn_packages,
        jetbrains_packages, keep_old, gomodule_packages, gomodule_path, nodejs_packages,
        nodejs_path, development, composer_packages, composer_path, maven_packages, maven_path,
        regex_version, restrict_version, sync_version, stable_version)


def check_instance(
        value: int | str | bool | list[str] | None,  # noqa: FBT001
        key: str,
        dtype: str,
        path: str | object,
        specific_value: bool | int | str | None = None) -> None:  # noqa: FBT001
    is_type = False
    if dtype == 'bool':
        is_type = isinstance(value, bool)
    elif dtype == 'int':
        is_type = isinstance(value, int)
    elif dtype == 'string':
        is_type = isinstance(value, str)
    elif dtype == 'none':
        is_type = value is None
    elif dtype == 'list':
        is_type = isinstance(value, list)
    elif dtype == 'url':
        if isinstance(value, str):
            parsed_url = urlparse(value)
            is_type = all([parsed_url.scheme, parsed_url.netloc])
    elif dtype == 'regex' and isinstance(value, str):
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
