from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import json
from urllib.parse import urlparse

import livecheck.special.handlers as sc

from . import utils

__all__ = ('LivecheckSettings', 'gather_settings')

from loguru import logger


@dataclass
class LivecheckSettings:
    branches: dict[str, str]
    checksum_livechecks: set[str]
    custom_livechecks: dict[str, tuple[str, str, bool, str]]
    dotnet_projects: dict[str, str]
    '''Dictionary of catpkg to project or solution file (base name only).'''
    go_sum_uri: dict[str, str]
    '''
    Dictionary of catpkg to full URI to ``go.sum`` with ``@PV@`` used for where version gets
    placed.
    '''
    ignored_packages: set[str]
    no_auto_update: set[str]
    semver: dict[str, bool]
    '''Disable auto-detection of semantic versioning.'''
    sha_sources: dict[str, str]
    transformations: Mapping[str, Callable[[str], str]]
    yarn_base_packages: dict[str, str]
    yarn_packages: dict[str, set[str]]
    jetbrains_packages: dict[str, bool]
    keep_old: dict[str, bool]
    gomodule_packages: dict[str, bool]
    gomodule_path: dict[str, str]
    nodejs_packages: dict[str, bool]
    nodejs_path: dict[str, str]


class UnknownTransformationFunction(NameError):
    def __init__(self, tfs: str):
        super().__init__(f'Unknown transformation function: {tfs}')


def gather_settings(search_dir: str) -> LivecheckSettings:
    branches: dict[str, str] = {}
    checksum_livechecks: set[str] = set()
    custom_livechecks: dict[str, tuple[str, str, bool, str]] = {}
    dotnet_projects: dict[str, str] = {}
    golang_packages: dict[str, str] = {}
    ignored_packages: set[str] = set()
    no_auto_update: set[str] = set()
    semver: dict[str, bool] = {}
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
    for path in Path(search_dir).glob('**/livecheck.json'):
        logger.debug(f"Opening {path}")
        with path.open() as f:
            dn = path.parent
            catpkg = f'{dn.parent.name}/{dn.name}'
            try:
                settings_parsed = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing file {path}: {e}")
                continue
            if settings_parsed.get('type') != None:
                if settings_parsed.get('type').lower() == 'none':
                    ignored_packages.add(catpkg)
                elif settings_parsed.get('type').lower() == 'regex':
                    custom_livechecks[catpkg] = (settings_parsed['url'], settings_parsed['regex'],
                                                 settings_parsed.get('use_vercmp', True),
                                                 settings_parsed.get('version', None))
                elif settings_parsed.get('type').lower() == 'checksum':
                    checksum_livechecks.add(catpkg)
                else:
                    logger.error(
                        f'Unknown "type" in {path}, only "none", "regex", and "checksum" are supported.'
                    )
            if settings_parsed.get('branch'):
                check_instance(settings_parsed['branch'], 'branch', 'string', path)
                branches[catpkg] = settings_parsed['branch']
            if 'no_auto_update' in settings_parsed:
                check_instance(settings_parsed['no_auto_update'], 'no_auto_update', 'bool', path,
                               True)
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
            if 'semver' in settings_parsed:
                check_instance(settings_parsed['semver'], 'semver', 'bool', path)
                semver[catpkg] = settings_parsed['semver']
            if 'jetbrains' in settings_parsed:
                check_instance(settings_parsed['jetbrains'], 'jetbrains', 'bool', path)
                jetbrains_packages[catpkg] = settings_parsed['jetbrains']
            if 'keep_old' in settings_parsed:
                check_instance(settings_parsed['keep_old'], 'keep_old', 'bool', path)
                keep_old[catpkg] = settings_parsed['keep_old']
            if 'gomodule' in settings_parsed:
                check_instance(settings_parsed['gomodule'], 'gomodule', 'bool', path)
                gomodule_packages[catpkg] = settings_parsed['gomodule']
                gomodule_path[catpkg] = ""
                if settings_parsed.get('gomodule_path'):
                    check_instance(settings_parsed['gomodule_path'], 'gomodule_path', 'string',
                                   path)
                    gomodule_path[catpkg] = settings_parsed['gomodule_path']
            if 'nodejs' in settings_parsed:
                check_instance(settings_parsed['nodejs'], 'nodejs', 'bool', path)
                nodejs_packages[catpkg] = settings_parsed['nodejs']
                nodejs_path[catpkg] = ""
                if settings_parsed.get('nodejs_path'):
                    check_instance(settings_parsed['nodejs_path'], 'nodejs_path', 'string', path)
                    nodejs_path[catpkg] = settings_parsed['nodejs_path']

    return LivecheckSettings(branches, checksum_livechecks, custom_livechecks, dotnet_projects,
                             golang_packages, ignored_packages, no_auto_update, semver, sha_sources,
                             transformations, yarn_base_packages, yarn_packages, jetbrains_packages,
                             keep_old, gomodule_packages, gomodule_path, nodejs_packages,
                             nodejs_path)


def check_instance(value: int | str | bool | list[str] | None,
                   key: str,
                   type: str,
                   path: str | object,
                   specific_value: bool | int | str | None = None) -> None:
    is_type = False
    if type == 'bool':
        is_type = isinstance(value, bool)
    elif type == 'int':
        is_type = isinstance(value, int)
    elif type == 'string':
        is_type = isinstance(value, str)
    elif type == 'none':
        is_type = value == None
    elif type == 'list':
        is_type = isinstance(value, list)
    elif type == 'url':
        if isinstance(value, str):
            parsed_url = urlparse(value)
            is_type = all([parsed_url.scheme, parsed_url.netloc])

    if not is_type:
        logger.error(f"Value \"{value}\" in key \"{key}\" is not of type \"{type}\" in file {path}")

    if specific_value is not None and value != specific_value:
        logger.error(
            f"Value \"{value}\" in key \"{key}\" is not equal to \"{specific_value}\" in file {path}"
        )
